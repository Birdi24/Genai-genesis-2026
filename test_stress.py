"""
Stress test suite for the fraud detection engine.
Tests diverse inputs: edge cases, adversarial, multilingual,
benign calls, multi-ring scenarios, and latency under load.
"""

import asyncio
import time
import statistics

from fraud_detection.config import AppConfig
from fraud_detection.data.synthetic import generate_fraud_ring_dataset, _graph_to_pyg
from fraud_detection.graph.schema import FraudGraph, NodeType
from fraud_detection.graph.risk_scorer import RiskScorer
from fraud_detection.llm.entity_extractor import EntityExtractor
from fraud_detection.models.sage_model import FraudSAGE, train_one_epoch, evaluate
import torch

PASS = 0
FAIL = 0


def result(name, passed, detail=""):
    global PASS, FAIL
    tag = "PASS" if passed else "FAIL"
    if not passed:
        FAIL += 1
    else:
        PASS += 1
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


def setup():
    """Build graph, train model, return all components."""
    dataset = generate_fraud_ring_dataset(seed=42)
    fg = dataset["graph"]
    pyg = dataset["pyg_data"]
    cfg = AppConfig()

    model = FraudSAGE(
        in_channels=pyg.x.size(1),
        hidden_channels=cfg.gnn.hidden_dim,
        out_channels=cfg.gnn.output_dim,
        num_layers=cfg.gnn.num_layers,
        dropout=cfg.gnn.dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.gnn.learning_rate)
    for _ in range(200):
        train_one_epoch(model, optimizer, pyg.x, pyg.edge_index, pyg.y, pyg.train_mask)

    scorer = RiskScorer(fg, cfg.graph)
    extractor = EntityExtractor()
    return fg, model, pyg, scorer, extractor


# ═══════════════════════════════════════════════════════════════════
# TEST GROUP 1: Entity Extraction — diverse transcript inputs
# ═══════════════════════════════════════════════════════════════════

