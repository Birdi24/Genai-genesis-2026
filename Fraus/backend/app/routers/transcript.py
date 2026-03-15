import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.schemas.transcript import (
    SubmitTranscriptRequest,
    SubmitTranscriptResponse,
    TranscriptRecord,
)
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["transcript"])


def _get_service() -> TranscriptService:
    try:
        from app.db.mongo import get_database
        db = get_database()
    except RuntimeError:
        logger.warning("MongoDB unavailable — transcript service running with JSON backup only")
        db = None
    return TranscriptService(db)


@router.post("/submit-transcript", response_model=SubmitTranscriptResponse)
async def submit_transcript(payload: SubmitTranscriptRequest) -> SubmitTranscriptResponse:
    service = _get_service()
    try:
        return await service.submit(payload)
    except Exception as exc:
        logger.exception("Transcript submission failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcript submission failed",
        ) from exc


@router.get("/transcripts", response_model=list[TranscriptRecord])
async def list_transcripts(limit: int = 20) -> list[TranscriptRecord]:
    service = _get_service()
    return await service.list_transcripts(limit=min(limit, 100))


@router.get("/transcripts/latest", response_model=Optional[TranscriptRecord])
async def get_latest_transcript() -> Optional[TranscriptRecord]:
    service = _get_service()
    return await service.get_latest()
