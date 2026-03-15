"""
NetworkX-based heterogeneous fraud graph.

Schema
------
Node types : phone_number, bank_account, persona
Edge types : CALLED_FROM, CALLED_TO, MENTIONED_ACCOUNT,
             USED_PERSONA, OWNS_ACCOUNT

Designed for O(1) node-lookup via typed prefixes (e.g. "phone::+1...")
and for zero-friction migration to Neo4j via Cypher export.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_STORE = Path("data/graph_store.json")

RISK_PHRASES = []  # list of phrases associated with suspicious behavior

class NodeType(str, Enum):
    PHONE = "phone_number"     # has phone number
    ACCOUNT = "bank_account"   # the account number of user callers
    PERSONA = "persona"        # call persona used by suspicious callers (e.g. "IRS agent", "Tech support")
    CALL = "call"              # call event connecting callers and callees, may have a transcript snippet and other metadata

class EdgeType(str, Enum):
    CALLED_FROM = "CALLED_FROM" # possible scammer or caller of a suspicious call event
    CALLED_TO = "CALLED_TO"     # possible victim or target of a call
    MENTIONED_ACCOUNT = "MENTIONED_ACCOUNT" # account mentioned during a call suspiciously
    USED_PERSONA = "USED_PERSONA" # persona used during a call (e.g. "IRS agent", "Tech support")
    OWNS_ACCOUNT = "OWNS_ACCOUNT" # indicates ownership or strong association between a phone number and bank account (e.g. from call transcripts or external data)


def _prefixed(ntype: NodeType, value: str) -> str:
    """Deterministic node-id that encodes type for O(1) lookup."""
    return f"{ntype.value}::{value}"


class FraudGraph:
    """Thread-safe wrapper around a NetworkX DiGraph with typed nodes/edges.

    All public mutators acquire a coarse lock so that the FastAPI event-loop
    can safely read while the background ingest writes.
    """

    def __init__(self, store_path: Path | None = DEFAULT_GRAPH_STORE) -> None:
        self._g = nx.DiGraph()
        self._store_path = store_path
        import threading
        self._lock = threading.Lock()

    # ── Persistence ────────────────────────────────────────────────────

    def save(self) -> None:
        """Dump the graph to JSON so it survives server reboots."""
        if not self._store_path:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = json_graph.node_link_data(self._g)
        tmp = self._store_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f)
        tmp.replace(self._store_path)
        logger.debug("Graph persisted to %s (%d nodes, %d edges)",
                     self._store_path, self._g.number_of_nodes(), self._g.number_of_edges())

    @classmethod
    def load(cls, store_path: Path = DEFAULT_GRAPH_STORE) -> FraudGraph:
        """Load a previously saved graph, or return an empty one."""
        fg = cls(store_path=store_path)
        if store_path.exists():
            with open(store_path) as f:
                data = json.load(f)
            fg._g = json_graph.node_link_graph(data, directed=True, multigraph=False)
            logger.info("Loaded persisted graph from %s (%d nodes, %d edges)",
                        store_path, fg._g.number_of_nodes(), fg._g.number_of_edges())
        return fg

    # ── Node helpers ──────────────────────────────────────────────────

    def _upsert_node(self, nid: str, ntype: str, raw: str, label: str, **attrs: Any) -> None:
        """Insert a node or merge attributes without downgrading an existing label."""
        with self._lock:
            if nid in self._g:
                existing = self._g.nodes[nid]
                if label != "unknown" and existing.get("label") != label:
                    existing["label"] = label
                existing.update(attrs)
            else:
                self._g.add_node(
                    nid, ntype=ntype, raw=raw,
                    label=label, created_at=time.time(), **attrs,
                )

    def add_phone(self, number: str, *, label: str = "unknown", **attrs: Any) -> str:
        nid = _prefixed(NodeType.PHONE, number)
        self._upsert_node(nid, NodeType.PHONE.value, number, label, **attrs)
        return nid

    def add_account(self, account_id: str, *, label: str = "unknown", **attrs: Any) -> str:
        nid = _prefixed(NodeType.ACCOUNT, account_id)
        self._upsert_node(nid, NodeType.ACCOUNT.value, account_id, label, **attrs)
        return nid

    def add_persona(self, name: str, *, label: str = "unknown", **attrs: Any) -> str:
        nid = _prefixed(NodeType.PERSONA, name)
        self._upsert_node(nid, NodeType.PERSONA.value, name, label, **attrs)
        return nid

    def add_call_event(
        self, *, caller: str, callee: str,
        persona: str | None = None,
        accounts: list[str] | None = None,
        transcript_snippet: str = "",
        label: str = "unknown",
    ) -> str:
        call_id = f"call::{uuid.uuid4().hex[:12]}"
        caller_nid = self.add_phone(caller)
        callee_nid = self.add_phone(callee)

        with self._lock:
            self._g.add_node(
                call_id, ntype=NodeType.CALL.value,
                label=label, transcript=transcript_snippet,
                created_at=time.time(),
            )
            self._g.add_edge(caller_nid, call_id, etype=EdgeType.CALLED_FROM.value)
            self._g.add_edge(call_id, callee_nid, etype=EdgeType.CALLED_TO.value)

        if persona:
            p_nid = self.add_persona(persona)
            with self._lock:
                self._g.add_edge(call_id, p_nid, etype=EdgeType.USED_PERSONA.value)

        for acc in accounts or []:
            a_nid = self.add_account(acc)
            with self._lock:
                self._g.add_edge(call_id, a_nid, etype=EdgeType.MENTIONED_ACCOUNT.value)

        logger.debug("Added call %s  caller=%s callee=%s", call_id, caller, callee)
        return call_id

    def link_phone_to_account(self, phone: str, account: str) -> None:
        p_nid = _prefixed(NodeType.PHONE, phone)
        a_nid = _prefixed(NodeType.ACCOUNT, account)
        with self._lock:
            if p_nid in self._g and a_nid in self._g:
                self._g.add_edge(p_nid, a_nid, etype=EdgeType.OWNS_ACCOUNT.value)

    # ── Query helpers ─────────────────────────────────────────────────

    @property
    def graph(self) -> nx.DiGraph:
        return self._g

    def get_node(self, nid: str) -> dict[str, Any] | None:
        return dict(self._g.nodes[nid]) if nid in self._g else None

    def neighbors(self, nid: str, hops: int = 1) -> set[str]:
        """Return all node-ids reachable within *hops* (undirected)."""
        visited: set[str] = set()
        frontier = {nid}
        for _ in range(hops):
            next_frontier: set[str] = set()
            for n in frontier:
                for nb in set(self._g.successors(n)) | set(self._g.predecessors(n)):
                    if nb not in visited and nb != nid:
                        next_frontier.add(nb)
            visited |= next_frontier
            frontier = next_frontier
        return visited

    def nodes_by_type(self, ntype: NodeType) -> list[str]:
        return [n for n, d in self._g.nodes(data=True) if d.get("ntype") == ntype.value]

    def set_label(self, nid: str, label: str) -> None:
        with self._lock:
            if nid in self._g:
                self._g.nodes[nid]["label"] = label

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, d in self._g.nodes(data=True):
            t = d.get("ntype", "unknown")
            counts[t] = counts.get(t, 0) + 1
        counts["edges"] = self._g.number_of_edges()
        return counts

    # ── Insight detection ────────────────────────────────────────────

    def detect_insights(self) -> list[dict[str, Any]]:
        """Scan the graph for fraud-indicative structural patterns.

        Returns a list of insight dicts, each with:
            id, severity, summary, involved_nodes
        """
        g = self._g
        insights: list[dict[str, Any]] = []
        _id = 0

        # ── 1. Shared drop accounts ───────────────────────────────────
        # Accounts targeted by 2+ distinct phone callers are drop accounts.
        for nid, data in g.nodes(data=True):
            if data.get("ntype") != NodeType.ACCOUNT.value:
                continue
            callers: set[str] = set()
            for pred in g.predecessors(nid):
                if g.nodes[pred].get("ntype") == NodeType.CALL.value:
                    for caller in g.predecessors(pred):
                        if g.nodes[caller].get("ntype") == NodeType.PHONE.value:
                            callers.add(caller)
            for succ in g.successors(nid):
                if g.nodes[succ].get("ntype") == NodeType.PHONE.value:
                    callers.add(succ)
            if len(callers) >= 2:
                raw = data.get("raw", nid.split("::")[-1])
                _id += 1
                insights.append({
                    "id": f"drop-{_id}",
                    "severity": "high" if len(callers) >= 3 else "medium",
                    "summary": (
                        f"Shared drop account: {len(callers)} phones target "
                        f"account {raw}"
                    ),
                    "involved_nodes": list(callers | {nid}),
                })

        # ── 2. Reused scam personas ───────────────────────────────────
        # Personas used by 3+ different phones indicate an organised ring.
        for nid, data in g.nodes(data=True):
            if data.get("ntype") != NodeType.PERSONA.value:
                continue
            phones: set[str] = set()
            for pred in g.predecessors(nid):
                if g.nodes[pred].get("ntype") == NodeType.CALL.value:
                    for caller in g.predecessors(pred):
                        if g.nodes[caller].get("ntype") == NodeType.PHONE.value:
                            phones.add(caller)
            if len(phones) >= 3:
                raw = data.get("raw", nid.split("::")[-1])
                _id += 1
                insights.append({
                    "id": f"persona-{_id}",
                    "severity": "high",
                    "summary": (
                        f"Fraud ring: {len(phones)} phones impersonating "
                        f"\"{raw}\""
                    ),
                    "involved_nodes": list(phones | {nid}),
                })

        # ── 3. High-degree hub phones ─────────────────────────────────
        # Phones with unusually high connectivity are potential ring leaders.
        phone_degrees: list[tuple[str, int]] = []
        for nid, data in g.nodes(data=True):
            if data.get("ntype") != NodeType.PHONE.value:
                continue
            deg = g.in_degree(nid) + g.out_degree(nid)
            phone_degrees.append((nid, deg))
        phone_degrees.sort(key=lambda x: x[1], reverse=True)
        if phone_degrees:
            median_deg = phone_degrees[len(phone_degrees) // 2][1]
            threshold = max(median_deg * 3, 6)
            for nid, deg in phone_degrees:
                if deg < threshold:
                    break
                raw = g.nodes[nid].get("raw", nid.split("::")[-1])
                neighbors = list(self.neighbors(nid, hops=1))[:10]
                _id += 1
                insights.append({
                    "id": f"hub-{_id}",
                    "severity": "medium",
                    "summary": (
                        f"Central hub: {raw} has {deg} connections "
                        f"(median is {median_deg})"
                    ),
                    "involved_nodes": [nid] + neighbors,
                })

        # ── 4. Fraud-labelled clusters ────────────────────────────────
        # Connected components of fraud-labelled phones.
        fraud_phones = {
            n for n, d in g.nodes(data=True)
            if d.get("ntype") == NodeType.PHONE.value and d.get("label") == "fraud"
        }
        if fraud_phones:
            ug = g.to_undirected()
            for comp in nx.connected_components(ug):
                cluster = comp & fraud_phones
                if len(cluster) >= 2:
                    involved = set()
                    for n in cluster:
                        involved.add(n)
                        for nb in self.neighbors(n, hops=1):
                            ntype = g.nodes.get(nb, {}).get("ntype", "")
                            if ntype in (NodeType.ACCOUNT.value, NodeType.PERSONA.value):
                                involved.add(nb)
                    _id += 1
                    insights.append({
                        "id": f"ring-{_id}",
                        "severity": "critical",
                        "summary": (
                            f"Fraud ring detected: {len(cluster)} confirmed "
                            f"fraud phones in connected cluster"
                        ),
                        "involved_nodes": list(involved),
                    })

        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        insights.sort(key=lambda i: severity_rank.get(i["severity"], 9))
        return insights

    # ── Export (Neo4j migration path) ─────────────────────────────────

    def to_cypher_statements(self) -> list[str]:
        """Generate Cypher CREATE statements for painless Neo4j import."""
        stmts: list[str] = []
        for nid, data in self._g.nodes(data=True):
            props = ", ".join(f'{k}: "{v}"' for k, v in data.items() if k != "ntype")
            lbl = data.get("ntype", "Node").replace(" ", "")
            stmts.append(f'CREATE (:{lbl} {{id: "{nid}", {props}}})')
        for u, v, data in self._g.edges(data=True):
            rel = data.get("etype", "RELATED")
            stmts.append(f'MATCH (a {{id: "{u}"}}), (b {{id: "{v}"}}) CREATE (a)-[:{rel}]->(b)')
        return stmts
