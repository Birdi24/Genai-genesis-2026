# Fraus — Real-Time Scam Call Intelligence Platform

Fraus is a full-stack fraud intelligence system that transforms suspicious call transcripts into actionable insights. Rather than relying on static blacklists, Fraus analyzes the content and context of a suspicious call, extracts key entities (phone numbers, bank accounts, scam personas), and maps their relationships into a structured fraud knowledge graph. A composite risk score blends graph-based signals with a GraphSAGE neural network to detect hidden fraud rings and high-risk patterns across calls.

The platform spans three layers: a **SwiftUI iOS app** for consumer-facing call protection, a **FastAPI orchestration backend** for transcript processing and persistence, and a **fraud detection engine** powered by NetworkX and PyTorch Geometric for graph-based risk scoring — all visualized through an interactive **Streamlit dashboard**.

## Architecture

```
┌─────────────────────┐
│   iOS App (SwiftUI)  │
│                     │
│  Verify caller      │    POST /submit-transcript
│  AI takeover ───────│──────────────────────────────┐
│  Live transcript    │                              │
└─────────────────────┘                              ▼
                                          ┌─────────────────────┐
                                          │  Fraus Backend       │
                                          │  (FastAPI :8001)     │
                                          │                     │
                                          │  /verify-number     │
                                          │  /submit-transcript │     POST /analyze
                                          │  /transcripts       │────────────────┐
                                          │  MongoDB + JSON     │                │
                                          └─────────────────────┘                ▼
                                                                      ┌──────────────────────┐
                                                                      │  Fraud Engine        │
┌─────────────────────┐                                               │  (FastAPI :8000)     │
│  Streamlit Dashboard │  GET /graph/data                             │                      │
│  (:8501)            │◀──────────────────────────────────────────────│  LLM Extractor       │
│                     │  GET /graph/stats                             │  NetworkX Graph       │
│  Network graph      │  GET /graph/insights                          │  GraphSAGE GNN       │
│  Fraud insights     │  GET /transcripts/latest                      │  Risk Scorer         │
│  Risk extraction    │                                               └──────────────────────┘
└─────────────────────┘
```

## Components

### iOS App (`Fraus/`)

SwiftUI app with MVVM architecture providing consumer-facing call protection.

| Screen | Purpose |
|--------|---------|
| **Verify Caller** | Enter or paste a phone number for risk assessment |
| **Risk Result** | Displays verification state (Verified / Suspicious / Unknown) with threat tags and confidence |
| **Transfer to AI** | Explicit user consent to hand off a suspicious call to the AI agent |
| **Active Protection** | Live AI conversation with the caller, progressive scam indicator extraction, entity timeline |

**Key behaviors:**
- Simulated AI conversation with a 5-turn script demonstrating bank impersonation detection
- Automatic transcript submission to the backend after each AI session
- Verified number directory — known bank numbers (Chase, Bank of America, Wells Fargo) return verified status and skip AI takeover
- Offline-first with mock verification fallback when the backend is unreachable

### Fraus Backend (`Fraus/backend/`)

FastAPI service that orchestrates transcript processing, persistence, and fraud engine integration.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/verify-number` | POST | Verify a phone number against the fraud engine |
| `/submit-transcript` | POST | Ingest a call transcript, store it, forward to fraud engine for analysis |
| `/transcripts` | GET | List recent transcript records (limit configurable, max 100) |
| `/transcripts/latest` | GET | Retrieve the most recent transcript with analysis |
| `/start-takeover` | POST | Initiate an AI takeover session |
| `/health` | GET | Liveness check |

**Storage:** MongoDB (primary) with automatic JSON file backup fallback. Transcripts are persisted before forwarding to the fraud engine, ensuring no data loss if the engine is unavailable.

### Fraud Detection Engine (`fraud_detection/`)

Dual-model pipeline combining LLM-based entity extraction with graph neural network inference.

**Entity Extraction** — Railtracks-orchestrated LLM flow (GPT-4o-mini) with regex fallback. Extracts phone numbers, bank accounts, scam personas, caller intent, and risk indicators from raw transcript text.

**Fraud Knowledge Graph** — NetworkX directed graph with typed nodes and edges:

| Node Type | Example ID | Shape |
|-----------|------------|-------|
| `phone_number` | `phone_number::+12025551234` | Dot |
| `bank_account` | `bank_account::ACCT-123456` | Square |
| `persona` | `persona::IRS Agent` | Triangle |
| `call_event` | `call::a1b2c3d4` | Star |

| Edge Type | Relationship |
|-----------|-------------|
| `CALLED_FROM` | Phone → Call Event |
| `CALLED_TO` | Call Event → Phone |
| `MENTIONED_ACCOUNT` | Call Event → Bank Account |
| `USED_PERSONA` | Call Event → Persona |
| `OWNS_ACCOUNT` | Phone → Bank Account |

**Risk Scoring** — Composite score blending four signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Fraud neighbor density | 0.60 | k-hop neighborhood in graph |
| Shared account overlap | 0.25 | Bank accounts shared with fraud-flagged phones |
| Persona toxicity | 0.15 | Match against known scam personas (IRS Agent, Tech Support, Bank Officer, etc.) |
| GNN fraud probability | 0.50 | GraphSAGE model prediction |

When GNN output is available: `final = 0.5 * graph_score + 0.5 * gnn_score`. A score above **0.65** flags the caller as high risk.

**GraphSAGE Model** — 2-layer SAGEConv network (PyTorch Geometric) with BatchNorm, ELU activation, and mean aggregation. Inductive: new nodes get embeddings from their neighborhood without retraining.

### Streamlit Dashboard (`Fraus/backend/dashboard/`)

Real-time visualization dashboard with a Tokyo Night theme.

- **Network Graph** — Interactive force-directed graph rendered with `streamlit-agraph`, showing phones, accounts, personas, and call events with fraud-flagged highlighting
- **Meaningful Connections** — Graph statistics, fraud pattern insights, and latest transcript overlay with extracted entity summary
- **Transcript Integration** — Selecting the latest transcript injects synthetic nodes into the graph and highlights extracted entities (caller phone, accounts, persona, risk flags)

## Quick Start

### Prerequisites

- Python 3.9+
- Xcode 15+ (for iOS app)
- MongoDB (optional — JSON backup works without it)

### 1. Fraud Detection Engine

```bash
cd fraud_detection
pip install -r requirements.txt

