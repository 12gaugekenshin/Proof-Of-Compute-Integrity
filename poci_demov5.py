import time, json, uuid, hashlib, random
from dataclasses import dataclass
from typing import Optional, List, Dict


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
    return x * 2


def create_event(x: int, parent_id: Optional[str], model_id: str) -> Event:
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
    return Proof(
        event_id=str(uuid.uuid4()),
        parent_id=None,
        model_id=model_id,
        hash="",
        signature="invalid",
        anchor_ref="INVALID",
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
    L_t = 1 - s_t
    state.theta += eta * (L_t - 0.5)
    state.w = lam * state.w + (1 - lam) * s_t
    return state


def ascii_bar(value: float, width: int = 30) -> str:
    value = max(0.0, min(1.0, value))
    n = int(value * width)
    return "#" * n + "-" * (width - n)


# =============================
# TWO-MODEL LONG-CHAIN DEMO
# =============================

if __name__ == "__main__":
    HONEST_ID = "honest_model"
    NOISY_ID = "noisy_model"
    MODEL_IDS = [HONEST_ID, NOISY_ID]

    N_STEPS = 100
    NOISY_ERROR_RATE = 0.15  # 15% bad proofs for noisy_model

    random.seed(123)

    trust: Dict[str, TrustState] = {
        HONEST_ID: TrustState(theta=0.0, w=1.0),
        NOISY_ID: TrustState(theta=0.0, w=1.0),
    }

    parents: Dict[str, Optional[str]] = {
        HONEST_ID: None,
        NOISY_ID: None,
    }

    all_proofs: List[Proof] = []

    history_w: Dict[str, List[float]] = {
        HONEST_ID: [],
        NOISY_ID: [],
    }

    history_s: Dict[str, List[float]] = {
        HONEST_ID: [],
        NOISY_ID: [],
    }

    history_type: Dict[str, List[str]] = {
        HONEST_ID: [],
        NOISY_ID: [],
    }

    print("=== PoCI Two-Model Long-Chain Demo (100 steps) ===")
    print("honest_model: 0% bad proofs")
    print("noisy_model:  15% bad proofs\n")

    for step in range(1, N_STEPS + 1):
        # ---- Honest model: always GOOD ----
        e_h = create_event(step, parents[HONEST_ID], HONEST_ID)
        p_h = generate_proof(e_h, HONEST_ID)
        all_proofs.append(p_h)
        parents[HONEST_ID] = e_h.event_id
        type_h = "GOOD"

        # ---- Noisy model: 15% BAD ----
        if random.random() < NOISY_ERROR_RATE:
            p_n = generate_bad_proof(NOISY_ID)
            type_n = "BAD "
        else:
            e_n = create_event(step, parents[NOISY_ID], NOISY_ID)
            p_n = generate_proof(e_n, NOISY_ID)
            parents[NOISY_ID] = e_n.event_id
            type_n = "GOOD"
        all_proofs.append(p_n)

        # Update consistency and trust for both
        for mid, etype in [(HONEST_ID, type_h), (NOISY_ID, type_n)]:
            s_t = compute_consistency_score(all_proofs, mid)
            trust[mid] = update_trust_state(trust[mid], s_t)

            history_s[mid].append(s_t)
            history_w[mid].append(trust[mid].w)
            history_type[mid].append(etype)

        # Print per-step summary
        print(
            f"step {step:03d} | "
            f"H: {type_h} s={history_s[HONEST_ID][-1]:.3f} w={history_w[HONEST_ID][-1]:.3f} | "
            f"N: {type_n} s={history_s[NOISY_ID][-1]:.3f} w={history_w[NOISY_ID][-1]:.3f}"
        )

    # =========================
    # FINAL SUMMARY
    # =========================
    print("\n=== FINAL STATS ===")
    for mid in MODEL_IDS:
        final_s = history_s[mid][-1]
        final_w = history_w[mid][-1]
        final_theta = trust[mid].theta
        n_bad = sum(1 for t in history_type[mid] if t.startswith("BAD"))
        print(f"\nModel: {mid}")
        print(f"  Bad proofs:        {n_bad} ({n_bad / N_STEPS * 100:.1f}%)")
        print(f"  Final consistency: {final_s:.3f}")
        print(f"  Final theta:       {final_theta:.3f}")
        print(f"  Final w:           {final_w:.3f}")

    # =========================
    # ASCII TRUST CURVES
    # =========================
    print("\n=== TRUST OVER TIME (w) ===")
    print("Index | honest_model                | noisy_model")
    for i in range(N_STEPS):
        w_h = history_w[HONEST_ID][i]
        w_n = history_w[NOISY_ID][i]
        bar_h = ascii_bar(w_h, 20)
        bar_n = ascii_bar(w_n, 20)
        print(f"{i+1:03d} | {w_h:.3f} {bar_h} | {w_n:.3f} {bar_n}")
