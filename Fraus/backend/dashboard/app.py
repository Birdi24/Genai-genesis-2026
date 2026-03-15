"""
Fraus — Real-time Scam Detection Dashboard
Auto-fetches transcripts from the Fraus backend and displays analysis results.
"""

import json
from pathlib import Path

import requests
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

# ── Configuration ────────────────────────────────────────────────────

FRAUS_API = "http://127.0.0.1:8001"
FRAUD_ENGINE_API = "http://127.0.0.1:8000"

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "dashboard_state.json"

VERIFIED_NUMBERS = {
    "+18005551234": "Chase Bank — Official",
    "+18004567890": "Bank of America — Fraud Dept",
    "+18009221111": "Wells Fargo — Customer Service",
}


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"call_count": 0}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

st.set_page_config(
    page_title="Fraus — Scam Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Tokyo Night CSS ──────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

html, body { background: #16161e !important; }

@keyframes prismRotate {
  0%, 100% {
    background: #16161e,
    radial-gradient(ellipse 80% 50% at 20% 30%, rgba(125,207,255,0.15), transparent 50%),
    radial-gradient(ellipse 60% 80% at 85% 70%, rgba(187,154,247,0.12), transparent 45%),
    radial-gradient(ellipse 70% 60% at 50% 90%, rgba(122,162,247,0.1), transparent 40%);
  }
  50% {
    background: #16161e,
    radial-gradient(ellipse 70% 60% at 80% 40%, rgba(187,154,247,0.15), transparent 50%),
    radial-gradient(ellipse 80% 50% at 15% 75%, rgba(125,207,255,0.12), transparent 45%),
    radial-gradient(ellipse 60% 70% at 55% 15%, rgba(247,118,142,0.08), transparent 40%);
  }
}

:root {
  --tn-bg: #1a1b26;
  --tn-bg-dark: #16161e;
  --tn-bg-hl: #292e42;
  --tn-fg: #c0caf5;
  --tn-comment: #565f89;
  --tn-cyan: #7dcfff;
  --tn-blue: #7aa2f7;
  --tn-magenta: #bb9af7;
  --tn-green: #9ece6a;
  --tn-red: #f7768e;
  --tn-orange: #ff9e64;
  --tn-yellow: #e0af68;
  --tn-border: #3b4261;
}

.stApp {
  background: transparent !important;
  color: var(--tn-fg) !important;
  font-family: 'Inter', sans-serif !important;
}
.stApp::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  min-height: 100vh;
  animation: prismRotate 12s ease-in-out infinite;
  pointer-events: none;
}
[data-testid="stAppViewContainer"],
.main .block-container {
  position: relative;
  z-index: 1;
  background: transparent !important;
}

header[data-testid="stHeader"] { background-color: var(--tn-bg-dark) !important; }

.risk-card {
  background: var(--tn-bg-dark);
  border: 1px solid var(--tn-border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}

.risk-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 36px;
  font-weight: 700;
}

.risk-high { color: var(--tn-red); }
.risk-medium { color: var(--tn-orange); }
.risk-low { color: var(--tn-green); }

.risk-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--tn-comment);
  font-weight: 600;
}

.tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  margin: 2px 4px 2px 0;
  font-family: 'JetBrains Mono', monospace;
}

.tag-red { background: rgba(247,118,142,0.15); color: var(--tn-red); border: 1px solid rgba(247,118,142,0.3); }
.tag-blue { background: rgba(122,162,247,0.15); color: var(--tn-blue); border: 1px solid rgba(122,162,247,0.3); }
.tag-magenta { background: rgba(187,154,247,0.15); color: var(--tn-magenta); border: 1px solid rgba(187,154,247,0.3); }
.tag-cyan { background: rgba(125,207,255,0.15); color: var(--tn-cyan); border: 1px solid rgba(125,207,255,0.3); }
.tag-orange { background: rgba(255,158,100,0.15); color: var(--tn-orange); border: 1px solid rgba(255,158,100,0.3); }
.tag-green { background: rgba(158,206,106,0.15); color: var(--tn-green); border: 1px solid rgba(158,206,106,0.3); }

