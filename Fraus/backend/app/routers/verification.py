from fastapi import APIRouter, HTTPException, status

from app.db.mongo import get_database
from app.schemas.verification import VerifyNumberRequest, VerifyNumberResponse
from app.services.verification_service import VerificationService

router = APIRouter(tags=["verification"])


@router.post("/verify-number", response_model=VerifyNumberResponse)
async def verify_number(payload: VerifyNumberRequest) -> VerifyNumberResponse:
    service = VerificationService(get_database())
    try:
        return await service.verify_number(payload.phone_number)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification service failed",
        ) from error
