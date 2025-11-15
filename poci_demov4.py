import time, json, uuid, hashlib, random
from dataclasses import dataclass
from typing import Optional, List


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


def create_event(x: int, parent_id=None, model_id="model") -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        parent_id=parent_id,
        payload={"input": x, "output": fake_model(x), "model_id": model_id},
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


def generate_bad_proof(model_id: str) -> Proof:
    """Simulate a malformed / dishonest proof with no real event."""
    return Proof(
        event_id=str(uuid.uuid4()),
        parent_id=None,
        model_id=model_id,
        hash="",                    # missing hash
        signature="invalid",
        anchor_ref="INVALID",       # bad anchor
        timestamp=time.time()
    )


# =============================
# CONSISTENCY + TRUST UPDATE
# =============================

def compute_consistency_score(proofs: List[Proof], model_id: str) -> float:
    relevant = [p for p in proofs if p.model_id == model_id]
    if not relevant:
        return 1.0
    valid = 0
    for p in relevant:
        if p.hash and p.anchor_ref.startswith("kaspa_tx_"):
            valid += 1
    return valid / len(relevant)


def update_trust_state(state: TrustState, s_t: float,
                       eta: float = 0.1, lam: float = 0.9) -> TrustState:
    """
    Very simple ACE/AFL-style update:
      L_t = 1 - s_t
      theta += eta * (L_t - 0.5)
      w = lam * w + (1 - lam) * s_t
    """
    L_t = 1 - s_t
    state.theta += eta * (L_t - 0.5)
    state.w = lam * state.w + (1 - lam) * s_t
    return state


def ascii_bar(value: float, width: int = 30) -> str:
    """Make a simple bar for trust visualization."""
    n = int(max(0.0, min(1.0, value)) * width)
    return "#" * n + "-" * (width - n)


# =============================
# LONG-CHAIN DEMO (100 EVENTS, ~15% ERRORS)
# =============================

if __name__ == "__main__":
    MODEL_ID = "longchain_model"
    N_EVENTS = 100
    ERROR_RATE = 0.15   # 15% of steps will be bad proofs

    trust = TrustState(theta=0.0, w=1.0)
    parent_id = None
    all_proofs: List[Proof] = []

    history_s = []
    history_w = []
    history_theta = []
    history_type = []  # "GOOD" or "BAD"

    random.seed(42)  # deterministic for reproducible demo

    print("=== PoCI Long-Chain Demo (100 events, 15% bad proofs) ===")

    for step in range(1, N_EVENTS + 1):
        is_bad = (random.random() < ERROR_RATE)

        if not is_bad:
            # Honest event
            e = create_event(step, parent_id, MODEL_ID)
            p = generate_proof(e, MODEL_ID)
            all_proofs.append(p)
            parent_id = e.event_id
            event_type = "GOOD"
        else:
            # Malformed / dishonest proof (no new event in chain)
            p = generate_bad_proof(MODEL_ID)
            all_proofs.append(p)
            # parent_id unchanged
            event_type = "BAD "

        s_t = compute_consistency_score(all_proofs, MODEL_ID)
        trust = update_trust_state(trust, s_t)

        history_s.append(s_t)
        history_w.append(trust.w)
        history_theta.append(trust.theta)
        history_type.append(event_type)

        print(
            f"step {step:03d} | type={event_type} | "
            f"s={s_t:.3f} | theta={trust.theta:.3f} | w={trust.w:.3f}"
        )

    # =========================
    # FINAL SUMMARY
    # =========================
    print("\n=== FINAL STATS ===")
    final_s = history_s[-1]
    final_w = history_w[-1]
    final_theta = history_theta[-1]
    n_bad = sum(1 for t in history_type if t.startswith("BAD"))
    print(f"Total events: {N_EVENTS}")
    print(f"Bad proofs:   {n_bad} ({n_bad / N_EVENTS * 100:.1f}%)")
    print(f"Final consistency: {final_s:.3f}")
    print(f"Final theta (strictness): {final_theta:.3f}")
    print(f"Final w (trust weight):   {final_w:.3f}")

    # Simple ASCII visualization of trust over time
    print("\n=== TRUST OVER TIME (w) ===")
    for i, w_val in enumerate(history_w, start=1):
        bar = ascii_bar(w_val, width=40)
        print(f"{i:03d} | {w_val:.3f} | {bar}")