.stat-row {
  display: flex;
  gap: 12px;
  margin-bottom: 1rem;
}
.stat-box {
  flex: 1;
  background: var(--tn-bg-dark);
  border: 1px solid var(--tn-border);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  text-align: center;
}
.stat-box .num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 24px;
  font-weight: 700;
  color: var(--tn-cyan);
}
.stat-box .lbl {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--tn-comment);
  margin-top: 2px;
}

.section-title {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--tn-comment);
  font-weight: 700;
  margin-bottom: 0.75rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--tn-border);
}

</style>
""", unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────

_persisted = _load_state()
for _key, _default in [
    ("graph_data", None), ("graph_stats", None),
    ("graph_version", 0), ("insights", []),
    ("selected_insight", None), ("latest_transcript", None),
    ("call_count", _persisted.get("call_count", 0)),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ── Helpers ──────────────────────────────────────────────────────────

def _fetch_graph():
    try:
        gr = requests.get(f"{FRAUD_ENGINE_API}/graph/data?max_phones=40", timeout=10)
        gr.raise_for_status()
        st.session_state.graph_data = gr.json()
    except Exception:
        pass
    try:
        gs = requests.get(f"{FRAUD_ENGINE_API}/graph/stats", timeout=10)
        gs.raise_for_status()
        st.session_state.graph_stats = gs.json()
    except Exception:
        pass
    try:
        ins = requests.get(f"{FRAUD_ENGINE_API}/graph/insights", timeout=10)
        ins.raise_for_status()
        st.session_state.insights = ins.json()
    except Exception:
        pass
    st.session_state.graph_version += 1


def _fetch_latest_transcript():
    try:
        resp = requests.get(f"{FRAUS_API}/transcripts/latest", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            st.session_state.latest_transcript = data
    except Exception:
        pass


def _transcript_node_ids(transcript):
    """Build graph node IDs from the transcript's analysis extraction data."""
    if not transcript:
        return set()
    nodes = set()
    caller = transcript.get("caller_number", "")
    if caller:
        nodes.add(f"phone_number::{caller}")
    analysis = transcript.get("analysis") or {}
    ext = analysis.get("extraction") or {}
    for phone in ext.get("phone_numbers", []):
        nodes.add(f"phone_number::{phone.strip()}")
    for acct in ext.get("bank_accounts", []):
        nodes.add(f"bank_account::{acct.strip()}")
    persona = ext.get("persona")
    if persona:
        nodes.add(f"persona::{persona}")
    return nodes


def _build_transcript_graph(transcript):
    """Create synthetic nodes and edges from a transcript record so there
    is always something to render on the graph even when the fraud engine
    has no matching data."""
    if not transcript:
        return [], []

    analysis = transcript.get("analysis") or {}
    ext = analysis.get("extraction") or {}
    risk_score = analysis.get("risk_score", 0)
    is_high = analysis.get("is_high_risk", False)

    synth_nodes = []
    synth_edges = []
    added_ids = set()

    def _add(nid, label, ntype):
        if nid in added_ids:
            return
        added_ids.add(nid)
        synth_nodes.append({"id": nid, "label": label, "ntype": ntype,
                            "fraud_label": "fraud" if is_high else "normal"})

    caller = transcript.get("caller_number", "")
    caller_id = f"phone_number::{caller}" if caller else None
    if caller_id:
        _add(caller_id, caller, "phone_number")

    # Call-event hub (central node for this transcript)
    call_id = f"call_event::{transcript.get('transcript_id', 'latest')}"
    call_label = f"Call ({transcript.get('caller_label') or 'Unknown'})"
    _add(call_id, call_label, "call_event")
    if caller_id:
        synth_edges.append({"source": caller_id, "target": call_id})

    for phone in ext.get("phone_numbers", []):
        pid = f"phone_number::{phone.strip()}"
        _add(pid, phone.strip(), "phone_number")
        synth_edges.append({"source": call_id, "target": pid})

    for acct in ext.get("bank_accounts", []):
        aid = f"bank_account::{acct.strip()}"
        _add(aid, acct.strip(), "bank_account")
        synth_edges.append({"source": call_id, "target": aid})

    persona = ext.get("persona")
    if persona:
        pid = f"persona::{persona}"
        _add(pid, persona, "persona")
        synth_edges.append({"source": call_id, "target": pid})

    for indicator in ext.get("risk_indicators", []):
        rid = f"risk_indicator::{indicator}"
        _add(rid, indicator, "risk_indicator")
        synth_edges.append({"source": call_id, "target": rid})

    return synth_nodes, synth_edges


