import time, json, uuid, hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict
from collections import defaultdict

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
    theta: float
    w: float

def fake_model(x: int) -> int:
    return x * 2

def create_event(x, parent_id, model_id):
    return Event(
        event_id=str(uuid.uuid4()),
        parent_id=parent_id,
        payload={"input": x, "output": fake_model(x), "model_id": model_id},
        timestamp=time.time()
    )

def hash_event(event):
    data = json.dumps({
        "event_id": event.event_id,
        "parent_id": event.parent_id,
        "payload": event.payload,
        "timestamp": event.timestamp
    }, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()

def fake_sign(h, model_id):
    return hashlib.sha256((model_id + h).encode()).hexdigest()

def mock_anchor(h):
    return "kaspa_tx_" + h[:12]

def generate_proof(event, model_id):
    h = hash_event(event)
    return Proof(
        event_id=event.event_id,
        parent_id=event.parent_id,
        model_id=model_id,
        hash=h,
        signature=fake_sign(h, model_id),
        anchor_ref=mock_anchor(h),
        timestamp=time.time()
    )

def bad_proof(model_id):
    return Proof(
        event_id=str(uuid.uuid4()),
        parent_id=None,
        model_id=model_id,
        hash="",
        signature="bad",
        anchor_ref="INVALID",
        timestamp=time.time()
    )

def consistency(proofs, mid):
    relevant = [p for p in proofs if p.model_id == mid]
    if not relevant: return 1.0
    good = sum(1 for p in relevant if p.hash and p.anchor_ref.startswith("kaspa_tx_"))
    return good / len(relevant)

def update(state, s):
    L = 1 - s
    state.theta += 0.1 * (L - 0.5)
    state.w = 0.9 * state.w + 0.1 * s
    return state

def cycle(label, proofs, trust, mids):
    print(f"\n=== {label} ===")
    for mid in mids:
        s = consistency(proofs, mid)
        trust[mid] = update(trust[mid], s)
        print(f"{mid}: consistency={s:.3f} | theta={trust[mid].theta:.3f} | w={trust[mid].w:.3f}")

if __name__ == "__main__":
    honest = "honest_model"
    bad = "malicious_model"
    mids = [honest, bad]

    trust = {
        honest: TrustState(0,1),
        bad: TrustState(0,1)
    }

    parents = {honest: None, bad: None}
    proofs = []

    # Step 1: both honest
    for mid,x in [(honest,1),(bad,10)]:
        e = create_event(x, parents[mid], mid)
        parents[mid] = e.event_id
        proofs.append(generate_proof(e, mid))
    cycle("Step 1 (both honest)", proofs, trust, mids)

    # Step 2: honest OK, bad lies
    e = create_event(2, parents[honest], honest)
    parents[honest] = e.event_id
    proofs.append(generate_proof(e, honest))
    proofs.append(bad_proof(bad))
    cycle("Step 2 (bad lies)", proofs, trust, mids)

    # Step 3: honest OK, bad lies again
    e = create_event(3, parents[honest], honest)
    parents[honest] = e.event_id
    proofs.append(generate_proof(e, honest))
    proofs.append(bad_proof(bad))
    cycle("Step 3 (bad lies again)", proofs, trust, mids)

    # Step 4: both honest
    for mid,x in [(honest,4),(bad,20)]:
        e = create_event(x, parents[mid], mid)
        parents[mid] = e.event_id
        proofs.append(generate_proof(e, mid))
    cycle("Step 4 (recovery)", proofs, trust, mids)

    # Step 5: bad lies again
    e = create_event(5, parents[honest], honest)
    parents[honest] = e.event_id
    proofs.append(generate_proof(e, honest))
    proofs.append(bad_proof(bad))
    cycle("Step 5 (bad lies again)", proofs, trust, mids)

    print("\n=== FINAL STATS ===")
    for mid in mids:
        s = consistency(proofs, mid)
        st = trust[mid]
        print(f"{mid}: final consistency={s:.3f} | theta={st.theta:.3f} | w={st.w:.3f}")
