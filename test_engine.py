"""
End-to-end integration test for the fraud detection engine.
Validates all components without needing a running server.
"""

import asyncio
import time
import torch

from fraud_detection.config import AppConfig
from fraud_detection.data.synthetic import generate_fraud_ring_dataset, _graph_to_pyg
from fraud_detection.graph.schema import FraudGraph, NodeType
from fraud_detection.graph.risk_scorer import RiskScorer
from fraud_detection.llm.entity_extractor import EntityExtractor
from fraud_detection.models.sage_model import FraudSAGE, train_one_epoch, evaluate


def test_synthetic_data():
    print("=" * 60)
    print("TEST 1: Synthetic Fraud Ring Generation")
    print("=" * 60)
    dataset = generate_fraud_ring_dataset()
    fg = dataset["graph"]
    pyg = dataset["pyg_data"]
    stats = dataset["stats"]

    print(f"  Nodes  : {fg.graph.number_of_nodes()}")
    print(f"  Edges  : {fg.graph.number_of_edges()}")
    print(f"  Phones : {stats['phone_number']}  (fraud={stats['n_fraud_phones']}, benign={stats['n_benign_phones']})")
    print(f"  Accounts: {stats['bank_account']}")
    print(f"  Personas: {stats.get('persona', 'N/A')}")
    print(f"  Calls  : {stats['call_event']}")
    print(f"  Rings  : {stats['n_fraud_rings']}")
    print(f"  PyG shape: x={list(pyg.x.shape)}, edges={list(pyg.edge_index.shape)}, y={list(pyg.y.shape)}")
    print(f"  Labels : fraud={int((pyg.y == 1).sum())}, benign={int((pyg.y == 0).sum())}")
    print("  PASSED\n")
    return dataset


def test_gnn_training(pyg):
    print("=" * 60)
    print("TEST 2: GraphSAGE Training & Evaluation")
    print("=" * 60)
    cfg = AppConfig().gnn

    model = FraudSAGE(
        in_channels=pyg.x.size(1),
        hidden_channels=cfg.hidden_dim,
        out_channels=cfg.output_dim,
        num_layers=cfg.num_layers,
        dropout=cfg.dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.learning_rate)

    t0 = time.perf_counter()
    for epoch in range(1, 201):
        loss = train_one_epoch(model, optimizer, pyg.x, pyg.edge_index, pyg.y, pyg.train_mask)
        if epoch % 50 == 0:
            val = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.val_mask)
            print(f"  Epoch {epoch:3d}  loss={loss:.4f}  val_acc={val['accuracy']:.3f}")
    elapsed = time.perf_counter() - t0

    test = evaluate(model, pyg.x, pyg.edge_index, pyg.y, pyg.test_mask)
    print(f"  Test accuracy: {test['accuracy']:.3f}  (trained in {elapsed:.2f}s)")
    assert test["accuracy"] >= 0.85, f"Test accuracy too low: {test['accuracy']}"
    print("  PASSED\n")
    return model


def test_entity_extraction():
    print("=" * 60)
    print("TEST 3: Entity Extraction (regex fallback)")
    print("=" * 60)
    extractor = EntityExtractor()

    scam_transcript = (
        "Hello, this is Agent Smith from the IRS. We have found irregularities "
        "in your tax return. Your social security number has been compromised. "
        "You will be arrested unless you make an immediate payment. Please send "
        "$5,000 in gift cards to account ACCT-998877. Do not tell anyone about "
        "this call. Wire transfer to account ACCT-112233. Call 202-555-0199."
    )

    result = asyncio.run(extractor.extract(scam_transcript))
    print(f"  Source    : {result.source}")
    print(f"  Phones   : {result.phone_numbers}")
    print(f"  Accounts : {result.bank_accounts}")
    print(f"  Persona  : {result.persona}")
    print(f"  Intent   : {result.intent}")
    print(f"  Risk flags: {result.risk_indicators}")

    assert result.persona == "IRS Agent", f"Expected 'IRS Agent', got '{result.persona}'"
    assert result.intent == "potential_scam", f"Expected 'potential_scam', got '{result.intent}'"
    assert len(result.risk_indicators) >= 3, f"Expected >=3 risk indicators, got {len(result.risk_indicators)}"
    assert len(result.bank_accounts) >= 1, f"Expected >=1 account, got {len(result.bank_accounts)}"
    print("  PASSED\n")
    return result