def test_extraction_battery(extractor):
    print("\n" + "=" * 64)
    print("GROUP 1: Entity Extraction Stress Tests")
    print("=" * 64)

    cases = [
        {
            "name": "Classic IRS scam",
            "transcript": "This is the IRS. Your SSN has been suspended. Pay immediately with gift cards to avoid arrest. Send to account ACCT-887766. Call 800-555-1234.",
            "expect_persona": "IRS Agent",
            "expect_intent": "potential_scam",
            "min_flags": 2,
            "min_accounts": 1,
        },
        {
            "name": "Tech support scam",
            "transcript": "Hello, I am calling from Microsoft tech support. Your computer has been infected with a dangerous virus. We need you to give us remote access. Please purchase a $500 gift card and provide the code. Your case ID is ACCT-TC9922.",
            "expect_persona": "Tech Support",
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Lottery scam",
            "transcript": "Congratulations! You have won the National Lottery prize of 2 million dollars! To claim your prize, wire transfer the processing fee of $999 to account ACCT-LT5500. Act now before the offer expires!",
            "expect_persona": "Lottery Official",
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Crypto/investment scam",
            "transcript": "Hey, I have an amazing bitcoin investment opportunity. Guaranteed 500% returns in 30 days. Just send your initial investment to account ACCT-BTC001. Don't tell anyone, this is an exclusive insider deal. Send payment now.",
            "expect_persona": "Crypto Advisor",
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Immigration scam",
            "transcript": "This is US Immigration and Customs. Your visa has been flagged for review. You must pay a fine immediately or face deportation. Wire transfer $2000 to account ACCT-IM3344. Do not tell anyone.",
            "expect_persona": "Immigration Officer",
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Completely benign call",
            "transcript": "Hey Mom, just calling to check in. How are you doing? I was thinking we could have dinner this weekend. Let me know what works for you. Love you!",
            "expect_persona": None,
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 0,
        },
        {
            "name": "Benign business call",
            "transcript": "Hi, this is Sarah from the marketing team. I wanted to follow up on the Q3 report. Can we schedule a meeting for Thursday at 2pm? Also, please review the slides I sent yesterday.",
            "expect_persona": None,
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 0,
        },
        {
            "name": "Benign bank call (legitimate)",
            "transcript": "Hello, this is your bank calling about a recent transaction on your debit card ending in 4455. We noticed a charge of $89.99 at an electronics store. Was this you? Please confirm.",
            "expect_persona": "Bank Officer",
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 0,
        },
        {
            "name": "Empty transcript",
            "transcript": "",
            "expect_persona": None,
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 0,
        },
        {
            "name": "Only numbers and symbols",
            "transcript": "1234567890 !@#$%^&*() +1-800-555-0199 $$$ ### ???",
            "expect_persona": None,
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 0,
        },
        {
            "name": "Repeated scam keywords",
            "transcript": "gift card gift card gift card wire transfer wire transfer you will be arrested arrested arrested act now act now immediate payment. Account ACCT-SPAM01 ACCT-SPAM02 ACCT-SPAM03.",
            "expect_persona": None,
            "expect_intent": "potential_scam",
            "min_flags": 3,
            "min_accounts": 1,
        },
        {
            "name": "Mixed signals — friendly tone, scam content",
            "transcript": "Hey buddy! Long time no talk. Listen, I have a great opportunity for you. The IRS owes you a refund. Just give me your social security number and I will process it. Send the fee to account ACCT-MX7788.",
            "expect_persona": "IRS Agent",
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Very long transcript (1000+ chars)",
            "transcript": "This is the IRS. " * 50 + "You owe back taxes. Send gift cards to account ACCT-LONG01. Do not tell anyone. Your SSN is compromised. You will be arrested. Act now. " * 5,
            "expect_persona": "IRS Agent",
            "expect_intent": "potential_scam",
            "min_flags": 3,
            "min_accounts": 1,
        },
        {
            "name": "Unicode and special characters",
            "transcript": "H\u00e9llo, th\u00ecs is t\u00e9ch s\u00fcpport. Y\u00f6ur c\u00f6mputer has a v\u00edrus. Send $500 gift card to account ACCT-UNI001.",
            "expect_persona": None,
            "expect_intent": "potential_scam",
            "min_flags": 1,
            "min_accounts": 1,
        },
        {
            "name": "Multiple phone numbers embedded",
            "transcript": "Call me at 212-555-0100 or 310-555-0200 or 415-555-0300. Also try +1 800 555 0400. This is about account ACCT-MULTI1.",
            "expect_persona": None,
            "expect_intent": "unknown",
            "min_flags": 0,
            "min_accounts": 1,
        },
    ]

    for case in cases:
        res = asyncio.run(extractor.extract(case["transcript"]))
        checks = []
        if case["expect_persona"] is not None:
            checks.append(res.persona == case["expect_persona"])
        else:
            checks.append(res.persona is None or res.persona == case["expect_persona"])
        checks.append(res.intent == case["expect_intent"])
        checks.append(len(res.risk_indicators) >= case["min_flags"])
        checks.append(len(res.bank_accounts) >= case["min_accounts"])

        passed = all(checks)
        detail = f"persona={res.persona}, intent={res.intent}, flags={len(res.risk_indicators)}, accts={res.bank_accounts}"
        result(case["name"], passed, detail)


# ═══════════════════════════════════════════════════════════════════
# TEST GROUP 2: Risk Scoring — known fraud vs benign nodes
# ═══════════════════════════════════════════════════════════════════

def test_risk_scoring_battery(fg, scorer):
    print("\n" + "=" * 64)
    print("GROUP 2: Risk Scoring Stress Tests")
    print("=" * 64)

    fraud_phones = [
        fg.graph.nodes[n]["raw"]
        for n in fg.nodes_by_type(NodeType.PHONE)
        if fg.graph.nodes[n].get("label") == "fraud"
    ]
    benign_phones = [
        fg.graph.nodes[n]["raw"]
        for n in fg.nodes_by_type(NodeType.PHONE)
        if fg.graph.nodes[n].get("label") == "benign"
    ]

    # Fraud phones should score higher
    fraud_scores = [scorer.score_phone(p).composite_score for p in fraud_phones[:10]]
    benign_scores = [scorer.score_phone(p).composite_score for p in benign_phones[:10]]

    avg_fraud = statistics.mean(fraud_scores) if fraud_scores else 0
    avg_benign = statistics.mean(benign_scores) if benign_scores else 0

    result(
        "Fraud phones score higher than benign on average",
        avg_fraud > avg_benign,
        f"avg_fraud={avg_fraud:.3f} vs avg_benign={avg_benign:.3f}",
    )

    result(
        "At least one fraud phone is high-risk",
        any(scorer.score_phone(p).is_high_risk for p in fraud_phones[:10]),
        f"scores={[f'{s:.2f}' for s in fraud_scores[:5]]}",
    )

    result(
        "No benign phone is high-risk",
        not any(scorer.score_phone(p).is_high_risk for p in benign_phones[:10]),
        f"scores={[f'{s:.2f}' for s in benign_scores[:5]]}",
    )

    # Unknown phone
    report = scorer.score_phone("+19999999999")
    result("Unknown phone returns zero score", report.composite_score == 0, report.detail)

    # Score stability — same input twice
    if fraud_phones:
        s1 = scorer.score_phone(fraud_phones[0]).composite_score
        s2 = scorer.score_phone(fraud_phones[0]).composite_score
        result("Score is deterministic (same input = same output)", s1 == s2, f"{s1} == {s2}")
    elif benign_phones:
        s1 = scorer.score_phone(benign_phones[0]).composite_score
        s2 = scorer.score_phone(benign_phones[0]).composite_score
        result("Score is deterministic (same input = same output)", s1 == s2, f"{s1} == {s2}")


