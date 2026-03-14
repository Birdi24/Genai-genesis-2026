"""
Synthetic Fraud-Ring Dataset Generator.

Produces a realistic heterogeneous graph with planted fraud rings so the
GNN can be tested immediately without real PII data.

Strategy
--------
1. Generate *benign* phone numbers and bank accounts with random call
   patterns and low overlap.
2. Plant *fraud rings*: clusters of phones that share accounts, reuse
   known scam personas, and call many victims.
3. Assign ground-truth labels and export as both a FraudGraph and a
   PyG Data object ready for training.
"""

from __future__ import annotations

import logging
import random
from typing import Any

import networkx as nx
import numpy as np
import torch
from torch_geometric.data import Data
from torch_geometric.utils import from_networkx

from fraud_detection.graph.schema import FraudGraph, NodeType, _prefixed, RISK_PHRASES

import hashlib

def stable_node_seed(nid: str) -> int:
    h = hashlib.md5(nid.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


logger = logging.getLogger(__name__)

SCAM_PERSONAS = RISK_PHRASES if RISK_PHRASES else [
    "IRS Agent", "Tech Support", "Bank Officer",
    "Lottery Official", "Medicare Rep", "Utility Company",
    "Immigration Officer", "Crypto Advisor",
]

BENIGN_PERSONAS = ["Friend", "Family", "Colleague", "Business Partner"]



def _random_phone() -> str:
    return f"+1{random.randint(2000000000, 9999999999)}"


def _random_account() -> str:
    return f"ACCT-{random.randint(100000, 999999)}"


def generate_fraud_ring_dataset(
    n_benign_phones: int = 80,
    n_fraud_rings: int = 3,
    ring_size: int = 5,
    calls_per_benign: int = 3,
    calls_per_fraud: int = 8,
    seed: int = 42,
) -> dict[str, Any]:
    """Build a synthetic fraud-ring graph.

    Returns
    -------
    dict with keys:
        graph       : FraudGraph instance
        pyg_data    : torch_geometric.data.Data (node features, edge_index, labels)
        stats       : summary dict
    """
    random.seed(seed)
    np.random.seed(seed)

    fg = FraudGraph()
    g = fg.graph

    benign_phones = [_random_phone() for _ in range(n_benign_phones)]
    benign_accounts = [_random_account() for _ in range(n_benign_phones // 2)]

    for phone in benign_phones:
        fg.add_phone(phone, label="benign")

    for acc in benign_accounts:
        fg.add_account(acc, label="benign")

    for phone in benign_phones:
        acc = random.choice(benign_accounts)
        fg.link_phone_to_account(phone, acc)

    for phone in benign_phones:
        for _ in range(random.randint(1, calls_per_benign)):
            callee = random.choice(benign_phones)
            if callee != phone:
                fg.add_call_event(
                    caller=phone, callee=callee,
                    persona=random.choice(BENIGN_PERSONAS),
                    accounts=[],
                    label="benign",
                )

    # ── Plant fraud rings ─────────────────────────────────────────────
    fraud_phones: list[str] = []
    victims: set[str] = set()

    for ring_idx in range(n_fraud_rings):
        ring_phones = [_random_phone() for _ in range(ring_size)]
        shared_accounts = [_random_account() for _ in range(2)]
        ring_persona = random.choice(SCAM_PERSONAS)

        for p in ring_phones:
            fg.add_phone(p, label="fraud")
            fraud_phones.append(p)

        for acc in shared_accounts:
            fg.add_account(acc, label="fraud")
            for p in ring_phones:
                fg.link_phone_to_account(p, acc)

        # pick a pool of victims for this ring (may overlap across rings)
        ring_victims = random.sample(benign_phones, min(len(benign_phones), calls_per_fraud * ring_size))
        for scammer in ring_phones:
            for victim in random.sample(ring_victims, min(len(ring_victims), calls_per_fraud)):
                fg.add_call_event(
                    caller=scammer, callee=victim,
                    persona=ring_persona,
                    accounts=shared_accounts,
                    label="fraud",
                )

        # Track which benign phones have been victimized by fraud calls
        victims.update(ring_victims)

        logger.info("Planted fraud ring %d: %d phones, persona=%s", ring_idx, ring_size, ring_persona)

    # Ensure every benign phone has at least one incoming "fraud" call so the graph shows more red regions
    for ben_phone in benign_phones:
        if ben_phone not in victims:
            scammer = random.choice(fraud_phones)
            fg.add_call_event(
                caller=scammer, callee=ben_phone,
                persona=random.choice(SCAM_PERSONAS),
                accounts=[],
                label="fraud",
            )

    # ── Convert to PyG Data ───────────────────────────────────────────
    pyg_data = _graph_to_pyg(fg)

    stats = fg.summary()
    stats["n_fraud_phones"] = len(fraud_phones)
    stats["n_benign_phones"] = n_benign_phones
    stats["n_fraud_rings"] = n_fraud_rings

    logger.info("Synthetic dataset: %s", stats)
    return {"graph": fg, "pyg_data": pyg_data, "stats": stats}


def _graph_to_pyg(fg: FraudGraph, feature_dim: int = 16) -> Data:
    """Convert the FraudGraph into a PyG Data object with features and labels.

    Node feature encoding (fast, no external embeddings needed):
      - 4 bits  : one-hot node type
      - 4 floats: degree stats (in, out, total, normalized)
      - 8 floats: random structural embedding (stand-in until real features arrive)
    """
    g = fg.graph
    node_list = list(g.nodes())
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    n = len(node_list)

    type_map = {
        "phone_number": 0,
        "bank_account": 1,
        "persona": 2,
        "call": 3,
    }

    x = np.zeros((n, feature_dim), dtype=np.float32)
    labels = np.zeros(n, dtype=np.int64)
    label_map = {"fraud": 1, "benign": 0, "unknown": 0}

    for i, nid in enumerate(node_list):
        data = g.nodes[nid]
        ntype = data.get("ntype", "unknown")
        tid = type_map.get(ntype, 3)
        x[i, tid] = 1.0

        in_deg = g.in_degree(nid)
        out_deg = g.out_degree(nid)
        total_deg = in_deg + out_deg
        x[i, 4] = in_deg
        x[i, 5] = out_deg
        x[i, 6] = total_deg
        x[i, 7] = total_deg / max(g.number_of_nodes(), 1)

        seed = stable_node_seed(str(nid))
        rng = np.random.default_rng(seed)
        x[i, 8:] = rng.normal(0, 0.1, size=(feature_dim - 8,))

        labels[i] = label_map.get(data.get("label", "unknown"), 0)

    edges_src, edges_dst = [], []
    for u, v in g.edges():
        if u in node_to_idx and v in node_to_idx:
            edges_src.append(node_to_idx[u])
            edges_dst.append(node_to_idx[v])
            edges_src.append(node_to_idx[v])
            edges_dst.append(node_to_idx[u])

    edge_index = torch.tensor([edges_src, edges_dst], dtype=torch.long)
    x_tensor = torch.from_numpy(x)
    y_tensor = torch.from_numpy(labels)

    train_mask = torch.zeros(n, dtype=torch.bool)
    val_mask = torch.zeros(n, dtype=torch.bool)
    test_mask = torch.zeros(n, dtype=torch.bool)

    indices = list(range(n))
    random.shuffle(indices)
    t1 = int(0.6 * n)
    t2 = int(0.8 * n)
    for i in indices[:t1]:
        train_mask[i] = True
    for i in indices[t1:t2]:
        val_mask[i] = True
    for i in indices[t2:]:
        test_mask[i] = True

    return Data(
        x=x_tensor,
        edge_index=edge_index,
        y=y_tensor,
        train_mask=train_mask,
        val_mask=val_mask,
        test_mask=test_mask,
        node_ids=node_list,
    )
