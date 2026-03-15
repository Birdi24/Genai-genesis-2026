"""
FastAPI orchestration layer for real-time fraud detection.

Endpoints
---------
POST /analyze    — Analyze a call transcript end-to-end.
POST /ingest     — Ingest a raw call event into the graph.
GET  /risk/{phone} — Get the risk report for a phone number.
GET  /graph/stats  — Summary statistics of the knowledge graph.
GET  /health       — Liveness probe.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fraud_detection.config import AppConfig
from fraud_detection.data.synthetic import generate_fraud_ring_dataset, _graph_to_pyg
from fraud_detection.graph.schema import FraudGraph, NodeType, _prefixed, DEFAULT_GRAPH_STORE
from fraud_detection.graph.risk_scorer import RiskScorer
from fraud_detection.llm.entity_extractor import EntityExtractor, ExtractionResult
from fraud_detection.models.sage_model import FraudSAGE, train_one_epoch, evaluate

logger = logging.getLogger(__name__)

# ── Global state (initialised in lifespan) ────────────────────────────

_state: dict = {}


def _get(key: str):
    return _state[key]


# ── Lifespan: build graph, train GNN on synthetic data ────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = AppConfig()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # Always generate synthetic data for GNN training baseline
    logger.info("Generating synthetic fraud-ring dataset…")
    dataset = generate_fraud_ring_dataset()
    fg: FraudGraph = dataset["graph"]
    fg._store_path = DEFAULT_GRAPH_STORE
    pyg = dataset["pyg_data"]

    # Merge any previously persisted user-submitted data on top
    persisted = FraudGraph.load(DEFAULT_GRAPH_STORE)
    if persisted.graph.number_of_nodes() > 0:
        import networkx as nx
        fg._g = nx.compose(fg._g, persisted.graph)
        logger.info("Merged persisted graph data — total: %d nodes, %d edges",
                     fg.graph.number_of_nodes(), fg.graph.number_of_edges())

    logger.info("Training GraphSAGE on synthetic data…")
    model = FraudSAGE(
        in_channels=cfg.gnn.input_dim,
        hidden_channels=cfg.gnn.hidden_dim,
        out_channels=cfg.gnn.output_dim,
        num_layers=cfg.gnn.num_layers,
        dropout=cfg.gnn.dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.gnn.learning_rate)

    for epoch in range(1, cfg.gnn.epochs + 1):
        loss = train_one_epoch(model, optimizer, pyg.x, pyg.edge_index, pyg.y, pyg.train_mask)
        if epoch % 50 == 0:
            metrics = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.val_mask)
            logger.info("Epoch %3d  loss=%.4f  val_acc=%.3f", epoch, loss, metrics["accuracy"])

    test_metrics = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.test_mask)
    logger.info("Test accuracy: %.3f", test_metrics["accuracy"])

    scorer = RiskScorer(fg, cfg.graph)

    # ── Railtracks initialisation ─────────────────────────────────────
    import railtracks as rt
    if cfg.railtracks.enable_rt_logging:
        rt.enable_logging(level=cfg.log_level)
    rt.set_config(
        save_state=cfg.railtracks.save_state,
        timeout=cfg.railtracks.flow_timeout,
        end_on_error=False,
    )
    extractor = EntityExtractor(cfg.llm, cfg.railtracks)
    rt_mode = "railtracks_llm" if cfg.llm.api_key else "regex_fallback"
    logger.info("EntityExtractor initialised — mode=%s  save_state=%s",
                rt_mode, cfg.railtracks.save_state)

    _state.update(
        cfg=cfg, fg=fg, pyg=pyg, model=model,
        scorer=scorer, extractor=extractor,
    )

    logger.info("Fraud detection engine ready.  Graph: %s", fg.summary())
    yield
    _state.clear()


app = FastAPI(
    title="Fraud Detection Engine",
    version="0.1.0",
    description="Dual-model fraud detection: LLM intent analysis + GraphSAGE fraud rings.",
    lifespan=lifespan,
)


# ── Request / Response models ─────────────────────────────────────────

class TranscriptRequest(BaseModel):
    caller: str = Field(..., description="Caller phone number")
    callee: str = Field(..., description="Callee phone number")
    transcript: str = Field(..., description="Raw call transcript text")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "caller": "+12025551234",
                    "callee": "+13105559876",
                    "transcript": "Hello this is Agent Smith from the IRS. We found irregularities in your tax return. Your social security number has been compromised. You will be arrested unless you make an immediate payment. Please send 5000 dollars in gift cards to account ACCT-998877. Do not tell anyone about this call. You can also wire transfer to account ACCT-112233. Act now or a warrant will be issued. Call us back at 202-555-0199.",
                }
            ]
        }
    }


class IngestRequest(BaseModel):
    caller: str
    callee: str
    persona: str | None = None
    accounts: list[str] = []
    transcript_snippet: str = ""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "caller": "+19175550001",
                    "callee": "+18005550000",
                    "persona": "Tech Support",
                    "accounts": ["ACCT-554433"],
                    "transcript_snippet": "Your computer has been infected with a virus. We need remote access to fix it.",
                }
            ]
        }
    }


class AnalysisResponse(BaseModel):
    caller: str
    extraction: dict
    risk_score: float
    is_high_risk: bool
    fraud_density: float
    shared_account_score: float
    persona_score: float
    gnn_fraud_prob: float | None
    detail: str
    latency_ms: float
    # Railtracks observability fields
    extraction_source: str
    coercion_detected: bool
    hallucination_flags: list[str]
    rt_session_id: str | None
    rt_latency_ms: float | None


class RiskResponse(BaseModel):
    phone: str
    composite_score: float
    is_high_risk: bool
    fraud_density: float
    shared_account_score: float
    persona_score: float
    gnn_fraud_prob: float | None
    detail: str


# ── Helpers ───────────────────────────────────────────────────────────

def _gnn_predict_phone(phone: str) -> float | None:
    """Get GNN fraud probability for a phone node. Returns None if node absent."""
    fg: FraudGraph = _get("fg")
    model: FraudSAGE = _get("model")
    pyg = _get("pyg")

    nid = _prefixed(NodeType.PHONE, phone)
    if nid not in fg.graph:
        return None

    node_ids = list(pyg.node_ids) if hasattr(pyg, "node_ids") else list(fg.graph.nodes())
    if nid not in node_ids:
        return None

    idx = node_ids.index(nid)
    probs = model.predict_proba(pyg.x, pyg.edge_index)
    return round(probs[idx, 1].item(), 4)


def _rebuild_pyg() -> None:
    """Rebuild PyG data from the current graph state (for fresh GNN inference)."""
    fg: FraudGraph = _get("fg")
    _state["pyg"] = _graph_to_pyg(fg)


# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_transcript(req: TranscriptRequest):
    """Full pipeline: extract entities -> ingest -> score -> respond."""
    t0 = time.perf_counter()

    extractor: EntityExtractor = _get("extractor")
    fg: FraudGraph = _get("fg")
    scorer: RiskScorer = _get("scorer")

    extraction: ExtractionResult = await extractor.extract(
        req.transcript, caller=req.caller, callee=req.callee
    )

    fg.add_call_event(
        caller=req.caller,
        callee=req.callee,
        persona=extraction.persona,
        accounts=extraction.bank_accounts,
        transcript_snippet=req.transcript[:200],
    )
    fg.save()

    _rebuild_pyg()
    gnn_prob = _gnn_predict_phone(req.caller)

    report = scorer.score_phone(req.caller, gnn_fraud_prob=gnn_prob)

    latency = (time.perf_counter() - t0) * 1000
    logger.info("Analyzed call from %s in %.1fms — risk=%.3f", req.caller, latency, report.composite_score)

    return AnalysisResponse(
        caller=req.caller,
        extraction={
            "phone_numbers": extraction.phone_numbers,
            "bank_accounts": extraction.bank_accounts,
            "persona": extraction.persona,
            "intent": extraction.intent,
            "risk_indicators": extraction.risk_indicators,
            "source": extraction.source,
        },
        risk_score=report.composite_score,
        is_high_risk=report.is_high_risk,
        fraud_density=report.fraud_density,
        shared_account_score=report.shared_account_score,
        persona_score=report.persona_score,
        gnn_fraud_prob=report.gnn_fraud_prob,
        detail=report.detail,
        latency_ms=round(latency, 1),
        extraction_source=extraction.source,
        coercion_detected=extraction.coercion_detected,
        hallucination_flags=extraction.hallucination_flags,
        rt_session_id=extraction.rt_session_id,
        rt_latency_ms=extraction.rt_latency_ms,
    )


@app.post("/ingest")
async def ingest_call(req: IngestRequest):
    """Manually ingest a call event into the graph."""
    fg: FraudGraph = _get("fg")
    call_id = fg.add_call_event(
        caller=req.caller,
        callee=req.callee,
        persona=req.persona,
        accounts=req.accounts,
        transcript_snippet=req.transcript_snippet,
    )
    fg.save()
    _rebuild_pyg()
    return {"status": "ok", "call_id": call_id, "graph_summary": fg.summary()}


@app.get("/risk/{phone}", response_model=RiskResponse)
async def get_risk(phone: str):
    """Return the risk report for a given phone number."""
    scorer: RiskScorer = _get("scorer")
    gnn_prob = _gnn_predict_phone(phone)
    report = scorer.score_phone(phone, gnn_fraud_prob=gnn_prob)

    if report.detail == "Node not found in graph.":
        raise HTTPException(status_code=404, detail=f"Phone {phone} not found in graph.")

    return RiskResponse(
        phone=phone,
        composite_score=report.composite_score,
        is_high_risk=report.is_high_risk,
        fraud_density=report.fraud_density,
        shared_account_score=report.shared_account_score,
        persona_score=report.persona_score,
        gnn_fraud_prob=report.gnn_fraud_prob,
        detail=report.detail,
    )


@app.get("/graph/stats")
async def graph_stats():
    fg: FraudGraph = _get("fg")
    return fg.summary()


@app.get("/graph/insights")
async def graph_insights():
    """Detect fraud-indicative patterns and return human-readable insights."""
    fg: FraudGraph = _get("fg")
    return fg.detect_insights()


@app.get("/graph/data")
async def graph_data(max_phones: int = 40):
    """Return the heterogeneous graph for frontend visualization.

    Strategy: include ALL personas and accounts (there are few), then
    fill up to *max_phones* phone nodes.  Call-event nodes are
    collapsed — the server resolves them into direct edges between
    phones, accounts and personas so the frontend never needs to
    render the tiny hub nodes.
    """
    fg: FraudGraph = _get("fg")
    g = fg.graph

    personas  = [(n, d) for n, d in g.nodes(data=True) if d.get("ntype") == NodeType.PERSONA.value]
    accounts  = [(n, d) for n, d in g.nodes(data=True) if d.get("ntype") == NodeType.ACCOUNT.value]
    phones    = [(n, d) for n, d in g.nodes(data=True) if d.get("ntype") == NodeType.PHONE.value]
    call_nodes = {n for n, d in g.nodes(data=True) if d.get("ntype") == NodeType.CALL.value}

    phones = phones[:max_phones]
    visible = {n for n, _ in personas + accounts + phones}

    nodes = []
    for nid, data in personas + accounts + phones:
        nodes.append({
            "id": nid,
            "label": data.get("raw", nid.split("::")[-1])[:20],
            "ntype": data.get("ntype", "unknown"),
            "fraud_label": data.get("label", "unknown"),
        })

    # Collapse call-event hubs into direct edges.
    # For every call node, connect its predecessors to its successors
    # so we get phone→account, phone→persona, phone→phone edges.
    edges_set: set[tuple[str, str, str]] = set()
    for cn in call_nodes:
        preds = [p for p in g.predecessors(cn) if p in visible]
        succs = [s for s in g.successors(cn) if s in visible]
        for p in preds:
            for s in succs:
                if p != s:
                    edge_data = g.get_edge_data(cn, s) or {}
                    etype = edge_data.get("etype", "RELATED")
                    edges_set.add((p, s, etype))

    # Also include direct edges (OWNS_ACCOUNT, etc.) that don't go through call nodes
    for u, v, data in g.edges(data=True):
        if u in visible and v in visible and u not in call_nodes and v not in call_nodes:
            edges_set.add((u, v, data.get("etype", "RELATED")))

    edges = [{"source": u, "target": v, "etype": e} for u, v, e in edges_set]

    return {"nodes": nodes, "edges": edges, "summary": fg.summary()}


@app.get("/health")
async def health():
    return {"status": "ok", "graph_loaded": "fg" in _state}
