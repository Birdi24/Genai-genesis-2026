from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings


async def seed() -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    now = datetime.now(timezone.utc)

    verified_numbers = [
        {
            "phone_number": "+18001234567",
            "label": "Official Bank Line",
            "category": "bank",
            "verified": True,
            "last_updated": now,
        },
        {
            "phone_number": "+14085550111",
            "label": "Insurance Helpdesk",
            "category": "insurance",
            "verified": True,
            "last_updated": now,
        },
    ]

    scam_numbers = [
        {
            "phone_number": "+19005550199",
            "label": "Known scam caller",
            "category": "bank impersonation",
            "risk_level": "critical",
            "reports": 182,
            "last_updated": now,
        },
        {
            "phone_number": "+13125558877",
            "label": "Potential phishing line",
            "category": "credential theft",
            "risk_level": "high",
            "reports": 46,
            "last_updated": now,
        },
    ]

    for document in verified_numbers:
        await db["verified_numbers"].update_one(
            {"phone_number": document["phone_number"]},
            {"$set": document},
            upsert=True,
        )

    for document in scam_numbers:
        await db["scam_numbers"].update_one(
            {"phone_number": document["phone_number"]},
            {"$set": document},
            upsert=True,
        )

    client.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())
