from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.integrations.elevenlabs_client import ElevenLabsClient
from app.schemas.takeover import (
    ExtractedEntity,
    StartTakeoverRequest,
    TakeoverSessionEventRequest,
    TakeoverSessionEventResponse,
    TakeoverSessionResponse,
)
from app.services.railtracks_service import RailtracksService
from app.services.verification_service import VerificationService


class TakeoverService:
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database["takeover_sessions"]
        self.verification_service = VerificationService(database)
        self.elevenlabs_client = ElevenLabsClient(
            api_key=settings.elevenlabs_api_key,
            agent_id=settings.elevenlabs_agent_id,
            base_url=settings.elevenlabs_base_url,
        )
        self.railtracks_service = RailtracksService(enabled=settings.railtracks_enabled)

    async def start_takeover(self, payload: StartTakeoverRequest) -> TakeoverSessionResponse:
        normalized_phone = self.verification_service.normalize_phone_number(payload.phone_number)
        session_id = f"fraus_{uuid4().hex}"
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        provider_result = await self.elevenlabs_client.start_conversation(
            session_id=session_id,
            phone_number=normalized_phone,
            caller_label=payload.caller_label,
            risk_level=payload.risk_level,
        )

        analysis_result = await self.railtracks_service.analyze_takeover_session(
            phone_number=normalized_phone,
            caller_label=payload.caller_label,
            risk_level=payload.risk_level,
        )

        document = {
            "session_id": session_id,
            "phone_number": normalized_phone,
            "caller_label": payload.caller_label,
            "risk_level": payload.risk_level,
            "status_text": self._status_text_for_provider(provider_result.provider_status),
            "connection_state": self._connection_state_for_provider(provider_result.provider_status),
            "conversation_signed_url": provider_result.signed_url,
            "ai_agent_name": settings.takeover_ai_agent_name,
            "started_at": started_at,
            "transcript_notes": analysis_result.transcript_notes,
            "scam_indicators": analysis_result.scam_indicators,
            "extracted_entities": analysis_result.extracted_entities,
            "business_intelligence_steps": analysis_result.business_intelligence_steps,
            "session_status": "active",
            "provider_metadata": {
                "provider_name": provider_result.provider_name,
                "elevenlabs_agent_id": provider_result.elevenlabs_agent_id,
                "elevenlabs_conversation_id": provider_result.elevenlabs_conversation_id,
                "conversation_signed_url": provider_result.signed_url,
                "provider_status": provider_result.provider_status,
                "initiation_method": provider_result.initiation_method,
                "signed_url_obtained": provider_result.signed_url_obtained,
                "conversation_token_obtained": provider_result.conversation_token_obtained,
                "provider_http_status": provider_result.http_status,
                "provider_error": provider_result.error,
            },
            "analysis_metadata": {
                **analysis_result.analysis_metadata,
                "tags": analysis_result.tags,
            },
        }

        await self.collection.insert_one(document)
        return self._response_from_document(document)

    async def get_session(self, session_id: str) -> Optional[TakeoverSessionResponse]:
        document = await self.collection.find_one({"session_id": session_id})
        if not document:
            return None
        return self._response_from_document(document)

    async def ingest_session_event(
        self,
        *,
        session_id: str,
        payload: TakeoverSessionEventRequest,
    ) -> Optional[TakeoverSessionEventResponse]:
        document = await self.collection.find_one({"session_id": session_id})
        if not document:
            return None

        occurred_at = payload.occurred_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        event = {
            "type": payload.event_type,
            "source": payload.source,
            "role": payload.role,
            "text": payload.text,
            "metadata": payload.metadata,
            "occurred_at": occurred_at,
        }

        existing_events = list(document.get("conversation_events", []))
        updated_events = [*existing_events, event]
        transcript_text = self._build_transcript_from_events(updated_events)

        analysis_result = await self.railtracks_service.analyze_takeover_session(
            phone_number=document.get("phone_number", "unknown"),
            caller_label=document.get("caller_label", "Unknown Caller"),
            risk_level=document.get("risk_level", "unknown"),
            transcript_text=transcript_text,
        )

        next_connection_state = self._derive_connection_state_from_event(
            current_state=document.get("connection_state", "prepared"),
            event_type=payload.event_type,
        )
        next_status_text = self._status_text_for_connection_state(next_connection_state)

        update_result = await self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"conversation_events": event},
                "$set": {
                    "connection_state": next_connection_state,
                    "status_text": next_status_text,
                    "transcript_notes": analysis_result.transcript_notes,
                    "scam_indicators": analysis_result.scam_indicators,
                    "extracted_entities": analysis_result.extracted_entities,
                    "business_intelligence_steps": analysis_result.business_intelligence_steps,
                    "analysis_metadata": {
                        **analysis_result.analysis_metadata,
                        "tags": analysis_result.tags,
                        "event_count": len(updated_events),
                        "last_event_type": payload.event_type,
                        "last_event_source": payload.source,
                        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    },
                    "provider_metadata.last_event_type": payload.event_type,
                },
            },
        )

        if update_result.matched_count == 0:
            return None

        return TakeoverSessionEventResponse(
            session_id=session_id,
            accepted=True,
            event_count=len(updated_events),
            connection_state=next_connection_state,
            status_text=next_status_text,
        )

    def _response_from_document(self, document: dict) -> TakeoverSessionResponse:
        extracted_entities = [ExtractedEntity(**item) for item in document.get("extracted_entities", [])]
        return TakeoverSessionResponse(
            session_id=document["session_id"],
            phone_number=document["phone_number"],
            status_text=document.get("status_text", "Takeover session active"),
            connection_state=document.get(
                "connection_state",
                self._connection_state_for_provider(
                    str(document.get("provider_metadata", {}).get("provider_status", "degraded"))
                ),
            ),
            conversation_signed_url=document.get("conversation_signed_url")
            or document.get("provider_metadata", {}).get("conversation_signed_url"),
            ai_agent_name=document.get("ai_agent_name", settings.takeover_ai_agent_name),
            started_at=document.get("started_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            transcript_notes=list(document.get("transcript_notes", [])),
            scam_indicators=list(document.get("scam_indicators", [])),
            extracted_entities=extracted_entities,
            business_intelligence_steps=list(document.get("business_intelligence_steps", [])),
        )

    @staticmethod
    def _status_text_for_provider(provider_status: str) -> str:
        if provider_status == "prepared_signed_url":
            return "AI takeover prepared. Signed conversation URL generated; live call starts when client connects."
        if provider_status.startswith("active") or provider_status == "partial":
            return "AI takeover active. Monitoring and analysis in progress."
        return "AI takeover started in fallback mode. Continuing protection and analysis."

    @staticmethod
    def _connection_state_for_provider(provider_status: str) -> str:
        if provider_status == "prepared_signed_url":
            return "prepared"
        if provider_status.startswith("active") or provider_status == "partial":
            return "live"
        return "degraded"

    @staticmethod
    def _derive_connection_state_from_event(current_state: str, event_type: str) -> str:
        normalized_event = event_type.lower()
        if "error" in normalized_event or "failed" in normalized_event:
            return "degraded"
        if normalized_event in {
            "connected",
            "conversation_started",
            "audio_playback_started",
            "agent_response",
            "transcript",
        }:
            return "live"
        return current_state

    @staticmethod
    def _status_text_for_connection_state(connection_state: str) -> str:
        if connection_state == "prepared":
            return "AI takeover prepared. Signed conversation URL generated; live call starts when client connects."
        if connection_state == "live":
            return "AI takeover active. Monitoring and analysis in progress."
        return "AI takeover started in fallback mode. Continuing protection and analysis."

    @staticmethod
    def _build_transcript_from_events(events: list[dict]) -> str:
        lines: list[str] = []
        for event in events:
            text = str(event.get("text") or "").strip()
            if not text:
                continue
            role = str(event.get("role") or event.get("source") or "unknown").strip()
            lines.append(f"{role}: {text}")
        return "\n".join(lines)
