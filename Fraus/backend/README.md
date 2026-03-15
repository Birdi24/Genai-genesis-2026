# Fraus Backend (FastAPI + MongoDB)

Fraus is a consumer-facing AI fraud-protection system for suspicious phone calls.

This backend powers the app and demo flow by providing:

- phone number verification
- AI protection / takeover session orchestration (session API contract)
- MongoDB-backed fraud and session data for app and dashboard workflows

## Current Capabilities

- `POST /verify-number` (live)
- `POST /start-takeover` (session API contract for app integration; implementation layer in progress)
- `GET /session/{id}` (session API contract for app integration; implementation layer in progress)
- `GET /health`

Verification is fully live today. Takeover is designed as a backend-session flow that connects to ElevenLabs (voice agent layer) and Railtracks (orchestration/analysis layer).

## Project Structure

Current repository structure:

```
backend/
  app/
    core/
      config.py
    db/
      mongo.py
    routers/
      verification.py
    schemas/
      verification.py
    services/
      verification_service.py
    main.py
  scripts/
    seed_demo_data.py
  tests/
    test_verify_number.py
  requirements.txt
```

Planned takeover modules (next backend iteration):

```
app/
  routers/
    takeover.py
  schemas/
    takeover.py
  services/
    takeover_service.py
```

## Data Model / Collections

- `verified_numbers`: trusted institution/customer-support numbers used to return `verified` results.
- `scam_numbers`: known fraudulent or high-risk numbers used to return `scam` results and risk labels.
- `takeover_sessions`: takeover session records (session metadata, transcripts, indicators, extracted entities, and handoff states) used by `POST /start-takeover` and `GET /session/{id}`.

## Environment Variables

Implemented today:

- `MONGODB_URI` (default: `mongodb://localhost:27017`)
- `MONGODB_DB_NAME` (default: `fraus`)

Future integration placeholders (for takeover/agent orchestration wiring):

- `ELEVENLABS_API_KEY` (placeholder)
- `RAILTRACKS_API_KEY` (placeholder)
- `TAKEOVER_DEFAULT_AGENT` (placeholder)

These placeholder vars document expected integration direction; they are not required for current verification-only execution.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Seed Demo Data

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python -m scripts.seed_demo_data
```

## Run API

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### `POST /verify-number` (live)

Request:

```json
{
  "phone_number": "+1 (900) 555-0199"
}
```

Example response:

```json
{
  "phoneNumber": "+19005550199",
  "status": "scam",
  "reason": "matched known scam database",
  "threatTags": ["reported fraud", "high risk", "bank impersonation"],
  "sourceLabel": "Known scam caller",
  "riskLevel": "critical"
}
```

### `POST /start-takeover` (session API contract)

Request:

```json
{
  "phone_number": "+1 (900) 555-0199",
  "caller_label": "Possible Bank Impersonation",
  "risk_level": "high"
}
```

Response:

```json
{
  "session_id": "sess_01JX9YJH2N8Q6W0A3M5B7C9D"
}
```

### `GET /session/{id}` (session API contract)

Response:

```json
{
  "session_id": "sess_01JX9YJH2N8Q6W0A3M5B7C9D",
  "phone_number": "+19005550199",
  "status_text": "AI actively containing caller",
  "ai_agent_name": "Fraus Sentinel v1",
  "started_at": "2026-03-14T17:20:00Z",
  "transcript_notes": [
    "Caller claims to be from customer bank security.",
    "Caller asks for one-time password and card verification code."
  ],
  "scam_indicators": [
    "Bank impersonation script",
    "OTP extraction attempt"
  ],
  "extracted_entities": [
    {
      "key": "Requested OTP",
      "value": "6-digit SMS code",
      "confidence": 95
    }
  ],
  "business_intelligence_steps": [
    "Transcript captured",
    "Entities extracted",
    "Fraud analysis queued",
    "Fraud graph update pending"
  ]
}
```

### `GET /health`

Response:

```json
{
  "status": "ok"
}
```

## iOS Takeover Integration Notes

- API payloads use `snake_case` JSON.
- iOS models map these payloads to `camelCase` Swift types.
- The app is backend-first for takeover sessions, with mock fallback when backend is unavailable.
- Takeover sessions are intended to be persisted in MongoDB (`takeover_sessions`).
- ElevenLabs is the intended backend voice-agent layer behind takeover endpoints.
- Railtracks is the intended backend orchestration/analysis/fraud-intelligence layer behind takeover endpoints.

Field mapping (API key → iOS field):

- `session_id` → `sessionId`
- `phone_number` → `phoneNumber`
- `status_text` → `status`
- `ai_agent_name` → `aiAgentName`
- `started_at` → `startedAt`
- `transcript_notes` → `transcriptLines`
- `scam_indicators` → `detectedIndicators`
- `extracted_entities` → `extractedEntities`
- `business_intelligence_steps` → `handoffStatuses`

## Architecture Notes

- SwiftUI app does not connect directly to MongoDB.
- Data flow is: `SwiftUI app -> FastAPI -> MongoDB`.
- Business dashboard / GNN pipeline should read MongoDB as source of truth.
- ElevenLabs belongs in backend takeover execution.
- Railtracks belongs in orchestration, analysis, and fraud-intelligence processing.

## Tests

Current automated tests focus on verification behavior.

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python -m unittest tests.test_verify_number -v
```
