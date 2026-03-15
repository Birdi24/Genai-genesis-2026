from pydantic import BaseModel, Field
from typing import Optional


class VerifyNumberRequest(BaseModel):
    phone_number: str = Field(..., min_length=3, max_length=32)


class VerifyNumberResponse(BaseModel):
    phoneNumber: str
    status: str
    reason: str
    threatTags: list[str]
    sourceLabel: Optional[str]
    riskLevel: Optional[str]
