import hashlib
import random

# ============================================================
# Utility Functions
# ============================================================

def hash_step(step_index):
    """Deterministic hash for the event."""
    return hashlib.sha256(f"step-{step_index}".encode()).hexdigest()

def verify_signature(model_key, signature, message):
    """Simulated signature verification."""
    return signature == f"{model_key}:{message}"

# ============================================================
# Model
# ============================================================

class HonestModel:
    def __init__(self, key="HONEST_KEY"):
        self.key = key
        self.model_id = "honest"

    def sign(self, message):
        return f"{self.key}:{message}"

# ============================================================
# Adaptive Controller (per-model)
# ============================================================

class PerModelController:
    def __init__(self):
        self.state = {}  # model_id -> {weight, theta}

    def _ensure(self, model_id):
        if model_id not in self.state:
            self.state[model_id] = {"weight": 1.0, "theta": 1.0}

    def update(self, model_id, valid):
        self._ensure(model_id)
        m = self.state[model_id]

        if valid:
            m["weight"] = min(1.0, m["weight"] + 0.05)
            m["theta"]  = max(0.5, m["theta"] - 0.1)
        else:
            m["weight"] = max(0.0, m["weight"] - 0.1)
            m["theta"]  = min(5.0, m["theta"] + 0.3)

    def get(self, model_id):
        self._ensure(model_id)
        m = self.state[model_id]
        return m["weight"], m["theta"]

    def summary(self):
        print("\n=== CONTROLLER SUMMARY ===")
        for mid, m in self.state.items():
            print(f"Model '{mid}': weight={m['weight']:.2f}, theta={m['theta']:.2f}")

controller = PerModelController()

# ============================================================
# Step Object (with timestamp)
# ============================================================

class Step:
    def __init__(self, index, hash_value, signature, model_id, phase, timestamp):
        self.index = index
        self.hash = hash_value
        self.signature = signature
        self.model_id = model_id
        self.phase = phase
        self.timestamp = timestamp

    def __repr__(self):
        return (f"Step {self.index} [{self.phase}] "
                f"model={self.model_id} t={self.timestamp} "
                f"hash={self.hash[:8]}…")

# ============================================================
# Timing + Replay Verification Logic
# ============================================================

MODEL_KEYS = {"honest": "HONEST_KEY"}

# Per-model last timestamp
last_timestamp = {}  # model_id -> last_seen_timestamp

# Replay protection: store used (model_id, hash, signature) tuples
used_proofs = set()

# Timing constraints
MAX_FUTURE_DRIFT = 30    # max seconds allowed ahead of global time
MAX_BACKWARD_DRIFT = 10  # max seconds allowed behind last timestamp

def verify_step(step: Step, global_time):
    """
    Verify:
      - signature valid
      - no replay
      - timestamp not too far in future
      - timestamp not too far back compared to last seen for this model
    """
    model_id = step.model_id
    key = MODEL_KEYS[model_id]
    message = step.hash

    # 1) Signature check
    sig_valid = verify_signature(key, step.signature, message)
    if not sig_valid:
        controller.update(model_id, False)
        print(f"[FAIL] {step} | reason=BAD_SIGNATURE")
        return False

    # 2) Replay check
    proof_id = (model_id, step.hash, step.signature)
    if proof_id in used_proofs:
        controller.update(model_id, False)
        print(f"[FAIL] {step} | reason=REPLAY_DETECTED")
        return False

    # 3) Future timestamp check
    if step.timestamp > global_time + MAX_FUTURE_DRIFT:
        controller.update(model_id, False)
        print(f"[FAIL] {step} | reason=TIMESTAMP_TOO_FAR_IN_FUTURE")
        return False

    # 4) Backward timestamp / monotonicity check
    last_t = last_timestamp.get(model_id, None)
    if last_t is not None:
        if step.timestamp + MAX_BACKWARD_DRIFT < last_t:
            controller.update(model_id, False)
            print(f"[FAIL] {step} | reason=TIMESTAMP_BACKDATED")
            return False

    # If all good:
    used_proofs.add(proof_id)
    last_timestamp[model_id] = step.timestamp
    controller.update(model_id, True)
    w, t = controller.get(model_id)
    print(f"[OK]   {step} | weight={w:.2f}, theta={t:.2f}")
    return True

# ============================================================
# Phases
# ============================================================

def phase_1_normal_timeline(model, start_index=0, start_time=1000, steps=5, dt=10):
    """
    Honest steps, strictly increasing timestamps.
    """
    print("\n=== PHASE 1: NORMAL TIMELINE ===")
    idx = start_index
    t = start_time
    for _ in range(steps):
        h = hash_step(idx)
        sig = model.sign(h)
        step = Step(idx, h, sig, model.model_id, "normal", t)
        verify_step(step, global_time=t)
        idx += 1
        t += dt
    return idx, t

def phase_2_replay_attack(model, replay_index, replay_time):
    """
    Reuse an old signature/hash at a new time and/or index.
    """
    print("\n=== PHASE 2: REPLAY ATTACK ===")
    # Simulate we have the original step hash & sig from history
    h = hash_step(replay_index)
    sig = model.sign(h)  # same as before
    # Create a new step with a new index pretending it's fresh
    fake_index = replay_index + 100
    step = Step(fake_index, h, sig, model.model_id, "replay", replay_time)
    verify_step(step, global_time=replay_time)

def phase_3_backdated_attack(model, next_index, last_time):
    """
    Timestamp significantly earlier than last_timestamp[model].
    """
    print("\n=== PHASE 3: BACKDATED ATTACK ===")
    # Create a step with a time way in the past
    backdated_time = last_time - 100  # way beyond MAX_BACKWARD_DRIFT
    h = hash_step(next_index)
    sig = model.sign(h)
    step = Step(next_index, h, sig, model.model_id, "backdated", backdated_time)
    verify_step(step, global_time=last_time)  # global time is still last_time

def phase_4_future_attack(model, next_index, last_time):
    """
    Timestamp way too far in the future compared to global_time.
    """
    print("\n=== PHASE 4: FUTURE TIMESTAMP ATTACK ===")
    future_time = last_time + 1000  # way beyond MAX_FUTURE_DRIFT
    h = hash_step(next_index)
    sig = model.sign(h)
    step = Step(next_index, h, sig, model.model_id, "future", future_time)
    verify_step(step, global_time=last_time)

# ============================================================
# Main Runner
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    honest = HonestModel()

    # Phase 1: Normal timeline, honest behavior
    idx, current_time = phase_1_normal_timeline(
        honest, start_index=0, start_time=1000, steps=5, dt=10
    )

    # Phase 2: Replay attack – reusing proof from step 2 at later time
    phase_2_replay_attack(honest, replay_index=2, replay_time=current_time + 5)

    # Phase 3: Backdated attack – timestamp way before last_timestamp
    phase_3_backdated_attack(honest, next_index=idx, last_time=current_time)

    # Phase 4: Future attack – timestamp way too far ahead
    phase_4_future_attack(honest, next_index=idx + 1, last_time=current_time)

    controller.summary()
    print("\n=== TIMING + REPLAY TEST COMPLETE ===")
