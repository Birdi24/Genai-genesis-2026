import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.db.mongo import close_mongo, connect_mongo, get_database
from app.integrations.elevenlabs_client import ElevenLabsStartResult
from app.main import app


class TakeoverApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await connect_mongo()
        self.db = get_database()
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://test")
        await self.db["takeover_sessions"].delete_many({})

    async def asyncTearDown(self) -> None:
        await self.db["takeover_sessions"].delete_many({})
        await self.client.aclose()
        await close_mongo()

    async def test_start_takeover_persists_session_when_elevenlabs_unavailable(self) -> None:
        with patch(
            "app.services.takeover_service.ElevenLabsClient.start_conversation",
            new=AsyncMock(
                return_value=ElevenLabsStartResult(
                    provider_name="elevenlabs",
                    provider_status="degraded_unavailable",
                    elevenlabs_agent_id="agent_test",
                    elevenlabs_conversation_id=None,
                    error="provider down",
                )
            ),
        ):
            response = await self.client.post(
                "/start-takeover",
                json={
                    "phone_number": "+1 (900) 555-0199",
                    "caller_label": "Possible Bank Impersonation",
                    "risk_level": "high",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["session_id"].startswith("fraus_"))
        self.assertEqual(body["phone_number"], "+19005550199")
        self.assertIn("fallback mode", body["status_text"].lower())
        self.assertEqual(body["connection_state"], "degraded")
        self.assertIsNone(body["conversation_signed_url"])
        self.assertIn("scam_indicators", body)
        self.assertIn("extracted_entities", body)

        session_doc = await self.db["takeover_sessions"].find_one({"session_id": body["session_id"]})
        self.assertIsNotNone(session_doc)
        self.assertEqual(session_doc["session_status"], "active")
        self.assertEqual(session_doc["provider_metadata"]["provider_status"], "degraded_unavailable")
        self.assertEqual(session_doc["provider_metadata"]["provider_name"], "elevenlabs")
        self.assertIn("analysis_metadata", session_doc)
        self.assertIn("tags", session_doc["analysis_metadata"])

    async def test_start_takeover_persists_provider_metadata_on_success(self) -> None:
        with patch(
            "app.services.takeover_service.ElevenLabsClient.start_conversation",
            new=AsyncMock(
                return_value=ElevenLabsStartResult(
                    provider_name="elevenlabs",
                    provider_status="active",
                    elevenlabs_agent_id="agent_live",
                    elevenlabs_conversation_id="conv_123",
                    signed_url="wss://api.elevenlabs.io/convai/conversation?token=signed",
                    error=None,
                )
            ),
        ):
            response = await self.client.post(
                "/start-takeover",
                json={
                    "phone_number": "3125558877",
                    "caller_label": "Possible IRS Scam",
                    "risk_level": "high",
                },
            )

        self.assertEqual(response.status_code, 200)
        session_id = response.json()["session_id"]

        session_doc = await self.db["takeover_sessions"].find_one({"session_id": session_id})
        self.assertIsNotNone(session_doc)
        self.assertEqual(session_doc["provider_metadata"]["provider_status"], "active")
        self.assertEqual(session_doc["provider_metadata"]["elevenlabs_agent_id"], "agent_live")
        self.assertEqual(session_doc["provider_metadata"]["elevenlabs_conversation_id"], "conv_123")
        self.assertEqual(
            session_doc["provider_metadata"]["conversation_signed_url"],
            "wss://api.elevenlabs.io/convai/conversation?token=signed",
        )
        self.assertEqual(session_doc["connection_state"], "live")

    async def test_get_session_returns_snake_case_contract(self) -> None:
        with patch(
            "app.services.takeover_service.ElevenLabsClient.start_conversation",
            new=AsyncMock(
                return_value=ElevenLabsStartResult(
                    provider_name="elevenlabs",
                    provider_status="partial",
                    elevenlabs_agent_id="agent_live",
                    elevenlabs_conversation_id=None,
                    error=None,
                )
            ),
        ):
            start_response = await self.client.post(
                "/start-takeover",
                json={
                    "phone_number": "+1 (900) 555-0199",
                    "caller_label": "Possible Bank Impersonation",
                    "risk_level": "high",
                },
            )
        self.assertEqual(start_response.status_code, 200)
        session_id = start_response.json()["session_id"]

        get_response = await self.client.get(f"/session/{session_id}")
        self.assertEqual(get_response.status_code, 200)
        body = get_response.json()

        expected_keys = {
            "session_id",
            "phone_number",
            "status_text",
            "connection_state",
            "conversation_signed_url",
            "ai_agent_name",
            "started_at",
            "transcript_notes",
            "scam_indicators",
            "extracted_entities",
            "business_intelligence_steps",
        }
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertEqual(body["session_id"], session_id)

    async def test_session_event_ingestion_persists_events_and_updates_analysis(self) -> None:
        with patch(
            "app.services.takeover_service.ElevenLabsClient.start_conversation",
            new=AsyncMock(
                return_value=ElevenLabsStartResult(
                    provider_name="elevenlabs",
                    provider_status="prepared_signed_url",
                    elevenlabs_agent_id="agent_live",
                    elevenlabs_conversation_id="conv_live",
                    signed_url="wss://api.elevenlabs.io/convai/conversation?token=signed",
                    error=None,
                )
            ),
        ):
            start_response = await self.client.post(
                "/start-takeover",
                json={
                    "phone_number": "+1 (312) 555-1234",
                    "caller_label": "Possible Bank Scam",
                    "risk_level": "high",
                },
            )

        self.assertEqual(start_response.status_code, 200)
        session_id = start_response.json()["session_id"]

        ingest_response = await self.client.post(
            f"/session/{session_id}/events",
            json={
                "event_type": "transcript",
                "source": "ios_client",
                "role": "user",
                "text": "I need you to share your OTP code immediately",
                "metadata": {"sequence": 1},
            },
        )

        self.assertEqual(ingest_response.status_code, 200)
        ingest_body = ingest_response.json()
        self.assertEqual(ingest_body["session_id"], session_id)
        self.assertTrue(ingest_body["accepted"])
        self.assertEqual(ingest_body["event_count"], 1)
        self.assertEqual(ingest_body["connection_state"], "live")

        session_doc = await self.db["takeover_sessions"].find_one({"session_id": session_id})
        self.assertIsNotNone(session_doc)
        self.assertEqual(len(session_doc.get("conversation_events", [])), 1)
        self.assertEqual(session_doc["conversation_events"][0]["type"], "transcript")
        self.assertIn("analysis_metadata", session_doc)
        self.assertEqual(session_doc["analysis_metadata"].get("event_count"), 1)
        self.assertEqual(session_doc.get("connection_state"), "live")


if __name__ == "__main__":
    unittest.main()