# Train the GNN on synthetic data
python -m fraud_detection.train

# Start the engine
uvicorn fraud_detection.api.server:app --port 8000 --reload
```

### 2. Fraus Backend

```bash
cd Fraus/backend
pip install -r requirements.txt
pip install streamlit streamlit-agraph

# Start the API server
uvicorn app.main:app --port 8001 --reload
```

### 3. Streamlit Dashboard

```bash
cd Fraus/backend
streamlit run dashboard/app.py --server.port 8501
```

### 4. iOS App

Open `Fraus/Fraus.xcodeproj` in Xcode, select a simulator, and run. The app is configured to use mock verification by default, so it works without a running backend.

### Test a transcript analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "caller": "+12025551234",
    "callee": "+13105559876",
    "transcript": "This is the IRS. Your social security number has been suspended. You need to make an immediate payment with gift cards to avoid arrest."
  }'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM entity extraction | *(regex fallback)* |
| `LLM_MODEL` | Model name for extraction | `gpt-4o-mini` |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `fraus` |
| `FRAUD_ENGINE_BASE_URL` | Fraud engine URL (used by Fraus backend) | `http://127.0.0.1:8000` |

## Project Structure

```
├── fraud_detection/              # Fraud detection engine
│   ├── api/server.py             # FastAPI endpoints (:8000)
│   ├── graph/schema.py           # NetworkX knowledge graph
│   ├── graph/risk_scorer.py      # Composite risk scoring
│   ├── llm/entity_extractor.py   # LLM + regex entity extraction
│   ├── models/sage_model.py      # GraphSAGE (PyTorch Geometric)
│   ├── data/synthetic.py         # Synthetic fraud ring generator
│   ├── config.py                 # Central configuration
│   └── train.py                  # GNN training script
│
├── Fraus/                        # iOS app + backend
│   ├── Fraus/                    # SwiftUI source
│   │   ├── Screens/              # UI screens
│   │   ├── ViewModels/           # MVVM view models
│   │   ├── Services/             # API + mock services
│   │   ├── Models/               # Data models
│   │   ├── Components/           # Reusable UI components
│   │   ├── Theme/                # Design system
│   │   └── Config/               # Runtime configuration
│   ├── FrausTests/               # Unit tests
│   ├── backend/
│   │   ├── app/                  # FastAPI backend (:8001)
│   │   │   ├── routers/          # verification, takeover, transcript
│   │   │   ├── schemas/          # Pydantic models
│   │   │   ├── services/         # Business logic
│   │   │   └── core/             # Configuration
│   │   └── dashboard/app.py      # Streamlit dashboard (:8501)
│   └── Fraus.xcodeproj/          # Xcode project
│
├── app.py                        # Fraud engine Streamlit dashboard
├── seed_db.py                    # Graph seeding script
└── requirements.txt              # Fraud engine dependencies
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| iOS App | SwiftUI, Combine, MVVM |
| Fraus Backend | FastAPI, Motor (MongoDB), httpx, Pydantic |
| Fraud Engine | FastAPI, NetworkX, PyTorch Geometric (GraphSAGE), Railtracks |
| Dashboard | Streamlit, streamlit-agraph |
| Entity Extraction | OpenAI GPT-4o-mini (with regex fallback) |
