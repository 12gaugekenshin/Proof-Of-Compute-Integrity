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
# Models
# ============================================================

class HonestModel:
    def __init__(self, key="HONEST_KEY"):
        self.key = key
        self.model_id = "honest"

    def sign(self, message):
        return f"{self.key}:{message}"

class ShadowModel:
    def __init__(self, key="SHADOW_KEY", cheat_prob=0.0):
        """
        cheat_prob: probability that shadow emits a BAD proof
        """
        self.key = key
        self.model_id = "shadow"
        self.cheat_prob = cheat_prob

    def sign(self, message):
        """
        GOOD: key:hash
        BAD:  key:tampered_hash (fails verification)
        """
        if random.random() < self.cheat_prob:
            bad_message = message[::-1]  # reverse hash = guaranteed invalid
            return f"{self.key}:{bad_message}"
        else:
            return f"{self.key}:{message}"

# ============================================================
# Per-Model Adaptive Controller
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
# Step Object
# ============================================================

class Step:
    def __init__(self, index, hash_value, signature, model_id, phase):
        self.index = index
        self.hash = hash_value
        self.signature = signature
        self.model_id = model_id
        self.phase = phase

# ============================================================
# Verification Logic
# ============================================================

MODEL_KEYS = {
    "honest": "HONEST_KEY",
    "shadow": "SHADOW_KEY"
}

def verify_step(step: Step):
    key = MODEL_KEYS[step.model_id]
    message = step.hash
    valid = verify_signature(key, step.signature, message)
    controller.update(step.model_id, valid)
    return valid

# ============================================================
# Test Phases
# ============================================================

def phase_1_bootstrap(honest, start_idx=0, steps=10):
    print("\n=== PHASE 1: HONEST BOOTSTRAP ===")
    idx = start_idx

    for _ in range(steps):
        h = hash_step(idx)
        sig = honest.sign(h)
        step = Step(idx, h, sig, "honest", "boot")
        valid = verify_step(step)
        w, t = controller.get("honest")
        print(f"[BOOT] step {idx} | honest | valid={valid} | weight={w:.2f}, theta={t:.2f}")
        idx += 1

    return idx

def phase_2_shadow_warmup(honest, shadow, start_idx, rounds=5):
    print("\n=== PHASE 2: SHADOW WARM-UP (Both behave) ===")
    idx = start_idx

    for _ in range(rounds):
        for model in (honest, shadow):
            h = hash_step(idx)
            sig = model.sign(h)
            step = Step(idx, h, sig, model.model_id, "warmup")
            valid = verify_step(step)
            w, t = controller.get(model.model_id)
            print(f"[WARMUP] step {idx} | {model.model_id} | valid={valid} "
                  f"| weight={w:.2f}, theta={t:.2f}")
            idx += 1

    return idx

def phase_3_shadow_attack(honest, shadow, start_idx, rounds=10, cheat_prob=0.5):
    print("\n=== PHASE 3: SHADOW ATTACK (Oscillation) ===")
    idx = start_idx

    shadow.cheat_prob = cheat_prob
    shadow_good = 0
    shadow_bad = 0

    for _ in range(rounds):
        for model in (honest, shadow):
            h = hash_step(idx)
            sig = model.sign(h)
            step = Step(idx, h, sig, model.model_id, "attack")
            valid = verify_step(step)
            w, t = controller.get(model.model_id)

            # Track shadow's actual behavior
            if model.model_id == "shadow":
                if valid:
                    shadow_good += 1
                    label = "GOOD"
                else:
                    shadow_bad += 1
                    label = "BAD"
                print(f"[ATTACK] step {idx} | shadow | {label} | weight={w:.2f}, theta={t:.2f}")
            else:
                print(f"[ATTACK] step {idx} | honest | valid={valid} "
                      f"| weight={w:.2f}, theta={t:.2f}")

            idx += 1

    print(f"\nShadow results: GOOD={shadow_good}, BAD={shadow_bad}")
    return idx

# ============================================================
# Main Runner
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    honest = HonestModel()
    shadow = ShadowModel()

    idx = 0
    idx = phase_1_bootstrap(honest, start_idx=idx, steps=10)
    idx = phase_2_shadow_warmup(honest, shadow, start_idx=idx, rounds=5)
    idx = phase_3_shadow_attack(honest, shadow, start_idx=idx, rounds=10, cheat_prob=0.5)

    controller.summary()
    print("\n=== SHADOW MODEL TEST COMPLETE ===")