# ═══════════════════════════════════════════════════════════════════
# TEST GROUP 3: Graph operations — edge cases
# ═══════════════════════════════════════════════════════════════════

def test_graph_operations(fg):
    print("\n" + "=" * 64)
    print("GROUP 3: Graph Operations Stress Tests")
    print("=" * 64)

    initial_nodes = fg.graph.number_of_nodes()

    # Add duplicate phone — should not crash, should be idempotent
    fg.add_phone("+10000000000", label="benign")
    fg.add_phone("+10000000000", label="benign")
    dupes = [n for n in fg.graph.nodes() if "10000000000" in n]
    result("Duplicate phone insert is idempotent", len(dupes) == 1)

    # Add call with missing callee (new node auto-created)
    call_id = fg.add_call_event(caller="+10000000000", callee="+19876543210")
    result("Call event creates new callee node", "+19876543210" in str(fg.graph.nodes()))

    # Link phone to non-existent account — should not crash
    fg.link_phone_to_account("+10000000000", "ACCT-DOESNOTEXIST")
    result("Linking to non-existent account does not crash", True)

    # Large batch insert
    t0 = time.perf_counter()
    for i in range(100):
        fg.add_call_event(
            caller=f"+1555000{i:04d}",
            callee=f"+1555100{i:04d}",
            persona="Test Persona",
            accounts=[f"ACCT-BATCH{i:04d}"],
        )
    batch_ms = (time.perf_counter() - t0) * 1000
    result(
        "Batch insert 100 calls",
        batch_ms < 2000,
        f"{batch_ms:.1f}ms ({batch_ms/100:.2f}ms per call)",
    )

    # Neighborhood query on high-degree node
    phones = fg.nodes_by_type(NodeType.PHONE)[:1]
    if phones:
        t0 = time.perf_counter()
        neighbors = fg.neighbors(phones[0], hops=2)
        nb_ms = (time.perf_counter() - t0) * 1000
        result("2-hop neighborhood query", nb_ms < 500, f"{len(neighbors)} nodes in {nb_ms:.1f}ms")

    # Cypher export on larger graph
    t0 = time.perf_counter()
    stmts = fg.to_cypher_statements()
    cypher_ms = (time.perf_counter() - t0) * 1000
    result("Cypher export on expanded graph", len(stmts) > 0, f"{len(stmts)} statements in {cypher_ms:.1f}ms")

    # Summary should still work
    summary = fg.summary()
    result("Graph summary after stress", summary.get("edges", 0) > 0, str(summary))


# ═══════════════════════════════════════════════════════════════════
# TEST GROUP 4: GNN model — robustness
# ═══════════════════════════════════════════════════════════════════

