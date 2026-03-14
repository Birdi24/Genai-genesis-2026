"""
Graph-based real-time risk scorer.

Given a target node, computes a composite risk score by combining:
  1. **Neighborhood fraud density** — ratio of fraud-labeled nodes in k-hop.
  2. **Shared-account overlap** — how many bank accounts are shared with
     known fraud nodes.
  3. **Persona toxicity** — whether the scam persona matches known patterns.
  4. **GNN probability** (optional) — the GraphSAGE fraud probability.

All weights are configurable via GraphConfig.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fraud_detection.config import GraphConfig
from fraud_detection.graph.schema import FraudGraph, NodeType, _prefixed

logger = logging.getLogger(__name__)

KNOWN_SCAM_PERSONAS = frozenset({
    "IRS Agent", "Tech Support", "Bank Officer",
    "Lottery Official", "Medicare Rep", "Utility Company",
    "Immigration Officer", "Crypto Advisor",
})


@dataclass
class RiskReport:
    node_id: str
    fraud_density: float
    shared_account_score: float
    persona_score: float
    gnn_fraud_prob: float | None
    composite_score: float
    is_high_risk: bool
    detail: str


class RiskScorer:
    def __init__(self, fg: FraudGraph, cfg: GraphConfig | None = None) -> None:
        self.fg = fg
        self.cfg = cfg or GraphConfig()

    def score_phone(
        self,
        phone: str,
        gnn_fraud_prob: float | None = None,
    ) -> RiskReport:
        nid = _prefixed(NodeType.PHONE, phone)
        if nid not in self.fg.graph:
            return RiskReport(
                node_id=nid, fraud_density=0, shared_account_score=0,
                persona_score=0, gnn_fraud_prob=gnn_fraud_prob,
                composite_score=0, is_high_risk=False,
                detail="Node not found in graph.",
            )

        neighborhood = self.fg.neighbors(nid, hops=self.cfg.max_hop)
        fraud_density = self._fraud_density(neighborhood)
        shared_acc = self._shared_account_score(nid, neighborhood)
        persona = self._persona_score(nid, neighborhood)

        w = self.cfg
        composite = (
            w.fraud_neighbor_weight * fraud_density
            + w.shared_account_weight * shared_acc
            + w.persona_similarity_weight * persona
        )

        if gnn_fraud_prob is not None:
            composite = 0.5 * composite + 0.5 * gnn_fraud_prob

        is_high = composite >= w.risk_threshold

        detail = (
            f"density={fraud_density:.2f} shared_acc={shared_acc:.2f} "
            f"persona={persona:.2f} gnn={gnn_fraud_prob}"
        )
        logger.info("Risk for %s: composite=%.3f high=%s  %s", phone, composite, is_high, detail)

        return RiskReport(
            node_id=nid,
            fraud_density=fraud_density,
            shared_account_score=shared_acc,
            persona_score=persona,
            gnn_fraud_prob=gnn_fraud_prob,
            composite_score=round(composite, 4),
            is_high_risk=is_high,
            detail=detail,
        )

    # ── Private scoring components ────────────────────────────────────

    def _fraud_density(self, neighborhood: set[str]) -> float:
        if not neighborhood:
            return 0.0
        fraud_count = sum(
            1 for n in neighborhood
            if self.fg.graph.nodes.get(n, {}).get("label") == "fraud"
        )
        return fraud_count / len(neighborhood)

    def _shared_account_score(self, nid: str, neighborhood: set[str]) -> float:
        target_accounts = {
            nb for nb in self.fg.graph.successors(nid)
            if self.fg.graph.nodes.get(nb, {}).get("ntype") == NodeType.ACCOUNT.value
        }
        if not target_accounts:
            return 0.0

        fraud_phones = [
            n for n in neighborhood
            if self.fg.graph.nodes.get(n, {}).get("ntype") == NodeType.PHONE.value
            and self.fg.graph.nodes.get(n, {}).get("label") == "fraud"
        ]

        shared = 0
        for fp in fraud_phones:
            fp_accounts = {
                nb for nb in self.fg.graph.successors(fp)
                if self.fg.graph.nodes.get(nb, {}).get("ntype") == NodeType.ACCOUNT.value
            }
            shared += len(target_accounts & fp_accounts)

        return min(shared / max(len(target_accounts), 1), 1.0)

    def _persona_score(self, nid: str, neighborhood: set[str]) -> float:
        personas_used: set[str] = set()
        call_nodes = [
            n for n in neighborhood
            if self.fg.graph.nodes.get(n, {}).get("ntype") == NodeType.CALL.value
        ]
        for cn in call_nodes:
            for nb in self.fg.graph.successors(cn):
                node_data = self.fg.graph.nodes.get(nb, {})
                if node_data.get("ntype") == NodeType.PERSONA.value:
                    personas_used.add(node_data.get("raw", ""))

        if not personas_used:
            return 0.0

        toxic_count = len(personas_used & KNOWN_SCAM_PERSONAS)
        return toxic_count / len(personas_used)
