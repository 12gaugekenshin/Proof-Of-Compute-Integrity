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
# Model with Drift
# ============================================================

class DriftModel:
    def __init__(self, key="DRIFT_KEY", model_id="drift_model"):
        self.key = key
        self.model_id = model_id
        self.cheat_prob = 0.0  # will be adjusted across phases

    def sign(self, message):
        """
        With probability cheat_prob, emit a BAD proof
        by tampering the hash. Otherwise emit GOOD proof.
        """
        if random.random() < self.cheat_prob:
            bad_message = message[::-1]
            return f"{self.key}:{bad_message}"
        else:
            return f"{self.key}:{message}"

# ============================================================
# Adaptive Controller (single model)
# ============================================================

class Controller:
    def __init__(self):
        self.weight = 1.0
        self.theta = 1.0

    def update(self, valid: bool):
        if valid:
            self.weight = min(1.0, self.weight + 0.03)
            self.theta  = max(0.5, self.theta - 0.08)
        else:
            self.weight = max(0.0, self.weight - 0.10)
            self.theta  = min(5.0, self.theta + 0.25)

    def snapshot(self):
        return self.weight, self.theta

controller = Controller()

# ============================================================
# Step Object
# ============================================================

class Step:
    def __init__(self, index, phase, hash_value, signature, valid, cheat_prob):
        self.index = index
        self.phase = phase
        self.hash = hash_value
        self.signature = signature
        self.valid = valid
        self.cheat_prob = cheat_prob

# ============================================================
# Verification Logic
# ============================================================

MODEL_KEY = "DRIFT_KEY"

def verify_step(step: Step):
    message = step.hash
    valid = verify_signature(MODEL_KEY, step.signature, message)
    controller.update(valid)
    return valid

# ============================================================
# Phases
# ============================================================

def phase_1_stable(model, start_idx=0, steps=15):
    """
    Model is fully honest (cheat_prob=0.0).
    Builds strong trust baseline.
    """
    print("\n=== PHASE 1: STABLE HONEST BEHAVIOR ===")
    idx = start_idx
    history = []

    model.cheat_prob = 0.0

    for _ in range(steps):
        h = hash_step(idx)
        sig = model.sign(h)
        # Here, sign is always GOOD because cheat_prob=0
        temp_step = Step(idx, "stable", h, sig, True, model.cheat_prob)
        valid = verify_step(temp_step)
        w, t = controller.snapshot()
        print(f"[STABLE] step={idx:02d} | valid={valid} | cheat_prob={model.cheat_prob:.2f} "
              f"| weight={w:.2f}, theta={t:.2f}")
        history.append(temp_step)
        idx += 1

    return history, idx

def phase_2_drift(model, start_idx, steps=25, max_cheat_prob=0.7):
    """
    Model gradually becomes noisier / more compromised.
    cheat_prob ramps from 0.0 up to max_cheat_prob.
    """
    print("\n=== PHASE 2: DRIFT / DEGRADATION ===")
    idx = start_idx
    history = []

    for i in range(steps):
        # Linearly ramp cheat_prob from 0.0 → max_cheat_prob
        frac = i / max(1, steps - 1)
        model.cheat_prob = frac * max_cheat_prob

        h = hash_step(idx)
        sig = model.sign(h)
        temp_step = Step(idx, "drift", h, sig, None, model.cheat_prob)
        valid = verify_step(temp_step)
        temp_step.valid = valid

        w, t = controller.snapshot()
        label = "GOOD" if valid else "BAD"
        print(f"[DRIFT ] step={idx:02d} | {label:4s} | cheat_prob={model.cheat_prob:.2f} "
              f"| weight={w:.2f}, theta={t:.2f}")
        history.append(temp_step)
        idx += 1

    return history, idx

def phase_3_recovery(model, start_idx, steps=25):
    """
    Model gradually recovers: cheat_prob ramps back down to 0.0.
    Tests how forgiveness behaves and whether trust can be partially restored.
    """
    print("\n=== PHASE 3: RECOVERY ===")
    idx = start_idx
    history = []

    for i in range(steps):
        # Ramp down cheat_prob from current level back to 0
        # For simplicity, linearly from some high to 0.0
        frac = 1.0 - (i / max(1, steps - 1))
        # Assume it starts at ~0.7 like in drift end
        model.cheat_prob = frac * 0.7

        h = hash_step(idx)
        sig = model.sign(h)
        temp_step = Step(idx, "recovery", h, sig, None, model.cheat_prob)
        valid = verify_step(temp_step)
        temp_step.valid = valid

        w, t = controller.snapshot()
        label = "GOOD" if valid else "BAD"
        print(f"[RECOV] step={idx:02d} | {label:4s} | cheat_prob={model.cheat_prob:.2f} "
              f"| weight={w:.2f}, theta={t:.2f}")
        history.append(temp_step)
        idx += 1

    return history, idx

# ============================================================
# Main Runner
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    model = DriftModel()

    history = []
    idx = 0

    h1, idx = phase_1_stable(model, start_idx=idx, steps=15)
    history.extend(h1)

    h2, idx = phase_2_drift(model, start_idx=idx, steps=25, max_cheat_prob=0.7)
    history.extend(h2)

    h3, idx = phase_3_recovery(model, start_idx=idx, steps=25)
    history.extend(h3)

    w, t = controller.snapshot()
    print("\n=== FINAL CONTROLLER STATE ===")
    print(f"weight={w:.2f}, theta={t:.2f}")
    print("\n=== MODEL DRIFT TEST COMPLETE ===")
