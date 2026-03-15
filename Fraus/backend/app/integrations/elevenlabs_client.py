from dataclasses import dataclass
import logging
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx


logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ElevenLabsStartResult:
    provider_name: str
    provider_status: str
    elevenlabs_agent_id: Optional[str]
    elevenlabs_conversation_id: Optional[str]
    signed_url: Optional[str] = None
    initiation_method: Optional[str] = None
    signed_url_obtained: bool = False
    conversation_token_obtained: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None


class ElevenLabsClient:
    def __init__(self, api_key: str, agent_id: str, base_url: str):
        self.api_key = api_key.strip()
        self.agent_id = agent_id.strip()
        self.base_url = base_url.rstrip("/")

    async def start_conversation(
        self,
        *,
        session_id: str,
        phone_number: str,
        caller_label: str,
        risk_level: str,
    ) -> ElevenLabsStartResult:
        logger.info(
            "ElevenLabs env detected: api_key=%s agent_id=%s",
            bool(self.api_key),
            bool(self.agent_id),
        )

        if not self.api_key or not self.agent_id:
            logger.warning("ElevenLabs initiation failed: missing ELEVENLABS_API_KEY or ELEVENLABS_AGENT_ID")
            return ElevenLabsStartResult(
                provider_name="elevenlabs",
                provider_status="degraded_missing_configuration",
                elevenlabs_agent_id=self.agent_id or None,
                elevenlabs_conversation_id=None,
                initiation_method="signed_url",
                signed_url_obtained=False,
                conversation_token_obtained=False,
                error="ELEVENLABS_API_KEY or ELEVENLABS_AGENT_ID not configured",
            )

        logger.info("ElevenLabs initiation path used: signed_url")

        headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/json",
        }

        endpoint = f"{self.base_url}/convai/conversation/get-signed-url"
        params = {"agent_id": self.agent_id}

        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                response = await client.get(endpoint, headers=headers, params=params)
            except Exception as error:
                logger.exception("ElevenLabs initiation request failed")
                return ElevenLabsStartResult(
                    provider_name="elevenlabs",
                    provider_status="degraded_unavailable",
                    elevenlabs_agent_id=self.agent_id,
                    elevenlabs_conversation_id=None,
                    initiation_method="signed_url",
                    signed_url_obtained=False,
                    conversation_token_obtained=False,
                    error=f"signed_url request failed: {error}",
                )

        logger.info("ElevenLabs initiation HTTP status: %s", response.status_code)

        response_json: dict[str, Any]
        try:
            response_json = response.json()
        except Exception:
            response_json = {}

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning("ElevenLabs initiation failed with HTTP %s", response.status_code)
            return ElevenLabsStartResult(
                provider_name="elevenlabs",
                provider_status="degraded_unavailable",
                elevenlabs_agent_id=self.agent_id,
                elevenlabs_conversation_id=None,
                initiation_method="signed_url",
                signed_url_obtained=False,
                conversation_token_obtained=False,
                http_status=response.status_code,
                error=f"GET /convai/conversation/get-signed-url HTTP {response.status_code}",
                raw_response=response_json,
            )

        signed_url = response_json.get("signed_url")
        if not signed_url:
            logger.warning("ElevenLabs initiation failed: signed_url missing in response")
            return ElevenLabsStartResult(
                provider_name="elevenlabs",
                provider_status="degraded_unavailable",
                elevenlabs_agent_id=self.agent_id,
                elevenlabs_conversation_id=None,
                initiation_method="signed_url",
                signed_url_obtained=False,
                conversation_token_obtained=False,
                http_status=response.status_code,
                error="signed_url missing in ElevenLabs response",
                raw_response=response_json,
            )

        conversation_id = self._extract_conversation_id(response_json)
        logger.info("ElevenLabs initiation success: signed_url obtained=%s", True)

        return ElevenLabsStartResult(
            provider_name="elevenlabs",
            provider_status="prepared_signed_url",
            elevenlabs_agent_id=self.agent_id,
            elevenlabs_conversation_id=conversation_id,
            signed_url=signed_url,
            initiation_method="signed_url",
            signed_url_obtained=True,
            conversation_token_obtained=False,
            http_status=response.status_code,
            raw_response=response_json,
        )

    @staticmethod
    def _extract_conversation_id(payload: dict[str, Any]) -> Optional[str]:
        signed_url = payload.get("signed_url")
        if isinstance(signed_url, str) and signed_url:
            parsed = urlparse(signed_url)
            query = parse_qs(parsed.query)
            candidate = (
                query.get("conversation_id", [None])[0]
                or query.get("conversation", [None])[0]
                or query.get("conversation_signature", [None])[0]
                or query.get("token", [None])[0]
            )
            if candidate:
                return str(candidate)

        nested_conversation_id = None
        conversation = payload.get("conversation")
        if isinstance(conversation, dict):
            nested_conversation_id = conversation.get("id")

        value = (
            payload.get("conversation_id")
            or payload.get("id")
            or payload.get("session_id")
            or nested_conversation_id
        )
        return str(value) if value else None
