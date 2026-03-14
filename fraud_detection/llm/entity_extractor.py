"""
LLM-based entity extraction from call transcripts.

Extracts structured entities (phone numbers, bank accounts, scam personas)
from raw transcript text.  Uses OpenAI's function-calling API for reliable
JSON output at low latency.

Falls back to a fast regex-based extractor when the API is unavailable
or the OPENAI_API_KEY is not set — essential for hackathon demos.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from fraud_detection.config import LLMConfig

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\+?1?\s*\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")
_ACCOUNT_RE = re.compile(r"(?:account|acct|a/c)[#:\s\-]*([\w\-]{4,16})", re.IGNORECASE)
_PERSONA_KEYWORDS: dict[str, str] = {
    "irs": "IRS Agent",
    "tax": "IRS Agent",
    "tech support": "Tech Support",
    "microsoft": "Tech Support",
    "bank": "Bank Officer",
    "lottery": "Lottery Official",
    "prize": "Lottery Official",
    "medicare": "Medicare Rep",
    "social security": "Medicare Rep",
    "utility": "Utility Company",
    "electric": "Utility Company",
    "immigration": "Immigration Officer",
    "visa": "Immigration Officer",
    "crypto": "Crypto Advisor",
    "bitcoin": "Crypto Advisor",
    "investment": "Crypto Advisor",
}

EXTRACTION_PROMPT = """You are a fraud-analysis assistant.  Extract entities from the call transcript below.

Return ONLY a JSON object with these keys:
  - "phone_numbers": list of phone numbers mentioned (strings)
  - "bank_accounts": list of account identifiers mentioned (strings)
  - "persona": the scam persona being used if any (string or null)
  - "intent": brief classification of the caller's intent (string)
  - "risk_indicators": list of suspicious phrases or behaviours (strings)

Transcript:
\"\"\"
{transcript}
\"\"\"
"""


@dataclass
class ExtractionResult:
    phone_numbers: list[str] = field(default_factory=list)
    bank_accounts: list[str] = field(default_factory=list)
    persona: str | None = None
    intent: str = ""
    risk_indicators: list[str] = field(default_factory=list)
    source: str = "regex"


class EntityExtractor:
    """Dual-path entity extractor: LLM with regex fallback."""

    def __init__(self, cfg: LLMConfig | None = None) -> None:
        self.cfg = cfg or LLMConfig()
        self._client = None

        if self.cfg.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.cfg.api_key,
                    timeout=self.cfg.timeout_seconds,
                )
                logger.info("OpenAI client initialised (model=%s)", self.cfg.model_name)
            except Exception:
                logger.warning("OpenAI client init failed; falling back to regex extractor.")

    async def extract(self, transcript: str) -> ExtractionResult:
        """Extract entities — tries LLM first, falls back to regex."""
        if self._client:
            try:
                return await self._extract_llm(transcript)
            except Exception as exc:
                logger.warning("LLM extraction failed (%s); using regex fallback", exc)

        return self._extract_regex(transcript)

    # ── LLM path ──────────────────────────────────────────────────────

    async def _extract_llm(self, transcript: str) -> ExtractionResult:
        import asyncio

        prompt = EXTRACTION_PROMPT.format(transcript=transcript)

        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self.cfg.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        return ExtractionResult(
            phone_numbers=data.get("phone_numbers", []),
            bank_accounts=data.get("bank_accounts", []),
            persona=data.get("persona"),
            intent=data.get("intent", ""),
            risk_indicators=data.get("risk_indicators", []),
            source="llm",
        )

    # ── Regex fallback path ───────────────────────────────────────────

    @staticmethod
    def _extract_regex(transcript: str) -> ExtractionResult:
        phones = _PHONE_RE.findall(transcript)
        accounts = _ACCOUNT_RE.findall(transcript)

        persona = None
        lower = transcript.lower()
        for keyword, persona_name in _PERSONA_KEYWORDS.items():
            if keyword in lower:
                persona = persona_name
                break

        risk_indicators: list[str] = []
        suspicious_phrases = [
            "gift card", "wire transfer", "do not tell anyone",
            "don't tell anyone", "act now", "you will be arrested",
            "your ssn", "social security", "warrant",
            "suspend your account", "immediate payment",
            "don't hang up", "do not hang up", "guaranteed returns",
            "guaranteed return", "send payment", "processing fee",
        ]
        for phrase in suspicious_phrases:
            if phrase in lower:
                risk_indicators.append(phrase)

        intent = "unknown"
        if risk_indicators:
            intent = "potential_scam"
        elif persona and persona in {
            "IRS Agent", "Tech Support", "Lottery Official",
            "Medicare Rep", "Immigration Officer",
        }:
            intent = "impersonation_scam"

        return ExtractionResult(
            phone_numbers=phones,
            bank_accounts=accounts,
            persona=persona,
            intent=intent,
            risk_indicators=risk_indicators,
            source="regex",
        )