# ── Header ───────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center; padding: 1.5rem 0 0.5rem;">
  <span style="font-size:48px;">🛡️</span>
  <h1 style="margin:0; font-size:32px; letter-spacing:6px; color:#7dcfff;">FRAUS</h1>
  <p style="color:#565f89; font-size:13px; letter-spacing:3px;">REAL-TIME SCAM DETECTION ENGINE</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# ── Fetch data ───────────────────────────────────────────────────────

_fetch_graph()
_fetch_latest_transcript()


# ── Layout ───────────────────────────────────────────────────────────

left_col, right_col = st.columns([4, 7], gap="large")


# ── LEFT COLUMN: Meaningful Connections ──────────────────────────────

with left_col:
    st.markdown('<div class="section-title">Meaningful Connections</div>', unsafe_allow_html=True)

    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state.call_count += 1
        _save_state({"call_count": st.session_state.call_count})
        _fetch_graph()
        _fetch_latest_transcript()

    gs = st.session_state.graph_stats
    if gs:
        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-box"><div class="num">{gs.get('phone_number', 0)}</div><div class="lbl">Phones</div></div>
          <div class="stat-box"><div class="num">{gs.get('bank_account', 0)}</div><div class="lbl">Accounts</div></div>
          <div class="stat-box"><div class="num">{gs.get('persona', 0)}</div><div class="lbl">Personas</div></div>
        </div>
        <div class="stat-row">
          <div class="stat-box"><div class="num">{st.session_state.call_count}</div><div class="lbl">Calls</div></div>
          <div class="stat-box"><div class="num">{gs.get('edges', 0)}</div><div class="lbl">Edges</div></div>
        </div>
        """, unsafe_allow_html=True)

    # Latest transcript entry
    latest_tx = st.session_state.latest_transcript
    has_latest = latest_tx is not None

    # Build the options list
    SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    insight_list = st.session_state.insights or []

    radio_options = ["○ Show all"]
    if has_latest:
        caller_num = latest_tx.get("caller_number", "Unknown")
        caller_lbl = latest_tx.get("caller_label") or "Unknown"
        radio_options.append(f"📱 Latest transcript: {caller_num} — {caller_lbl}")

    radio_options += [
        f"{SEVERITY_ICON.get(i['severity'], '⚪')} {i['summary']}"
        for i in insight_list
    ]

    if len(radio_options) > 1:
        sel = st.session_state.selected_insight
        if sel == "__latest_transcript__":
            current_idx = 1 if has_latest else 0
        elif sel is None:
            current_idx = 0
        else:
            offset = 2 if has_latest else 1
            current_idx = next(
                (i + offset for i, x in enumerate(insight_list) if x == sel), 0
            )

        choice = st.radio(
            "insight_selector",
            radio_options,
            index=min(current_idx, len(radio_options) - 1),
            label_visibility="collapsed",
            key="insight_radio",
        )

        if choice == "○ Show all":
            st.session_state.selected_insight = None
        elif has_latest and choice == radio_options[1]:
            st.session_state.selected_insight = "__latest_transcript__"
        else:
            offset = 2 if has_latest else 1
            idx = radio_options.index(choice) - offset
            st.session_state.selected_insight = insight_list[idx]

        # Show extraction summary when latest transcript is selected
        if st.session_state.selected_insight == "__latest_transcript__" and has_latest:
            analysis = latest_tx.get("analysis") or {}
            ext = analysis.get("extraction") or {}
            persona = ext.get("persona") or "None detected"
            intent = ext.get("intent") or "unknown"
            accounts = ext.get("bank_accounts", [])
            phones = ext.get("phone_numbers", [])
            flags = ext.get("risk_indicators", [])

            accounts_html = " ".join(
                f'<span class="tag tag-orange">{a}</span>' for a in accounts
            ) or '<span class="tag tag-cyan">None</span>'
            phones_html = " ".join(
                f'<span class="tag tag-blue">{p}</span>' for p in phones
            ) or '<span class="tag tag-cyan">None</span>'
            flags_html = " ".join(
                f'<span class="tag tag-red">{f}</span>' for f in flags
            ) or '<span class="tag tag-green">None</span>'

            st.markdown(f"""
            <div class="risk-card">
              <div class="risk-title" style="margin-bottom:10px;">Transcript Extraction</div>
              <div style="margin-bottom:6px;"><span style="color:var(--tn-comment);">Persona</span> <span class="tag tag-magenta">{persona}</span></div>
              <div style="margin-bottom:6px;"><span style="color:var(--tn-comment);">Intent</span> <span class="tag tag-red">{intent}</span></div>
              <div style="margin-bottom:6px;"><span style="color:var(--tn-comment);">Accounts</span> {accounts_html}</div>
              <div style="margin-bottom:6px;"><span style="color:var(--tn-comment);">Phones</span> {phones_html}</div>
              <div><span style="color:var(--tn-comment);">Risk Flags</span> {flags_html}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="risk-card" style="text-align:center; padding:1.5rem;">
          <span style="color:#565f89;">No insights detected yet.</span><br>
          <span style="color:#3b4261; font-size:12px;">
            Patterns appear as transcripts are analyzed.
          </span>
        </div>
        """, unsafe_allow_html=True)


# ── RIGHT COLUMN: Network Graph ──────────────────────────────────────

with right_col:
    st.markdown('<div class="section-title">Network Graph</div>', unsafe_allow_html=True)

    # Highlight set for graph
    sel = st.session_state.selected_insight
    if sel == "__latest_transcript__":
        highlight_ids = _transcript_node_ids(st.session_state.latest_transcript)
        if not highlight_ids:
            highlight_ids = None
    elif sel:
        highlight_ids = set(sel.get("involved_nodes", []))
    else:
        highlight_ids = None

    # Merge synthetic transcript nodes into graph data when selected
    gd = st.session_state.graph_data or {"nodes": [], "edges": []}
    all_nodes = list(gd.get("nodes", []))
    all_edges = list(gd.get("edges", []))

    show_transcript_overlay = sel == "__latest_transcript__"
    if show_transcript_overlay:
        tx_nodes, tx_edges = _build_transcript_graph(st.session_state.latest_transcript)
        existing_ids = {n["id"] for n in all_nodes}
        for tn in tx_nodes:
            if tn["id"] not in existing_ids:
                all_nodes.append(tn)
                existing_ids.add(tn["id"])
        all_edges.extend(tx_edges)
        if highlight_ids is None:
            highlight_ids = set()
        highlight_ids |= {n["id"] for n in tx_nodes}

    # Render graph
    if all_nodes:
        NODE_CFG = {
            "phone_number":   {"color": "#7aa2f7", "size": 12, "shape": "dot"},
            "bank_account":   {"color": "#ff9e64", "size": 16, "shape": "square"},
            "persona":        {"color": "#bb9af7", "size": 20, "shape": "triangle"},
            "call_event":     {"color": "#7dcfff", "size": 24, "shape": "star"},
            "risk_indicator": {"color": "#f7768e", "size": 14, "shape": "diamond"},
        }
        FRAUD_COLOR = "#ff4466"
        EDGE_COLOR = "#5a6380"
        HIGHLIGHT_COLOR = "#7dcfff"
        DIM_NODE_COLOR = "#2a2d3d"
        DIM_EDGE_COLOR = "#22243000"

        node_ids = {n["id"] for n in all_nodes}

        nodes = []
        for n in all_nodes:
            ntype = n["ntype"]
            is_fraud = n.get("fraud_label") == "fraud"
            cfg = NODE_CFG.get(ntype, {"color": "#565f89", "size": 10, "shape": "dot"})

            if highlight_ids is not None:
                in_focus = n["id"] in highlight_ids
                color = (HIGHLIGHT_COLOR if not is_fraud else FRAUD_COLOR) if in_focus else DIM_NODE_COLOR
                size = cfg["size"] + 10 if in_focus else max(cfg["size"] - 2, 5)
                border = 4 if in_focus else 0
                font_color = "#ffffff" if in_focus else "#3b4261"
            else:
                color = FRAUD_COLOR if is_fraud else cfg["color"]
                size = cfg["size"] + 6 if is_fraud else cfg["size"]
                border = 3 if is_fraud else 1
                font_color = "#c0caf5"

            label = "" if ntype == "phone_number" else n["label"]
            nodes.append(Node(
                id=n["id"], label=label, title=n["label"],
                size=size, color=color, shape=cfg["shape"],
                font={"color": font_color, "size": 10, "strokeWidth": 2, "strokeColor": "#16161e"},
                borderWidth=border, borderWidthSelected=5,
            ))

        edges = []
        seen = set()
        for e in all_edges:
            src, tgt = e["source"], e["target"]
            if src not in node_ids or tgt not in node_ids:
                continue
            pair = tuple(sorted([src, tgt]))
            if pair in seen:
                continue
            seen.add(pair)

            if highlight_ids is not None:
                both_in = src in highlight_ids and tgt in highlight_ids
                edge_color = HIGHLIGHT_COLOR if both_in else DIM_EDGE_COLOR
                edge_width = 3 if both_in else 0.5
            else:
                edge_color = EDGE_COLOR
                edge_width = 1.5

            edges.append(Edge(source=src, target=tgt, color=edge_color, width=edge_width))

        config = Config(
            width="100%", height=620,
            directed=True, physics=True, hierarchical=False,
            nodeHighlightBehavior=True, highlightColor="#7dcfff",
            collapsible=False,
            node={"labelProperty": "label"},
            link={"highlightColor": "#7aa2f7", "renderLabel": False},
            backgroundColor="#16161e",
            key=f"fraud_graph_{st.session_state.graph_version}_{id(sel)}",
        )

        agraph(nodes=nodes, edges=edges, config=config)

        st.markdown("""
        <div style="display:flex; gap:16px; justify-content:center; font-size:12px; color:#565f89; margin-top:8px;">
          <span>● Phone</span> <span>■ Account</span> <span>▲ Persona</span>
          <span style="color:#7dcfff;">★ Call Event</span>
          <span style="color:#f7768e;">◆ Risk Flag</span>
          <span style="color:#ff4466;">● Fraud-flagged</span>
          <span style="color:#7dcfff;">◉ Highlighted</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="risk-card" style="text-align:center; padding:3rem;">
          <span style="font-size:36px;">🔗</span><br>
          <span style="color:#565f89;">Fraud detection engine graph not available</span><br>
          <span style="color:#3b4261; font-size:12px;">
            Start the fraud engine at localhost:8000 to see the network graph.
          </span>
        </div>
        """, unsafe_allow_html=True)
