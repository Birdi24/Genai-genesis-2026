"""
Fraus — Real-time Scam Detection Dashboard
Streamlit frontend for the fraud detection engine.
"""

import streamlit as st
import requests
from streamlit_agraph import agraph, Node, Edge, Config

# ── Configuration ─────────────────────────────────────────────────────

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Fraus — Scam Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Tokyo Night CSS ───────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --tn-bg:        #1a1b26;
    --tn-bg-dark:   #16161e;
    --tn-bg-hl:     #292e42;
    --tn-fg:        #c0caf5;
    --tn-comment:   #565f89;
    --tn-cyan:      #7dcfff;
    --tn-blue:      #7aa2f7;
    --tn-magenta:   #bb9af7;
    --tn-green:     #9ece6a;
    --tn-red:       #f7768e;
    --tn-orange:    #ff9e64;
    --tn-yellow:    #e0af68;
    --tn-border:    #3b4261;
}

.stApp {
    background-color: var(--tn-bg) !important;
    color: var(--tn-fg) !important;
    font-family: 'Inter', sans-serif !important;
}

header[data-testid="stHeader"] { background-color: var(--tn-bg-dark) !important; }

.stTextArea textarea {
    background-color: var(--tn-bg-dark) !important;
    color: var(--tn-fg) !important;
    border: 1px solid var(--tn-border) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    border-radius: 8px !important;
}

.stTextInput input {
    background-color: var(--tn-bg-dark) !important;
    color: var(--tn-fg) !important;
    border: 1px solid var(--tn-border) !important;
    border-radius: 8px !important;
}

div.stButton > button {
    background: linear-gradient(135deg, var(--tn-blue), var(--tn-magenta)) !important;
    color: #1a1b26 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 2rem !important;
    font-size: 15px !important;
    width: 100% !important;
    transition: opacity 0.2s !important;
}
div.stButton > button:hover { opacity: 0.85 !important; }

.risk-card {
    background: var(--tn-bg-dark);
    border: 1px solid var(--tn-border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}

.risk-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.risk-title {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--tn-comment);
    font-weight: 600;
}

.risk-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 36px;
    font-weight: 700;
}

.risk-high   { color: var(--tn-red); }
.risk-medium { color: var(--tn-orange); }
.risk-low    { color: var(--tn-green); }

.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    margin: 2px 4px 2px 0;
    font-family: 'JetBrains Mono', monospace;
}

.tag-red      { background: rgba(247,118,142,0.15); color: var(--tn-red); border: 1px solid rgba(247,118,142,0.3); }
.tag-blue     { background: rgba(122,162,247,0.15); color: var(--tn-blue); border: 1px solid rgba(122,162,247,0.3); }
.tag-magenta  { background: rgba(187,154,247,0.15); color: var(--tn-magenta); border: 1px solid rgba(187,154,247,0.3); }
.tag-cyan     { background: rgba(125,207,255,0.15); color: var(--tn-cyan); border: 1px solid rgba(125,207,255,0.3); }
.tag-orange   { background: rgba(255,158,100,0.15); color: var(--tn-orange); border: 1px solid rgba(255,158,100,0.3); }
.tag-green    { background: rgba(158,206,106,0.15); color: var(--tn-green); border: 1px solid rgba(158,206,106,0.3); }

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

.meter-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--tn-bg-hl);
    margin-top: 6px;
    overflow: hidden;
}
.meter-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────

