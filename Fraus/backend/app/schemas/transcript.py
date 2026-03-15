from pydantic import BaseModel, Field
from typing import Any, Optional


class TranscriptMessage(BaseModel):
    speaker: str = Field(..., description="'caller' or 'frausAI'")
    text: str = Field(..., min_length=1)


class SubmitTranscriptRequest(BaseModel):
    caller_number: str = Field(..., min_length=3, max_length=32)
    callee_number: str = Field(default="unknown", max_length=32)
    caller_label: Optional[str] = None
    risk_level: Optional[str] = None
    session_id: Optional[str] = None
    messages: list[TranscriptMessage] = Field(..., min_length=1)


class AnalysisResult(BaseModel):
    risk_score: float = 0.0
    is_high_risk: bool = False
    fraud_density: float = 0.0
    shared_account_score: float = 0.0
    persona_score: float = 0.0
    gnn_fraud_prob: Optional[float] = None
    extraction: dict[str, Any] = Field(default_factory=dict)
    detail: str = ""
    latency_ms: float = 0.0


class SubmitTranscriptResponse(BaseModel):
    transcript_id: str
    status: str
    message: str
    analysis: Optional[AnalysisResult] = None


class TranscriptRecord(BaseModel):
    transcript_id: str
    caller_number: str
    callee_number: str
    caller_label: Optional[str] = None
    risk_level: Optional[str] = None
    session_id: Optional[str] = None
    transcript_text: str
    messages: list[TranscriptMessage]
    submitted_at: str
    analysis: Optional[AnalysisResult] = None
    analysis_source: str = "pending"
