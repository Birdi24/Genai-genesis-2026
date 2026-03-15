from fastapi import APIRouter, HTTPException, status

from app.db.mongo import get_database
from app.schemas.takeover import (
    StartTakeoverRequest,
    TakeoverSessionEventRequest,
    TakeoverSessionEventResponse,
    TakeoverSessionResponse,
)
from app.services.takeover_service import TakeoverService

router = APIRouter(tags=["takeover"])


@router.post("/start-takeover", response_model=TakeoverSessionResponse)
async def start_takeover(payload: StartTakeoverRequest) -> TakeoverSessionResponse:
    service = TakeoverService(get_database())
    try:
        return await service.start_takeover(payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Takeover service failed",
        ) from error


@router.get("/session/{session_id}", response_model=TakeoverSessionResponse)
async def get_session(session_id: str) -> TakeoverSessionResponse:
    service = TakeoverService(get_database())
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("/session/{session_id}/events", response_model=TakeoverSessionEventResponse)
async def ingest_session_event(session_id: str, payload: TakeoverSessionEventRequest) -> TakeoverSessionEventResponse:
    service = TakeoverService(get_database())
    event_result = await service.ingest_session_event(session_id=session_id, payload=payload)
    if not event_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return event_result
