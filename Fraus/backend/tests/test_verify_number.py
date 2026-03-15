import unittest

from app.db.mongo import close_mongo, connect_mongo, get_database
from app.services.verification_service import VerificationService


class VerifyNumberIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await connect_mongo()
        self.db = get_database()
        self.service = VerificationService(self.db)

        self.verified_number = "+18001234567"
        self.scam_number = "+19005550199"

        await self.db["verified_numbers"].update_one(
            {"phone_number": self.verified_number},
            {
                "$set": {
                    "phone_number": self.verified_number,
                    "label": "Official Bank Line",
                    "category": "bank",
                    "verified": True,
                }
            },
            upsert=True,
        )

        await self.db["scam_numbers"].update_one(
            {"phone_number": self.scam_number},
            {
                "$set": {
                    "phone_number": self.scam_number,
                    "label": "Known scam caller",
                    "category": "bank impersonation",
                    "risk_level": "critical",
                    "reports": 182,
                }
            },
            upsert=True,
        )

    async def asyncTearDown(self) -> None:
        await self.db["verified_numbers"].delete_one({"phone_number": self.verified_number})
        await self.db["scam_numbers"].delete_one({"phone_number": self.scam_number})
        await close_mongo()

    async def test_verified_number_returns_verified_status(self) -> None:
        result = await self.service.verify_number("+1 (800) 123-4567")

        self.assertEqual(result.phoneNumber, self.verified_number)
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.riskLevel, "low")
        self.assertEqual(result.sourceLabel, "Official Bank Line")

    async def test_scam_number_returns_scam_status(self) -> None:
        result = await self.service.verify_number("+1 (900) 555-0199")

        self.assertEqual(result.phoneNumber, self.scam_number)
        self.assertEqual(result.status, "scam")
        self.assertEqual(result.riskLevel, "critical")
        self.assertIn("reported fraud", result.threatTags)

    async def test_unknown_number_returns_unknown_status(self) -> None:
        result = await self.service.verify_number("+1 (312) 000-0000")

        self.assertEqual(result.phoneNumber, "+13120000000")
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.riskLevel, "medium")
        self.assertEqual(result.threatTags, ["unverified"])


if __name__ == "__main__":
    unittest.main()
