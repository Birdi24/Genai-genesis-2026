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
