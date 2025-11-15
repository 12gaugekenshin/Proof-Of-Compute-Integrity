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
# Model Classes
# ============================================================

class HonestModel:
    def __init__(self, key="HONEST_KEY"):
        self.key = key
        self.model_id = "honest"

    def sign(self, message):
        return f"{self.key}:{message}"

class ShadowModel:
    def __init__(self, model_id, key, cheat_prob=0.0):
        """
        model_id: unique ID, e.g. 'shadow_0'
        key: unique key per shadow
        cheat_prob: probability [0,1] that this model emits a BAD proof
        """
        self.key = key
        self.model_id = model_id
        self.cheat_prob = cheat_prob

    def sign(self, message):
        """
        GOOD: key:hash
        BAD:  key:tampered_hash (fails verification)
        """
        if random.random() < self.cheat_prob:
            bad_message = message[::-1]  # reverse hash = invalid
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
            m["weight"] = min(1.0, m["weight"] + 0.03)
            m["theta"]  = max(0.5, m["theta"] - 0.08)
        else:
            m["weight"] = max(0.0, m["weight"] - 0.12)
            m["theta"]  = min(5.0, m["theta"] + 0.35)

    def get(self, model_id):
        self._ensure(model_id)
        m = self.state[model_id]
        return m["weight"], m["theta"]

    def summary(self):
        print("\n=== CONTROLLER SUMMARY ===")
        for mid, m in sorted(self.state.items()):
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

MODEL_KEYS = {}  # filled dynamically

def verify_step(step: Step):
    key = MODEL_KEYS[step.model_id]
    message = step.hash
    valid = verify_signature(key, step.signature, message)
    controller.update(step.model_id, valid)
    return valid

# ============================================================
# Phases
# ============================================================

def phase_1_bootstrap(honest, start_idx=0, steps=10):
    print("\n=== PHASE 1: HONEST BOOTSTRAP ===")
    idx = start_idx
    for _ in range(steps):
        h = hash_step(idx)
        sig = honest.sign(h)
        step = Step(idx, h, sig, honest.model_id, "boot")
        valid = verify_step(step)
        w, t = controller.get(honest.model_id)
        print(f"[BOOT] step {idx} | honest   | valid={valid} "
              f"| weight={w:.2f}, theta={t:.2f}")
        idx += 1
    return idx

def phase_2_sybil_warmup(honest, shadows, start_idx, rounds=5):
    """
    Honest + all shadows behave correctly.
    Shadows gain trust as a group.
    """
    print("\n=== PHASE 2: SYBIL WARM-UP (all behave) ===")
    idx = start_idx

    for _ in range(rounds):
        # honest step
        h = hash_step(idx)
        sig = honest.sign(h)
        step = Step(idx, h, sig, honest.model_id, "warmup")
        valid = verify_step(step)
        w, t = controller.get(honest.model_id)
        print(f"[WARMUP] step {idx} | honest   | valid={valid} "
              f"| weightFrank={w:.2f}, theta={t:.2f}")
        idx += 1

        # each shadow in turn
        for shadow in shadows:
            h = hash_step(idx)
            sig = shadow.sign(h)
            step = Step(idx, h, sig, shadow.model_id, "warmup")
            valid = verify_step(step)
            w, t = controller.get(shadow.model_id)
            print(f"[WARMUP] step {idx} | {shadow.model_id:8} | valid={valid} "
                  f"| weight={w:.2f}, theta={t:.2f}")
            idx += 1

    return idx

def phase_3_sybil_attack(honest, shadows, start_idx, rounds=10, base_cheat_prob=0.5):
    """
    Sybil attack:
      - In each round, pick one "designated cheater" shadow.
      - That one cheats with high probability.
      - Others lower cheat prob, trying to look good and prop up the cluster.
    """
    print("\n=== PHASE 3: SYBIL GROUP ATTACK (colluding shadows) ===")
    idx = start_idx

    # stats
    stats = {s.model_id: {"GOOD": 0, "BAD": 0} for s in shadows}

    for r in range(rounds):
        print(f"\n--- ROUND {r} ---")

        # Honest always acts first, always good
        h = hash_step(idx)
        sig = honest.sign(h)
        step = Step(idx, h, sig, honest.model_id, "attack")
        valid = verify_step(step)
        w, t = controller.get(honest.model_id)
        print(f"[ATTACK] step {idx} | honest   | valid={valid} "
              f"| weight={w:.2f}, theta={t:.2f}")
        idx += 1

        # Pick one shadow to be the main cheater this round
        cheater = random.choice(shadows)

        for shadow in shadows:
            h = hash_step(idx)

            # Collusion logic:
            # - cheater: high cheat probability this round
            # - others: low cheat probability (or 0) to appear "good"
            if shadow is cheater:
                shadow.cheat_prob = base_cheat_prob
            else:
                shadow.cheat_prob = 0.05  # small chance of "noise"

            sig = shadow.sign(h)
            step = Step(idx, h, sig, shadow.model_id, "attack")
            valid = verify_step(step)
            w, t = controller.get(shadow.model_id)

            label = "GOOD" if valid else "BAD"
            if valid:
                stats[shadow.model_id]["GOOD"] += 1
            else:
                stats[shadow.model_id]["BAD"] += 1

            print(f"[ATTACK] step {idx} | {shadow.model_id:8} | {label} "
                  f"| weight={w:.2f}, theta={t:.2f}")
            idx += 1

    print("\n--- SYBIL SHADOW STATS ---")
    for mid, s in stats.items():
        print(f"{mid}: GOOD={s['GOOD']}, BAD={s['BAD']}")

    return idx

# ============================================================
# Main Runner
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    # Create honest model
    honest = HonestModel()
    MODEL_KEYS[honest.model_id] = honest.key

    # Create a group of shadows
    num_shadows = 3  # bump to 5 or 10 if you want
    shadows = []
    for i in range(num_shadows):
        mid = f"shadow_{i}"
        key = f"SHADOW_KEY_{i}"
        sm = ShadowModel(model_id=mid, key=key, cheat_prob=0.0)
        shadows.append(sm)
        MODEL_KEYS[mid] = key

    idx = 0
    idx = phase_1_bootstrap(honest, start_idx=idx, steps=10)
    idx = phase_2_sybil_warmup(honest, shadows, start_idx=idx, rounds=5)
    idx = phase_3_sybil_attack(honest, shadows, start_idx=idx, rounds=10, base_cheat_prob=0.6)

    controller.summary()
