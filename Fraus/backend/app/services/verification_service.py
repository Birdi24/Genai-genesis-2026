import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.verification import VerifyNumberResponse


class VerificationService:
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database

    def normalize_phone_number(self, phone_number: str) -> str:
        digits = re.sub(r"\D", "", phone_number)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        if digits:
            return f"+{digits}"
        raise ValueError("Phone number is empty or invalid")

    async def verify_number(self, raw_phone_number: str) -> VerifyNumberResponse:
        normalized = self.normalize_phone_number(raw_phone_number)

        verified_doc = await self.database["verified_numbers"].find_one({"phone_number": normalized})
        if verified_doc:
            return VerifyNumberResponse(
                phoneNumber=normalized,
                status="verified",
                reason="matched verified institution number",
                threatTags=["trusted source"],
                sourceLabel=verified_doc.get("label"),
                riskLevel="low",
            )

        scam_doc = await self.database["scam_numbers"].find_one({"phone_number": normalized})
        if scam_doc:
            risk_level = scam_doc.get("risk_level", "critical")
            base_tags = ["reported fraud", "high risk"]
            if scam_doc.get("category"):
                base_tags.append(str(scam_doc["category"]))

            return VerifyNumberResponse(
                phoneNumber=normalized,
                status="scam",
                reason="matched known scam database",
                threatTags=base_tags,
                sourceLabel=scam_doc.get("label") or "Known scam caller",
                riskLevel=str(risk_level),
            )

        return VerifyNumberResponse(
            phoneNumber=normalized,
            status="unknown",
            reason="number not found in trusted or scam database",
            threatTags=["unverified"],
            sourceLabel=None,
            riskLevel="medium",
        )
