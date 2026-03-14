"""
MongoDB seeder — 1000 phone numbers total:
  - 50  scammers (fraud)
  - 950 victims  (benign)

Call patterns:
  - scammer → victim calls only (no victim → victim calls)
  - each scammer calls ~15 unique victims
  - shared bank accounts and personas per scam ring
"""

import random
import time
import uuid
from pymongo import MongoClient

# ── Config ────────────────────────────────────────────────────────────────────
MONGO_URI           = "mongodb://localhost:27017"
DB_NAME             = "scam_detector"
SEED                = 42

N_VICTIMS           = 1500
N_SCAMMERS          = 30
CALLS_PER_SCAMMER   = 20   # number of call events each scammer creates
VICTIMS_PER_CALL    = 3    # number of victims per call event (multiple victims per scam call)

N_FRAUD_RINGS       = 2    # scammers are grouped into rings of 10
ACCOUNTS_PER_RING   = 2

SCAM_PERSONAS = [
    "IRS Agent", "Tech Support", "Bank Officer",
    "Lottery Official", "Medicare Rep", "Utility Company",
    "Immigration Officer", "Crypto Advisor",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
random.seed(SEED)

def rand_phone():
    return f"+1{random.randint(2000000000, 9999999999)}"

def rand_account():
    return f"ACCT-{random.randint(100000, 999999)}"

def nid(ntype, value):
    return f"{ntype}::{value}"

def make_node(node_id, ntype, raw, label):
    return {
        "_id":        node_id,
        "ntype":      ntype,
        "raw":        raw,
        "label":      label,
        "created_at": time.time(),
        "transcript": "",
    }

def make_edge(src, dst, etype):
    return {"from": src, "to": dst, "etype": etype}

# ── Generate phones ───────────────────────────────────────────────────────────
print(f"Generating {N_VICTIMS} victims and {N_SCAMMERS} scammers…")

# Ensure no duplicate phone numbers
all_phones = random.sample(range(2000000000, 9999999999), N_VICTIMS + N_SCAMMERS)
victim_phones  = [f"+1{p}" for p in all_phones[:N_VICTIMS]]
scammer_phones = [f"+1{p}" for p in all_phones[N_VICTIMS:]]

nodes = {}
edges = []

# ── Victim nodes (no calls between victims) ───────────────────────────────────
for p in victim_phones:
    node_id = nid("phone_number", p)
    nodes[node_id] = make_node(node_id, "phone_number", p, "benign")

# ── Scam rings ────────────────────────────────────────────────────────────────
ring_size = N_SCAMMERS // N_FRAUD_RINGS  # 10 scammers per ring

for ring_idx in range(N_FRAUD_RINGS):
    ring_scammers = scammer_phones[ring_idx * ring_size : (ring_idx + 1) * ring_size]
    shared_accs   = [rand_account() for _ in range(ACCOUNTS_PER_RING)]
    persona_name  = SCAM_PERSONAS[ring_idx % len(SCAM_PERSONAS)]

    # Register persona node
    per_id = nid("persona", persona_name)
    if per_id not in nodes:
        nodes[per_id] = make_node(per_id, "persona", persona_name, "fraud")

    # Register shared bank accounts
    for acc in shared_accs:
        aid = nid("bank_account", acc)
        nodes[aid] = make_node(aid, "bank_account", acc, "fraud")

    # Register scammer phones
    for p in ring_scammers:
        pid = nid("phone_number", p)
        nodes[pid] = make_node(pid, "phone_number", p, "fraud")

        # Scammer owns the shared accounts
        for acc in shared_accs:
            aid = nid("bank_account", acc)
            edges.append(make_edge(pid, aid, "OWNS_ACCOUNT"))

    # (Call generation moved after fraud-ring loop to ensure every victim gets at least one scam call)

    print(f"  Ring {ring_idx+1}: {len(ring_scammers)} scammers, persona='{persona_name}', accounts={shared_accs}")

# ── Generate scam call events so every victim is involved in at least one scam call ─────────────────
print("Generating scam call events (ensuring each profile has at least one scam call)…")

all_scammers = scammer_phones[:]  # list of all fraud phones
victims_to_assign = victim_phones.copy()
random.shuffle(victims_to_assign)

# Create enough capacity to include all victims
total_call_capacity = len(all_scammers) * CALLS_PER_SCAMMER * VICTIMS_PER_CALL
if total_call_capacity < len(victims_to_assign):
    raise RuntimeError("Not enough call capacity to include every victim. Increase CALLS_PER_SCAMMER or VICTIMS_PER_CALL.")

# Assign victims across call events, ensuring each victim is included at least once
victims_iter = iter(victims_to_assign)

for p in all_scammers:
    pid = nid("phone_number", p)
    for _ in range(CALLS_PER_SCAMMER):
        call_id = f"call_event::{uuid.uuid4().hex[:12]}"
        nodes[call_id] = make_node(call_id, "call_event", call_id, "fraud")
        edges.append(make_edge(pid, call_id, "CALLED_FROM"))

        # Attach a persona and a fraud account to this call
        persona_name = random.choice(SCAM_PERSONAS)
        per_id = nid("persona", persona_name)
        if per_id not in nodes:
            nodes[per_id] = make_node(per_id, "persona", persona_name, "fraud")
        edges.append(make_edge(call_id, per_id, "USED_PERSONA"))

        acc = rand_account()
        aid = nid("bank_account", acc)
        if aid not in nodes:
            nodes[aid] = make_node(aid, "bank_account", acc, "fraud")
        edges.append(make_edge(call_id, aid, "MENTIONED_ACCOUNT"))

        # Link a small group of victims to this call
        for _ in range(VICTIMS_PER_CALL):
            try:
                victim = next(victims_iter)
            except StopIteration:
                # If we run out of uncovered victims, fall back to random victims
                victim = random.choice(victim_phones)
            vid = nid("phone_number", victim)
            edges.append(make_edge(call_id, vid, "CALLED_TO"))

    print(f"  Ring {ring_idx+1}: {len(ring_scammers)} scammers, persona='{persona_name}', accounts={shared_accs}")

# ── Write to MongoDB ──────────────────────────────────────────────────────────
print(f"\nTotal nodes : {len(nodes):,}")
print(f"Total edges : {len(edges):,}")
print("Writing to MongoDB…")

client = MongoClient(MONGO_URI)
db     = client[DB_NAME]

db.nodes.drop()
db.edges.drop()

BATCH = 500
node_list = list(nodes.values())
for i in range(0, len(node_list), BATCH):
    db.nodes.insert_many(node_list[i:i+BATCH], ordered=False)

for i in range(0, len(edges), BATCH):
    db.edges.insert_many(edges[i:i+BATCH], ordered=False)

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n── Verification ──────────────────────────────────────────────────────")
print(f"  phone_number (fraud)  : {db.nodes.count_documents({'ntype': 'phone_number', 'label': 'fraud'}):>6,}")
print(f"  phone_number (benign) : {db.nodes.count_documents({'ntype': 'phone_number', 'label': 'benign'}):>6,}")
print(f"  call_event nodes      : {db.nodes.count_documents({'ntype': 'call_event'}):>6,}")
print(f"  bank_account nodes    : {db.nodes.count_documents({'ntype': 'bank_account'}):>6,}")
print(f"  persona nodes         : {db.nodes.count_documents({'ntype': 'persona'}):>6,}")
print(f"  CALLED_FROM edges     : {db.edges.count_documents({'etype': 'CALLED_FROM'}):>6,}")
print(f"  CALLED_TO edges       : {db.edges.count_documents({'etype': 'CALLED_TO'}):>6,}")
print(f"  OWNS_ACCOUNT edges    : {db.edges.count_documents({'etype': 'OWNS_ACCOUNT'}):>6,}")
print(f"  MENTIONED_ACCOUNT     : {db.edges.count_documents({'etype': 'MENTIONED_ACCOUNT'}):>6,}")
print(f"\n  Total nodes           : {db.nodes.count_documents({}):>6,}")
print(f"  Total edges           : {db.edges.count_documents({}):>6,}")
print("\nDone ✓")