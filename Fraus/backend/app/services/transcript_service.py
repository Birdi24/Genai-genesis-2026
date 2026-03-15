import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.schemas.transcript import (
    AnalysisResult,
    SubmitTranscriptRequest,
    SubmitTranscriptResponse,
    TranscriptRecord,
)

logger = logging.getLogger(__name__)

JSON_BACKUP_PATH = Path(__file__).resolve().parents[2] / "data" / "transcripts_backup.json"


class TranscriptService:
    def __init__(self, database: Optional[AsyncIOMotorDatabase]):
        self.database = database
        self.collection = database["transcripts"] if database is not None else None

    async def submit(self, payload: SubmitTranscriptRequest) -> SubmitTranscriptResponse:
        transcript_id = f"tx_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        transcript_text = self._build_transcript_text(payload)

        record = TranscriptRecord(
            transcript_id=transcript_id,
            caller_number=payload.caller_number,
            callee_number=payload.callee_number,
            caller_label=payload.caller_label,
            risk_level=payload.risk_level,
            session_id=payload.session_id,
            transcript_text=transcript_text,
            messages=[m.model_dump() for m in payload.messages],
            submitted_at=now,
            analysis=None,
            analysis_source="pending",
        )

        await self._store(record)

        analysis = await self._forward_to_fraud_engine(
            caller=payload.caller_number,
            callee=payload.callee_number,
            transcript=transcript_text,
        )

        source = "fraud_engine" if analysis else "unavailable"
        record.analysis = analysis
        record.analysis_source = source
        await self._store(record)

        status = "analyzed" if analysis else "stored"
        message = (
            "Transcript analyzed by fraud detection engine."
            if analysis
            else "Transcript stored. Fraud engine unavailable — queued for analysis."
        )

        return SubmitTranscriptResponse(
            transcript_id=transcript_id,
            status=status,
            message=message,
            analysis=analysis,
        )

    async def list_transcripts(self, limit: int = 20) -> list[TranscriptRecord]:
        records: list[TranscriptRecord] = []

        if self.collection is not None:
            try:
                cursor = self.collection.find().sort("submitted_at", -1).limit(limit)
                async for doc in cursor:
                    doc.pop("_id", None)
                    records.append(TranscriptRecord(**doc))
                return records
            except Exception as exc:
                logger.warning("MongoDB read failed, falling back to JSON: %s", exc)

        return self._read_json_backup(limit)

    async def get_latest(self) -> Optional[TranscriptRecord]:
        results = await self.list_transcripts(limit=1)
        return results[0] if results else None

    async def _store(self, record: TranscriptRecord) -> None:
        doc = record.model_dump()

        if self.collection is not None:
            try:
                await self.collection.update_one(
                    {"transcript_id": record.transcript_id},
                    {"$set": doc},
                    upsert=True,
                )
                logger.info("Transcript %s stored in MongoDB", record.transcript_id)
                self._write_json_backup(doc)
                return
            except Exception as exc:
                logger.warning("MongoDB write failed, using JSON backup: %s", exc)

        self._write_json_backup(doc)
        logger.info("Transcript %s stored in JSON backup", record.transcript_id)

    async def _forward_to_fraud_engine(
        self, caller: str, callee: str, transcript: str
    ) -> Optional[AnalysisResult]:
        url = f"{settings.fraud_engine_base_url}/analyze"
        payload = {"caller": caller, "callee": callee, "transcript": transcript}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            return AnalysisResult(
                risk_score=data.get("risk_score", 0),
                is_high_risk=data.get("is_high_risk", False),
                fraud_density=data.get("fraud_density", 0),
                shared_account_score=data.get("shared_account_score", 0),
                persona_score=data.get("persona_score", 0),
                gnn_fraud_prob=data.get("gnn_fraud_prob"),
                extraction=data.get("extraction", {}),
                detail=data.get("detail", ""),
                latency_ms=data.get("latency_ms", 0),
            )
        except Exception as exc:
            logger.warning("Fraud engine at %s unreachable: %s", url, exc)
            return None

    @staticmethod
    def _build_transcript_text(payload: SubmitTranscriptRequest) -> str:
        lines: list[str] = []
        for msg in payload.messages:
            role = "Caller" if msg.speaker == "caller" else "Fraus AI"
            lines.append(f"{role}: {msg.text}")
        return "\n".join(lines)

    @staticmethod
    def _write_json_backup(doc: dict) -> None:
        try:
            JSON_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing: list[dict] = []
            if JSON_BACKUP_PATH.exists():
                with open(JSON_BACKUP_PATH) as f:
                    existing = json.load(f)

            existing = [
                d for d in existing
                if d.get("transcript_id") != doc.get("transcript_id")
            ]
            existing.insert(0, doc)
            existing = existing[:200]

            with open(JSON_BACKUP_PATH, "w") as f:
                json.dump(existing, f, indent=2, default=str)
        except Exception as exc:
            logger.error("JSON backup write failed: %s", exc)

    @staticmethod
    def _read_json_backup(limit: int = 20) -> list[TranscriptRecord]:
        if not JSON_BACKUP_PATH.exists():
            return []
        try:
            with open(JSON_BACKUP_PATH) as f:
                data = json.load(f)
            return [TranscriptRecord(**d) for d in data[:limit]]
        except Exception as exc:
            logger.warning("JSON backup read failed: %s", exc)
            return []
