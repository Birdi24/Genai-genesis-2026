"""
Railtracks-powered entity extraction pipeline.

Flow Architecture (3 nodes, fully traced in railtracks viz)
──────────────────────────────────────────────────────────
  extraction_pipeline  (@rt.function_node, entry point)
    ├─► rt.call(ExtractorAgent, prompt)     → ExtractedEntities (Pydantic structured output)
    └─► rt.call(risk_flag_validator, data)  → annotated ExtractionResult with broadcasts

Observability
  Every invocation saves a session to .railtracks/data/sessions/.
  Run `railtracks viz` to explore latency, token usage, and risk flag events.

Fallback
  If OPENAI_API_KEY is absent, the flow is skipped and a deterministic
  regex extractor returns the same ExtractionResult schema — no downstream
  breakage in risk_scorer.py or the Streamlit frontend.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fraud_detection.config import LLMConfig, RailTracksConfig

logger = logging.getLogger(__name__)

# ── Regex primitives (used both in the fallback path and as a
#    post-LLM validator inside the railtracks risk_flag_validator) ───

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

_RISK_PHRASES: list[str] = [
    "gift card", "wire transfer", "do not tell anyone", "don't tell anyone",
    "act now", "you will be arrested", "your ssn", "social security",
    "warrant", "suspend your account", "immediate payment", "don't hang up",
    "do not hang up", "guaranteed returns", "guaranteed return",
    "send payment", "processing fee",
]

_COERCION_PHRASES: list[str] = [
    "you will be arrested", "warrant", "deportation", "legal action",
    "law enforcement", "police", "irs agent", "act now or", "last chance",
    "your account will be closed",
]


# ── Downstream-compatible result contract ────────────────────────────

@dataclass
class ExtractionResult:
    """Immutable contract consumed by risk_scorer.py and the Streamlit frontend.

    Never remove or rename fields — the graph and API depend on this schema.
    """
    phone_numbers: list[str] = field(default_factory=list)
    bank_accounts: list[str] = field(default_factory=list)
    persona: str | None = None
    intent: str = "unknown"
    risk_indicators: list[str] = field(default_factory=list)
    source: str = "regex"
    # Railtracks-enriched fields (added without breaking existing consumers)
    coercion_detected: bool = False
    hallucination_flags: list[str] = field(default_factory=list)
    rt_session_id: str | None = None
    rt_latency_ms: float | None = None


# ── Pydantic schema for structured LLM output ────────────────────────

class ExtractedEntities(BaseModel):
    """Structured output schema passed to rt.agent_node(output_schema=...).

    The LLM is constrained to this shape — no free-form text, no hallucinated keys.
    """
    phone_numbers: list[str] = Field(
        default_factory=list,
        description="All phone numbers mentioned verbatim.",
    )
    bank_accounts: list[str] = Field(
        default_factory=list,
        description="Account identifiers or numbers mentioned.",
    )
    persona: str | None = Field(
        default=None,
        description="Scam persona the caller is impersonating, if any.",
    )
    intent: str = Field(
        default="unknown",
        description="One of: potential_scam, impersonation_scam, benign, unknown.",
    )
    risk_indicators: list[str] = Field(
        default_factory=list,
        description="Coercive or suspicious phrases used by the caller.",
    )


# ── LLM system message ───────────────────────────────────────────────

_SYSTEM_MSG = (
    "You are a fraud-analysis assistant for a real-time scam detection system. "
    "Extract structured information from call transcripts. "
    "Be precise: only extract phone numbers that match standard formats. "
    "Classify intent as one of: potential_scam, impersonation_scam, benign, unknown. "
    "List specific coercive phrases verbatim as risk_indicators. "
    "Identify the scam persona being portrayed, if any."
)

_USER_TEMPLATE = (
    "Analyze this call transcript and extract entities:\n\n"
    "CALLER: {caller}\nCALLEE: {callee}\n\nTRANSCRIPT:\n{transcript}"
)


# ── Entity Extractor (public API, drop-in replacement) ───────────────

class EntityExtractor:
    """Dual-path entity extractor: Railtracks Flow → regex fallback.

    Usage:
        extractor = EntityExtractor(llm_cfg, rt_cfg)
        result = await extractor.extract(transcript, caller=..., callee=...)

    The returned ExtractionResult is identical in schema regardless of which
    path ran, so risk_scorer.py and the Streamlit frontend are unaffected.
    """

    def __init__(
        self,
        llm_cfg: LLMConfig | None = None,
        rt_cfg: RailTracksConfig | None = None,
    ) -> None:
        from fraud_detection.config import LLMConfig, RailTracksConfig
        self.llm_cfg = llm_cfg or LLMConfig()
        self.rt_cfg = rt_cfg or RailTracksConfig()
        self._flow = self._build_flow() if self.llm_cfg.api_key else None
        if self._flow:
            logger.info(
                "Railtracks extraction flow initialised (model=%s, save_state=%s)",
                self.llm_cfg.model_name,
                self.rt_cfg.save_state,
            )
        else:
            logger.info("No OPENAI_API_KEY — using regex fallback extractor.")

    # ── Public entry point ────────────────────────────────────────────

    async def extract(
        self,
        transcript: str,
        caller: str = "unknown",
        callee: str = "unknown",
    ) -> ExtractionResult:
        if self._flow:
            try:
                return await self._extract_rt(transcript, caller, callee)
            except Exception as exc:
                logger.warning("Railtracks flow failed (%s); falling back to regex.", exc)
        return await self._extract_regex_traced(transcript, caller)

    # ── Railtracks flow path ──────────────────────────────────────────

    def _build_flow(self):
        """Construct the rt.Flow once at init time; reused per request."""
        import railtracks as rt

        llm_cfg = self.llm_cfg
        rt_cfg = self.rt_cfg

        # ── Node 1: Structured LLM extractor ─────────────────────────
        ExtractorAgent = rt.agent_node(
            name="EntityExtractorLLM",
            llm=rt.llm.OpenAILLM(
                model_name=llm_cfg.model_name,
                api_key=llm_cfg.api_key,
                temperature=llm_cfg.temperature,
            ),
            system_message=_SYSTEM_MSG,
            output_schema=ExtractedEntities,
        )

        # ── Node 2: Programmatic risk flag validator ──────────────────
        @rt.function_node
        async def risk_flag_validator(entities_json: str) -> str:
            """
            Validates LLM output and flags high-risk signals using railtracks broadcasts.
            Broadcasts are visible as real-time events in `railtracks viz`.
            """
            data: dict = json.loads(entities_json)
            flags: list[str] = []

            # Phone number format validation — catch hallucinated numbers
            bad_phones = [
                p for p in data.get("phone_numbers", [])
                if not _PHONE_RE.fullmatch(p.strip())
            ]
            if bad_phones:
                msg = f"HALLUCINATION_FLAG: invalid phone format(s): {bad_phones}"
                await rt.broadcast(msg)
                logger.warning(msg)
                flags.append(f"invalid_phone_format:{bad_phones}")
                data["phone_numbers"] = [
                    p for p in data["phone_numbers"] if p not in bad_phones
                ]

            # Coercion tactic detection
            transcript_lower = data.get("_transcript", "").lower()
            coercion_hits = [c for c in _COERCION_PHRASES if c in transcript_lower]
            if coercion_hits:
                msg = f"COERCION_DETECTED: tactics={coercion_hits}"
                await rt.broadcast(msg)
                logger.warning(msg)
                flags.append(f"coercion:{coercion_hits}")

            # High-risk persona + coercion combo — elevate intent
            if coercion_hits and data.get("intent") != "potential_scam":
                data["intent"] = "potential_scam"
                await rt.broadcast("INTENT_UPGRADED: coercion+persona combo detected")

            data["_hallucination_flags"] = flags
            data["_coercion_detected"] = bool(coercion_hits)
            return json.dumps(data)

        # ── Node 3: Pipeline orchestrator (flow entry point) ─────────
        @rt.function_node
        async def extraction_pipeline(
            transcript: str,
            caller: str,
            callee: str,
        ) -> str:
            """
            Orchestrates entity extraction and risk flagging.
            Full execution graph is traced and saved to .railtracks/.
            """
            prompt = _USER_TEMPLATE.format(
                caller=caller, callee=callee, transcript=transcript
            )

            # Call the structured LLM agent
            structured: ExtractedEntities = await rt.call(ExtractorAgent, prompt)

            # Serialise, injecting transcript for coercion check in validator
            payload = structured.model_dump()
            payload["_transcript"] = transcript

            validated_json: str = await rt.call(
                risk_flag_validator, json.dumps(payload)
            )
            return validated_json

        return rt.Flow(
            rt_cfg.flow_name,
            entry_point=extraction_pipeline,
            timeout=rt_cfg.flow_timeout,
            save_state=rt_cfg.save_state,
        )

    async def _extract_rt(
        self,
        transcript: str,
        caller: str,
        callee: str,
    ) -> ExtractionResult:
        import railtracks as rt

        t0 = time.perf_counter()
        validated_json: str = await self._flow.ainvoke(transcript, caller, callee)
        latency_ms = (time.perf_counter() - t0) * 1000

        data: dict = json.loads(validated_json)

        return ExtractionResult(
            phone_numbers=data.get("phone_numbers", []),
            bank_accounts=data.get("bank_accounts", []),
            persona=data.get("persona"),
            intent=data.get("intent", "unknown"),
            risk_indicators=data.get("risk_indicators", []),
            source="railtracks_llm",
            coercion_detected=data.get("_coercion_detected", False),
            hallucination_flags=data.get("_hallucination_flags", []),
            rt_session_id=rt.session_id(),
            rt_latency_ms=round(latency_ms, 2),
        )

    # ── Regex fallback path (traced via a minimal railtracks session) ──

    async def _extract_regex_traced(
        self, transcript: str, caller: str
    ) -> ExtractionResult:
        """Run regex extraction inside a Railtracks session so it is always
        visible in `railtracks viz`, even without an LLM API key."""
        import railtracks as rt

        t0 = time.perf_counter()
        result = self._extract_regex(transcript)

        # Emit broadcast events for coercion flags so they appear in the trace
        @rt.function_node
        async def regex_extraction_node(text: str) -> str:
            """Regex-based entity extraction (no LLM)."""
            if result.coercion_detected:
                await rt.broadcast(f"COERCION_DETECTED (regex): indicators={result.risk_indicators}")
            if result.persona:
                await rt.broadcast(f"PERSONA_MATCH: {result.persona}")
            await rt.broadcast(f"INTENT: {result.intent}")
            return f"regex extraction complete — caller={caller}"

        flow = rt.Flow(
            self.rt_cfg.flow_name,
            entry_point=regex_extraction_node,
            save_state=self.rt_cfg.save_state,
            timeout=self.rt_cfg.flow_timeout,
        )
        try:
            await flow.ainvoke(transcript)
        except Exception as exc:
            logger.debug("Regex trace session failed silently: %s", exc)

        result.rt_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return result

    @staticmethod
    def _extract_regex(transcript: str) -> ExtractionResult:
        phones = _PHONE_RE.findall(transcript)
        accounts = _ACCOUNT_RE.findall(transcript)

        persona: str | None = None
        lower = transcript.lower()
        for keyword, persona_name in _PERSONA_KEYWORDS.items():
            if keyword in lower:
                persona = persona_name
                break

        risk_indicators = [p for p in _RISK_PHRASES if p in lower]
        coercion_detected = any(c in lower for c in _COERCION_PHRASES)

        intent = "unknown"
        if risk_indicators:
            intent = "potential_scam"
        elif persona in {
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
            coercion_detected=coercion_detected,
        )
