from pydantic import BaseModel, Field
from typing import Any, Optional


class StartTakeoverRequest(BaseModel):
    phone_number: str = Field(..., min_length=3, max_length=32)
    caller_label: str = Field(..., min_length=1, max_length=128)
    risk_level: str = Field(..., min_length=1, max_length=32)


class ExtractedEntity(BaseModel):
    key: str
    value: str
    confidence: Optional[float] = None


class TakeoverSessionResponse(BaseModel):
    session_id: str
    phone_number: str
    status_text: str
    connection_state: str
    conversation_signed_url: Optional[str] = None
    ai_agent_name: str
    started_at: str
    transcript_notes: list[str]
    scam_indicators: list[str]
    extracted_entities: list[ExtractedEntity]
    business_intelligence_steps: list[str]


class TakeoverSessionEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    source: str = Field(default="provider", min_length=1, max_length=32)
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)
    text: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[str] = None


class TakeoverSessionEventResponse(BaseModel):
    session_id: str
    accepted: bool
    event_count: int
    connection_state: str
    status_text: str
