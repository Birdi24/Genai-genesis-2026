# Fraud Detection Engine — Dual-Model Architecture

Real-time scam detection system combining **LLM-based intent analysis** with a **GraphSAGE neural network** for fraud ring identification.

## Architecture

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────────┐
│  Call Stream  │────▶│   FastAPI Server    │────▶│   Risk Report    │
└──────────────┘     │                    │     └──────────────────┘
                     │  ┌──────────────┐  │
                     │  │  Railtracks  │  │  Entity extraction
                     │  └──────┬───────┘  │  (phone, account, persona)
                     │         ▼          │
                     │  ┌──────────────┐  │
                     │  │ Fraud Graph  │  │  NetworkX knowledge graph
                     │  │  (NetworkX)  │  │
                     │  └──────┬───────┘  │
                     │         ▼          │
                     │  ┌──────────────┐  │
                     │  │  GraphSAGE   │  │  PyTorch Geometric GNN
                     │  │   (PyG)      │  │
                     │  └──────┬───────┘  │
                     │         ▼          │
                     │  ┌──────────────┐  │
                     │  │ Risk Scorer  │  │  Composite scoring
                     │  └──────────────┘  │
                     └────────────────────┘
```

## Graph Schema

| Node Type     | Properties                  | Example ID                          |
|---------------|-----------------------------|-------------------------------------|
| phone_number  | raw, label, created_at      | `phone_number::+12025551234`        |
| bank_account  | raw, label, created_at      | `bank_account::ACCT-123456`         |
| persona       | raw, label, created_at      | `persona::IRS Agent`                |
| call_event    | transcript, label, created_at | `call::a1b2c3d4e5f6`              |

| Edge Type          | From → To                    |
|--------------------|------------------------------|
| CALLED_FROM        | phone_number → call_event    |
| CALLED_TO          | call_event → phone_number    |
| MENTIONED_ACCOUNT  | call_event → bank_account    |
| USED_PERSONA       | call_event → persona         |
| OWNS_ACCOUNT       | phone_number → bank_account  |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Train the GNN on synthetic data
python -m fraud_detection.train

# Start the API server
uvicorn fraud_detection.api.server:app --reload

# Analyze a transcript
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "caller": "+12025551234",
    "callee": "+13105559876",
    "transcript": "This is the IRS. Your social security number has been suspended. You need to make an immediate payment with gift cards to avoid arrest."
  }'
```

## API Endpoints

| Method | Path              | Description                               |
|--------|-------------------|-------------------------------------------|
| POST   | `/analyze`        | Full pipeline: extract → ingest → score   |
| POST   | `/ingest`         | Manually ingest a call event              |
| GET    | `/risk/{phone}`   | Risk report for a phone number            |
| GET    | `/graph/stats`    | Knowledge graph summary                   |
| GET    | `/health`         | Liveness check                            |

## Risk Scoring

The composite risk score blends four signals:

| Signal               | Weight | Source                          |
|----------------------|--------|---------------------------------|
| Fraud neighbor density | 0.60 | k-hop neighborhood in graph     |
| Shared account overlap | 0.25 | Bank accounts shared with fraud |
| Persona toxicity       | 0.15 | Match against known scam types  |
| GNN fraud probability  | 0.50 | GraphSAGE model prediction      |

When GNN probability is available, the final score is `0.5 * graph_score + 0.5 * gnn_score`.

## Project Structure

```
fraud_detection/
├── api/
│   └── server.py           # FastAPI orchestration
├── data/
│   └── synthetic.py        # Synthetic fraud ring generator
├── graph/
│   ├── schema.py           # NetworkX graph with typed nodes/edges
│   └── risk_scorer.py      # Composite risk scoring engine
├── llm/
│   └── entity_extractor.py # LLM + regex entity extraction
├── models/
│   └── sage_model.py       # GraphSAGE (PyTorch Geometric)
├── config.py               # Central configuration
└── train.py                # Standalone training script
```

## Environment Variables

| Variable        | Description                     | Default       |
|-----------------|---------------------------------|---------------|
| `OPENAI_API_KEY` | OpenAI API key for LLM extraction | (regex fallback) |
| `LLM_MODEL`     | Model name for entity extraction | `gpt-4o-mini` |

## Neo4j Migration

The graph schema includes a `to_cypher_statements()` method that exports
all nodes and edges as Cypher `CREATE` / `MATCH` statements for direct
import into Neo4j.
