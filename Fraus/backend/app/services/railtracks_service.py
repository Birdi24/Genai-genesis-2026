import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AnalysisResult:
    transcript_notes: list[str]
    scam_indicators: list[str]
    extracted_entities: list[dict[str, Any]]
    business_intelligence_steps: list[str]
    tags: dict[str, Any]
    analysis_metadata: dict[str, Any]


class RailtracksService:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.railtracks_available = self._detect_railtracks()

    def _detect_railtracks(self) -> bool:
        if not self.enabled:
            return False
        try:
            __import__("railtracks")
            return True
        except Exception:
            return False

    async def analyze_takeover_session(
        self,
        *,
        phone_number: str,
        caller_label: str,
        risk_level: str,
        transcript_text: Optional[str] = None,
    ) -> AnalysisResult:
        transcript = transcript_text or self._build_demo_transcript(caller_label, risk_level)
        transcript_notes = self._build_transcript_notes(transcript)
        scam_indicators = self._extract_scam_indicators(transcript, risk_level)
        extracted_entities = self._extract_entities(transcript, phone_number)
        tags = self._derive_tags(transcript, caller_label)
        business_steps = self._build_business_steps(scam_indicators, tags)

        return AnalysisResult(
            transcript_notes=transcript_notes,
            scam_indicators=scam_indicators,
            extracted_entities=extracted_entities,
            business_intelligence_steps=business_steps,
            tags=tags,
            analysis_metadata={
                "engine": "railtracks-python-flow" if self.railtracks_available else "python-sequential-fallback",
                "railtracks_available": self.railtracks_available,
                "flow_version": "mvp-sequential-v1",
            },
        )

    def _build_demo_transcript(self, caller_label: str, risk_level: str) -> str:
        return (
            f"Caller identified as {caller_label}. "
            "Claims unusual account activity and requests immediate OTP confirmation. "
            "Caller asks victim to move funds to a safe account due to urgent fraud hold. "
            f"Risk context provided by verifier: {risk_level}."
        )

    def _build_transcript_notes(self, transcript: str) -> list[str]:
        normalized = " ".join(transcript.split())
        if not normalized:
            return ["No transcript available."]
        chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
        return chunks[:6]

    def _extract_scam_indicators(self, transcript: str, risk_level: str) -> list[str]:
        text = transcript.lower()
        indicators: list[str] = []
        keyword_map = {
            "otp": "otp request detected",
            "one-time": "otp request detected",
            "urgent": "urgency pressure language",
            "immediately": "urgency pressure language",
            "safe account": "fund transfer redirection",
            "transfer": "fund transfer redirection",
            "gift card": "gift-card payment signal",
            "wire": "wire/payment coercion",
            "crypto": "crypto payment coercion",
            "password": "credential harvesting attempt",
        }
        for keyword, label in keyword_map.items():
            if keyword in text and label not in indicators:
                indicators.append(label)

        if risk_level.lower() in {"high", "critical"} and "high-risk verification context" not in indicators:
            indicators.append("high-risk verification context")

        return indicators or ["suspicious caller behavior"]

    def _extract_entities(self, transcript: str, phone_number: str) -> list[dict[str, Any]]:
        text = transcript
        entities: list[dict[str, Any]] = [
            {"key": "phone_number", "value": phone_number, "confidence": 1.0}
        ]

        otp_matches = re.findall(r"\b(\d{4,8})\b", text)
        if otp_matches:
            entities.append({"key": "otp_code_candidate", "value": otp_matches[0], "confidence": 0.6})

        amount_match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
        if amount_match:
            entities.append({"key": "requested_amount", "value": amount_match.group(1), "confidence": 0.8})

        brand_map = {
            "bank": "bank",
            "apple": "apple",
            "amazon": "amazon",
            "irs": "irs",
            "microsoft": "microsoft",
        }
        lowered = text.lower()
        for token, brand in brand_map.items():
            if token in lowered:
                entities.append({"key": "impersonated_brand", "value": brand, "confidence": 0.75})
                break

        return entities

    def _derive_tags(self, transcript: str, caller_label: str) -> dict[str, Any]:
        lower = transcript.lower()
        label_lower = caller_label.lower()

        impersonated_brand = None
        for brand in ("bank", "apple", "amazon", "irs", "microsoft"):
            if brand in lower or brand in label_lower:
                impersonated_brand = brand
                break

        requested_action = "share_sensitive_info" if any(
            token in lower for token in ("otp", "password", "code")
        ) else "unknown"

        urgency_detected = any(token in lower for token in ("urgent", "immediately", "now"))
        otp_requested = any(token in lower for token in ("otp", "one-time", "verification code"))
        payment_requested = any(token in lower for token in ("transfer", "wire", "gift card", "crypto", "payment"))

        return {
            "impersonated_brand": impersonated_brand,
            "requested_action": requested_action,
            "urgency_detected": urgency_detected,
            "otp_requested": otp_requested,
            "payment_requested": payment_requested,
        }

    def _build_business_steps(self, indicators: list[str], tags: dict[str, Any]) -> list[str]:
        steps = [
            "Takeover session created and monitoring initiated",
            "Transcript processed through sequential fraud analysis flow",
        ]

        if indicators:
            steps.append(f"Detected {len(indicators)} scam indicator(s)")

        if tags.get("otp_requested"):
            steps.append("Advise user not to share OTP or verification code")

        if tags.get("payment_requested"):
            steps.append("Recommend freezing outgoing transfers pending verification")

        return steps