def test_gnn_robustness(model, pyg):
    print("\n" + "=" * 64)
    print("GROUP 4: GNN Model Robustness Tests")
    print("=" * 64)

    # Inference on full graph
    probs = model.predict_proba(pyg.x, pyg.edge_index)
    result("Predict proba returns valid shape", probs.shape == (pyg.x.size(0), 2), str(probs.shape))
    result("All probabilities sum to ~1", torch.allclose(probs.sum(dim=1), torch.ones(probs.size(0)), atol=1e-4))

    result(
        "No NaN in predictions",
        not torch.isnan(probs).any().item(),
    )

    result(
        "No Inf in predictions",
        not torch.isinf(probs).any().item(),
    )

    # Inference latency
    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        model.predict_proba(pyg.x, pyg.edge_index)
        times.append((time.perf_counter() - t0) * 1000)
    avg_ms = statistics.mean(times)
    p99_ms = sorted(times)[int(0.99 * len(times))]
    result("GNN inference latency", avg_ms < 50, f"avg={avg_ms:.2f}ms  p99={p99_ms:.2f}ms")

    # Zero features — should not crash
    zero_x = torch.zeros_like(pyg.x)
    zero_probs = model.predict_proba(zero_x, pyg.edge_index)
    result("Zero-feature input does not crash", zero_probs.shape == probs.shape)

    # Single node graph
    single_x = torch.randn(1, pyg.x.size(1))
    empty_edge = torch.zeros((2, 0), dtype=torch.long)
    single_prob = model.predict_proba(single_x, empty_edge)
    result("Single isolated node inference", single_prob.shape == (1, 2), str(single_prob))


# ═══════════════════════════════════════════════════════════════════
# TEST GROUP 5: Full pipeline — end-to-end latency under load
# ═══════════════════════════════════════════════════════════════════

def test_pipeline_latency(fg, scorer, extractor):
    print("\n" + "=" * 64)
    print("GROUP 5: Full Pipeline Latency Under Load")
    print("=" * 64)

    transcripts = [
        "IRS calling. Your SSN is suspended. Pay with gift cards to account ACCT-LAT001. Do not tell anyone.",
        "Hi, this is tech support from Microsoft. Your PC has a virus. Buy a gift card. Account ACCT-LAT002.",
        "Congratulations! You won the lottery! Wire transfer fee to account ACCT-LAT003. Act now!",
        "This is immigration. Your visa is revoked. Immediate payment required to ACCT-LAT004.",
        "Hey, it is me. Want to grab lunch tomorrow?",
        "Your Medicare benefits are expiring. Call us at 800-555-0001. Send fee to account ACCT-LAT005.",
        "Bitcoin investment. 1000 percent returns guaranteed. Account ACCT-LAT006. Do not tell anyone.",
        "Hi, your utility bill is overdue. Suspend your account unless you pay now. Account ACCT-LAT007.",
        "Just checking in. How is the project going? Any blockers?",
        "This is a warrant for your arrest. Your social security number was used in a crime. Act now.",
    ]

    latencies = []
    for i, transcript in enumerate(transcripts):
        caller = f"+1888000{i:04d}"
        callee = f"+1888100{i:04d}"

        t0 = time.perf_counter()
        extraction = asyncio.run(extractor.extract(transcript))
        fg.add_call_event(
            caller=caller, callee=callee,
            persona=extraction.persona,
            accounts=extraction.bank_accounts,
            transcript_snippet=transcript[:200],
        )
        report = scorer.score_phone(caller)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

    avg = statistics.mean(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(0.99 * len(latencies))]
    mx = max(latencies)

    result(
        f"10 sequential pipeline calls",
        avg < 50,
        f"avg={avg:.1f}ms  p50={p50:.1f}ms  p99={p99:.1f}ms  max={mx:.1f}ms",
    )

    # Rapid fire — 50 calls
    t0 = time.perf_counter()
    for i in range(50):
        extraction = asyncio.run(extractor.extract("IRS scam gift card account ACCT-RF0001"))
        fg.add_call_event(
            caller=f"+1777{i:07d}", callee="+18005550000",
            persona=extraction.persona,
            accounts=extraction.bank_accounts,
        )
    total_ms = (time.perf_counter() - t0) * 1000
    result(
        f"Rapid fire 50 calls",
        total_ms < 5000,
        f"total={total_ms:.0f}ms ({total_ms/50:.1f}ms per call)",
    )

    final_summary = fg.summary()
    result(
        "Graph integrity after load test",
        final_summary.get("edges", 0) > 1000,
        str(final_summary),
    )


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n  FRAUD DETECTION ENGINE — Stress Test Suite\n")

    print("Setting up (generating data + training GNN)...")
    fg, model, pyg, scorer, extractor = setup()
    print("Setup complete.\n")

    test_extraction_battery(extractor)
    test_risk_scoring_battery(fg, scorer)
    test_graph_operations(fg)
    test_gnn_robustness(model, pyg)
    test_pipeline_latency(fg, scorer, extractor)

    print("\n" + "=" * 64)
    print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
    print("=" * 64)
    if FAIL > 0:
        print("SOME TESTS FAILED — review output above.")
    else:
        print("ALL TESTS PASSED")