for _key, _default in [
    ("analysis", None), ("graph_data", None), ("graph_stats", None),
    ("error", None), ("history", []), ("graph_version", 0),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ── Helpers ───────────────────────────────────────────────────────────

def risk_class(score: float) -> str:
    if score >= 0.65:
        return "risk-high"
    if score >= 0.35:
        return "risk-medium"
    return "risk-low"


def risk_label(score: float) -> str:
    if score >= 0.65:
        return "HIGH RISK"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def meter_color(score: float) -> str:
    if score >= 0.65:
        return "var(--tn-red)"
    if score >= 0.35:
        return "var(--tn-orange)"
    return "var(--tn-green)"


def _fetch_graph():
    """Fetch latest graph data + stats from the backend."""
    try:
        gr = requests.get(f"{API_BASE}/graph/data?max_phones=40", timeout=10)
        gr.raise_for_status()
        st.session_state.graph_data = gr.json()
    except Exception:
        pass
    try:
        gs = requests.get(f"{API_BASE}/graph/stats", timeout=10)
        gs.raise_for_status()
        st.session_state.graph_stats = gs.json()
    except Exception:
        pass
    st.session_state.graph_version += 1


def do_analysis(caller: str, callee: str, transcript: str):
    """Call /analyze then re-fetch the full graph and bump the render key."""
    st.session_state.error = None
    try:
        resp = requests.post(
            f"{API_BASE}/analyze",
            json={"caller": caller, "callee": callee, "transcript": transcript},
            timeout=15,
        )
        resp.raise_for_status()
        st.session_state.analysis = resp.json()

        st.session_state.history.insert(0, {
            "caller": caller,
            "risk": st.session_state.analysis["risk_score"],
            "persona": st.session_state.analysis["extraction"].get("persona", "—"),
        })
        if len(st.session_state.history) > 20:
            st.session_state.history = st.session_state.history[:20]

    except requests.exceptions.ConnectionError:
        st.session_state.error = "Cannot reach backend at " + API_BASE
        return
    except Exception as e:
        st.session_state.error = str(e)
        return

    _fetch_graph()


# ── Header ────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:0.25rem;">
    <span style="font-size:32px;">🛡️</span>
    <div>
        <h1 style="margin:0; font-size:28px; font-weight:700; color:#c0caf5; letter-spacing:-0.5px;">FRAUS</h1>
        <p style="margin:0; font-size:13px; color:#565f89; letter-spacing:1px;">REAL-TIME SCAM DETECTION ENGINE</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:4px; background:linear-gradient(90deg, #7aa2f7, #bb9af7, #f7768e); border-radius:2px; margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)


# ── Layout: two columns ──────────────────────────────────────────────

left_col, right_col = st.columns([5, 6], gap="large")


# ── LEFT COLUMN: Investigation Panel ─────────────────────────────────

with left_col:
    st.markdown('<p class="section-title">Active Investigation</p>', unsafe_allow_html=True)

    col_caller, col_callee = st.columns(2)
    with col_caller:
        caller = st.text_input("Caller", value="+12025551234", label_visibility="collapsed", placeholder="Caller phone")
    with col_callee:
        callee = st.text_input("Callee", value="+13105559876", label_visibility="collapsed", placeholder="Callee phone")

    transcript = st.text_area(
        "transcript_input",
        height=160,
        placeholder="Paste a live call transcript here…",
        label_visibility="collapsed",
    )

    st.button("⚡  Analyze Intent", on_click=do_analysis, args=(caller, callee, transcript), use_container_width=True)

    # Auto-fetch graph on first load so the visualization appears immediately
    if st.session_state.graph_data is None:
        _fetch_graph()

    if st.session_state.error:
        st.error(st.session_state.error)

    # ── Analysis results ──────────────────────────────────────────────

    a = st.session_state.analysis
    if a:
        score = a["risk_score"]
        cls = risk_class(score)
        lbl = risk_label(score)
        col = meter_color(score)

        st.markdown(f"""
        <div class="risk-card">
            <div class="risk-header">
                <span class="risk-title">Composite Risk Score</span>
                <span class="tag tag-{'red' if score >= 0.65 else 'orange' if score >= 0.35 else 'green'}">{lbl}</span>
            </div>
            <div class="risk-value {cls}">{score:.1%}</div>
            <div class="meter-bar"><div class="meter-fill" style="width:{score*100:.0f}%; background:{col};"></div></div>
        </div>
        """, unsafe_allow_html=True)

        ext = a["extraction"]

        # Score breakdown
        st.markdown(f"""
        <div class="risk-card">
            <p class="risk-title">Score Breakdown</p>
            <div class="stat-row">
                <div class="stat-box">
                    <div class="num" style="color:var(--tn-red);">{a['fraud_density']:.0%}</div>
                    <div class="lbl">Fraud Density</div>
                </div>
                <div class="stat-box">
                    <div class="num" style="color:var(--tn-orange);">{a['shared_account_score']:.0%}</div>
                    <div class="lbl">Shared Accounts</div>
                </div>
                <div class="stat-box">
                    <div class="num" style="color:var(--tn-magenta);">{a['persona_score']:.0%}</div>
                    <div class="lbl">Persona Match</div>
                </div>
                <div class="stat-box">
                    <div class="num" style="color:var(--tn-cyan);">{(a['gnn_fraud_prob'] or 0):.0%}</div>
                    <div class="lbl">GNN Score</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Extracted entities
        persona_tag = f'<span class="tag tag-magenta">{ext["persona"]}</span>' if ext.get("persona") else '<span class="tag tag-green">None detected</span>'
        intent_tag_cls = "tag-red" if ext.get("intent") == "potential_scam" else "tag-cyan"

        accounts_html = "".join(f'<span class="tag tag-blue">{ac}</span>' for ac in ext.get("bank_accounts", [])) or '<span style="color:var(--tn-comment); font-size:12px;">None</span>'
        phones_html = "".join(f'<span class="tag tag-cyan">{p.strip()}</span>' for p in ext.get("phone_numbers", [])) or '<span style="color:var(--tn-comment); font-size:12px;">None</span>'
        flags_html = "".join(f'<span class="tag tag-red">{f}</span>' for f in ext.get("risk_indicators", [])) or '<span style="color:var(--tn-comment); font-size:12px;">None</span>'

        st.markdown(f"""
        <div class="risk-card">
            <p class="risk-title">Extracted Entities</p>
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr><td style="color:var(--tn-comment); padding:6px 0; width:120px;">Persona</td><td>{persona_tag}</td></tr>
                <tr><td style="color:var(--tn-comment); padding:6px 0;">Intent</td><td><span class="tag {intent_tag_cls}">{ext.get('intent','—')}</span></td></tr>
                <tr><td style="color:var(--tn-comment); padding:6px 0;">Accounts</td><td>{accounts_html}</td></tr>
                <tr><td style="color:var(--tn-comment); padding:6px 0;">Phones</td><td>{phones_html}</td></tr>
                <tr><td style="color:var(--tn-comment); padding:6px 0; vertical-align:top;">Risk Flags</td><td>{flags_html}</td></tr>
            </table>
            <div style="margin-top:10px; font-size:11px; color:var(--tn-comment);">
                Extraction source: <span class="tag tag-cyan" style="font-size:10px;">{ext.get('source','—')}</span>
                &nbsp; Latency: <span style="color:var(--tn-green);">{a['latency_ms']:.1f}ms</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Recent investigations ──────────────────────────────────────────
    if st.session_state.history:
        st.markdown('<p class="section-title" style="margin-top:1.5rem;">Recent Investigations</p>', unsafe_allow_html=True)
        for h in st.session_state.history[:5]:
            r = h["risk"]
            c = risk_class(r)
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 12px; margin-bottom:4px; background:var(--tn-bg-dark); border-radius:6px; border:1px solid var(--tn-border); font-size:12px;">
                <span style="font-family:'JetBrains Mono',monospace; color:var(--tn-fg);">{h['caller']}</span>
                <span>{h['persona'] or '—'}</span>
                <span class="{c}" style="font-weight:700;">{r:.1%}</span>
            </div>
            """, unsafe_allow_html=True)


# ── RIGHT COLUMN: Network Graph ──────────────────────────────────────

with right_col:
    st.markdown('<p class="section-title">Network Graph</p>', unsafe_allow_html=True)

    # Graph stats bar
    gs = st.session_state.graph_stats
    if gs:
        st.markdown(f"""
        <div class="stat-row">
            <div class="stat-box"><div class="num">{gs.get('phone_number',0)}</div><div class="lbl">Phones</div></div>
            <div class="stat-box"><div class="num">{gs.get('bank_account',0)}</div><div class="lbl">Accounts</div></div>
            <div class="stat-box"><div class="num">{gs.get('persona',0)}</div><div class="lbl">Personas</div></div>
            <div class="stat-box"><div class="num">{gs.get('call_event',0)}</div><div class="lbl">Calls</div></div>
            <div class="stat-box"><div class="num">{gs.get('edges',0)}</div><div class="lbl">Edges</div></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Render graph ─────────────────────────────────────────────────
    gd = st.session_state.graph_data
    if gd and gd.get("nodes"):

        # Style maps — every node type is distinct
        NODE_CFG = {
            "phone_number": {"color": "#7aa2f7", "size": 12, "shape": "dot"},
            "bank_account": {"color": "#ff9e64", "size": 16, "shape": "square"},
            "persona":      {"color": "#bb9af7", "size": 20, "shape": "triangle"},
        }
        FRAUD_COLOR = "#ff4466"
        EDGE_COLOR  = "#5a6380"

        node_ids = {n["id"] for n in gd["nodes"]}

        nodes = []
        for n in gd["nodes"]:
            ntype = n["ntype"]
            is_fraud = n["fraud_label"] == "fraud"
            cfg = NODE_CFG.get(ntype, {"color": "#565f89", "size": 10, "shape": "dot"})
            color = FRAUD_COLOR if is_fraud else cfg["color"]
            size = cfg["size"] + 6 if is_fraud else cfg["size"]
            label = "" if ntype == "phone_number" else n["label"]

            nodes.append(Node(
                id=n["id"],
                label=label,
                title=n["label"],
                size=size,
                color=color,
                shape=cfg["shape"],
                font={"color": "#c0caf5", "size": 10, "strokeWidth": 2, "strokeColor": "#16161e"},
                borderWidth=3 if is_fraud else 1,
                borderWidthSelected=4,
            ))

        edges = []
        seen = set()
        for e in gd["edges"]:
            src, tgt = e["source"], e["target"]
            if src not in node_ids or tgt not in node_ids:
                continue
            pair = tuple(sorted([src, tgt]))
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(Edge(
                source=src,
                target=tgt,
                color=EDGE_COLOR,
                width=1.5,
            ))

        config = Config(
            width="100%",
            height=620,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor="#7dcfff",
            collapsible=False,
            node={"labelProperty": "label"},
            link={"highlightColor": "#7aa2f7", "renderLabel": False},
            backgroundColor="#16161e",
            key=f"fraud_graph_{st.session_state.graph_version}",
        )

        agraph(nodes=nodes, edges=edges, config=config)

        # Legend
        st.markdown("""
        <div style="display:flex; gap:20px; justify-content:center; margin-top:10px; font-size:12px; color:var(--tn-comment); flex-wrap:wrap;">
            <span><span style="color:#7aa2f7; font-size:14px;">●</span> Phone</span>
            <span><span style="color:#ff9e64; font-size:14px;">■</span> Account</span>
            <span><span style="color:#bb9af7; font-size:14px;">▲</span> Persona</span>
            <span><span style="color:#ff4466; font-size:14px;">●</span> Fraud-flagged</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:400px; background:var(--tn-bg-dark); border:1px dashed var(--tn-border);
                    border-radius:12px; color:var(--tn-comment);">
            <span style="font-size:48px; margin-bottom:12px;">🔗</span>
            <span style="font-size:14px;">Analyze a transcript to populate the graph</span>
            <span style="font-size:11px; margin-top:4px;">Nodes and edges will appear here after analysis</span>
        </div>
        """, unsafe_allow_html=True)