def test_risk_scoring(fg: FraudGraph):
    print("=" * 60)
    print("TEST 4: Risk Scoring")
    print("=" * 60)

    scorer = RiskScorer(fg)

    fraud_phones = fg.nodes_by_type(NodeType.PHONE)
    fraud_phone = None
    benign_phone = None
    for p in fraud_phones:
        label = fg.graph.nodes[p].get("label")
        if label == "fraud" and fraud_phone is None:
            fraud_phone = fg.graph.nodes[p]["raw"]
        elif label == "benign" and benign_phone is None:
            benign_phone = fg.graph.nodes[p]["raw"]
        if fraud_phone and benign_phone:
            break

    if fraud_phone:
        report = scorer.score_phone(fraud_phone)
        print(f"  Fraud phone {fraud_phone}:")
        print(f"    composite={report.composite_score:.3f}  high_risk={report.is_high_risk}")
        print(f"    density={report.fraud_density:.3f}  shared_acc={report.shared_account_score:.3f}  persona={report.persona_score:.3f}")

    if benign_phone:
        report = scorer.score_phone(benign_phone)
        print(f"  Benign phone {benign_phone}:")
        print(f"    composite={report.composite_score:.3f}  high_risk={report.is_high_risk}")
        print(f"    density={report.fraud_density:.3f}  shared_acc={report.shared_account_score:.3f}  persona={report.persona_score:.3f}")

    print("  PASSED\n")


def test_full_pipeline(fg: FraudGraph, model: FraudSAGE):
    print("=" * 60)
    print("TEST 5: Full Pipeline — Transcript → Risk Score")
    print("=" * 60)

    extractor = EntityExtractor()
    transcript = (
        "This is the IRS calling about your tax debt. Your SSN has been flagged. "
        "You must pay immediately via gift card. Send payment to account ACCT-998877. "
        "Do not tell anyone. Call us at 202-555-9999."
    )

    t0 = time.perf_counter()

    result = asyncio.run(extractor.extract(transcript))
    print(f"  Extracted: persona={result.persona}, accounts={result.bank_accounts}, "
          f"flags={len(result.risk_indicators)}")

    caller = "+19175550001"
    callee = "+18005550000"
    fg.add_call_event(
        caller=caller, callee=callee,
        persona=result.persona,
        accounts=result.bank_accounts,
        transcript_snippet=transcript[:200],
    )

    pyg = _graph_to_pyg(fg)

    scorer = RiskScorer(fg)
    report = scorer.score_phone(caller)

    latency = (time.perf_counter() - t0) * 1000
    print(f"  Risk score : {report.composite_score:.3f}")
    print(f"  High risk  : {report.is_high_risk}")
    print(f"  Detail     : {report.detail}")
    print(f"  Latency    : {latency:.1f}ms")
    print("  PASSED\n")


def test_cypher_export(fg: FraudGraph):
    print("=" * 60)
    print("TEST 6: Neo4j Cypher Export")
    print("=" * 60)
    stmts = fg.to_cypher_statements()
    print(f"  Generated {len(stmts)} Cypher statements")
    print(f"  Sample: {stmts[0][:100]}...")
    print("  PASSED\n")


if __name__ == "__main__":
    print("\n  FRAUD DETECTION ENGINE — Integration Tests\n")
    dataset = test_synthetic_data()
    model = test_gnn_training(dataset["pyg_data"])
    test_entity_extraction()
    test_risk_scoring(dataset["graph"])
    test_full_pipeline(dataset["graph"], model)
    test_cypher_export(dataset["graph"])
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
