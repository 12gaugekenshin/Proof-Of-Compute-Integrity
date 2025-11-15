import time, json, uuid, hashlib
from dataclasses import dataclass
from typing import Optional, List
from collections import defaultdict


# =============================
# DATA STRUCTURES
# =============================

@dataclass
class Event:
    event_id: str
    parent_id: Optional[str]
    payload: dict
    timestamp: float


@dataclass
class Proof:
    event_id: str
    parent_id: Optional[str]
    model_id: str
    hash: str
    signature: str
    anchor_ref: str
    timestamp: float


@dataclass
class TrustState:
    theta: float   # strictness
    w: float       # trust weight


# =============================
# EVENT CREATION / PROOFING
# =============================

def fake_model(x: int) -> int:
    """Our pretend AI model"""
    return x * 2


def create_event(x: int, parent_id=None) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        parent_id=parent_id,
        payload={"input": x, "output": fake_model(x)},
        timestamp=time.time()
    )


def hash_event(event: Event) -> str:
    data = json.dumps({
        "event_id": event.event_id,
        "parent_id": event.parent_id,
        "payload": event.payload,
        "timestamp": event.timestamp,
    }, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def fake_sign(h: str, model_id: str) -> str:
    return hashlib.sha256((model_id + h).encode()).hexdigest()


def mock_anchor_to_kaspa(h: str) -> str:
    return "kaspa_tx_" + h[:12]


def generate_proof(event: Event, model_id: str) -> Proof:
    h = hash_event(event)
    sig = fake_sign(h, model_id)
    anchor = mock_anchor_to_kaspa(h)

    return Proof(
        event_id=event.event_id,
        parent_id=event.parent_id,
        model_id=model_id,
        hash=h,
        signature=sig,
        anchor_ref=anchor,
        timestamp=time.time()
    )


def generate_bad_proof(model_id="model_pubkey_1") -> Proof:
    """Simulate a dishonest or malformed proof."""
    return Proof(
        event_id=str(uuid.uuid4()),
        parent_id=None,
        model_id=model_id,
        hash="",                           # missing hash
        signature="invalid_signature",      # bad signature
        anchor_ref="INVALID",               # bad anchor
        timestamp=time.time()
    )


# =============================
# LINEAGE GRAPH
# =============================

def build_lineage_graph(proofs: List[Proof]):
    children = defaultdict(list)
    by_id = {}

    for p in proofs:
        by_id[p.event_id] = p
        if p.parent_id:
            children[p.parent_id].append(p.event_id)

    return by_id, children


# =============================
# VERIFIER + CONSISTENCY
# =============================

def compute_consistency_score(proofs: List[Proof], model_id: str):
    relevant = [p for p in proofs if p.model_id == model_id]
    if not relevant:
        return 1.0

    valid = 0
    for p in relevant:
        if p.hash and p.anchor_ref.startswith("kaspa_tx_"):
            valid += 1

    return valid / len(relevant)


def update_trust_state(state: TrustState, s_t: float,
                       eta=0.1, lam=0.9):

    L_t = 1 - s_t
    state.theta += eta * (L_t - 0.5)
    state.w = lam * state.w + (1 - lam) * s_t
    return state


def verifier_cycle(proofs: List[Proof], state: TrustState, model_id: str, label=""):
    s_t = compute_consistency_score(proofs, model_id)
    state = update_trust_state(state, s_t)

    print(f"\n=== {label} ===")
    print(f"Consistency: {s_t:.3f}")
    print(f"theta (strictness): {state.theta:.3f}")
    print(f"w (trust weight):   {state.w:.3f}")

    return state


# =============================
# DEMO — MIXED EVENTS
# =============================

if __name__ == "__main__":
    model_id = "model_pubkey_1"
    trust = TrustState(theta=0.0, w=1.0)
    all_proofs = []

    parent = None

    # 1: Honest sequence of 3 events
    for i in [3, 4, 5]:
        e = create_event(i, parent)
        p = generate_proof(e, model_id)
        all_proofs.append(p)
        parent = e.event_id
        trust = verifier_cycle(all_proofs, trust, model_id, f"Honest Event (input={i})")

    # 2: Inject a bad proof
    bad = generate_bad_proof(model_id)
    all_proofs.append(bad)
    trust = verifier_cycle(all_proofs, trust, model_id, "BAD Event (malformed proof)")

    # 3: Recover with honest events
    for i in [6, 7]:
        e = create_event(i, parent)
        p = generate_proof(e, model_id)
        all_proofs.append(p)
        parent = e.event_id
        trust = verifier_cycle(all_proofs, trust, model_id, f"Recovery Honest Event (input={i})")

    # 4: Another bad proof
    bad2 = generate_bad_proof(model_id)
    all_proofs.append(bad2)
    trust = verifier_cycle(all_proofs, trust, model_id, "BAD Event #2 (malformed proof)")

    # 5: Final honest event
    e = create_event(8, parent)
    p = generate_proof(e, model_id)
    all_proofs.append(p)
    trust = verifier_cycle(all_proofs, trust, model_id, f"Final Honest Event (input=8)")

    # Print graph
    print("\n=== FINAL LINEAGE GRAPH ===")
    by_id, children = build_lineage_graph(all_proofs)
    print("Nodes:", list(by_id.keys()))
    print("Edges:", dict(children))
