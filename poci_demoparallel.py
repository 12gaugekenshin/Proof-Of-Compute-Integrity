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
        # Always correct
        return f"{self.key}:{message}"

class ShadowModel:
    def __init__(self, key="SHADOW_KEY", cheat_prob=0.0):
        """
        cheat_prob: probability in [0,1] that the model will emit a BAD proof
        """
        self.key = key
        self.model_id = "shadow"
        self.cheat_prob = cheat_prob

    def sign(self, message):
        """
        If behaving, sign correctly with its own key.
        If cheating, either corrupt the message or use a wrong signature.
        """
        if random.random() < self.cheat_prob:
            # BAD behavior: tamper with hash or send nonsense
            bad_message = message[::-1]  # reversed hash, won't verify
            return f"{self.key}:{bad_message}"
        else:
            # GOOD behavior for shadow (but still checked against its own key)
            return f"{self.key}:{message}"

# ============================================================
# Per-Model Adaptive Controller
# ============================================================

class PerModelController:
    def __init__(self):
        # Each model_id -> {"weight": float, "theta": float}
        self.state = {}

    def _ensure_model(self, model_id):
        if model_id not in self.state:
            self.state[model_id] = {"weight": 1.0, "theta": 1.0}

    def update(self, model_id, valid):
        self._ensure_model(model_id)
        s = self.state[model_id]

        if valid:
            s["weight"] = min(1.0, s["weight"] + 0.05)
            s["theta"]  = max(0.5, s["theta"]  - 0.1)
        else:
            s["weight"] = max(0.0, s["weight"] - 0.1)
            s["theta"]  = min(5.0, s["theta"]  + 0.3)

    def get(self, model_id):
        self._ensure_model(model_id)
        s = self.state[model_id]
        return s["weight"], s["theta"]

    def summary(self):
        lines = ["\n=== CONTROLLER SUMMARY (per model) ==="]
        for mid, s in self.state.items():
            lines.append(
                f"Model '{mid}': weight={s['weight']:.2f}, theta={s['theta']:.2f}"
            )
        return "\n".join(lines)

controller = PerModelController()

# ============================================================
# Step Structure
# ============================================================

class Step:
    def __init__(self, index, hash_value, signature, model_id, phase):
        self.index = index
        self.hash = hash_value
        self.signature = signature
        self.model_id = model_id
        self.phase = phase  # e.g. "boot", "warmup", "attack"

    def __repr__(self):
        return (f"Step {self.index} [{self.phase}] "
                f"model={self.model_id} hash={self.hash[:8]}…")

# ============================================================
# Verification Logic
# ============================================================

MODEL_KEYS = {
    "honest": "HONEST_KEY",
    "shadow": "SHADOW_KEY",
}

def verify_step(step: Step):
    """Verify a single step against its own model key."""
    key = MODEL_KEYS[step.model_id]
    message = step.hash
    valid = verify_signature(key, step.signature, message)
    controller.update(step.model_id, valid)
    return valid

# ============================================================
# Scenario Phases
# ============================================================

def run_phase_bootstrap(honest, start_idx=0, steps=20):
    """
    Phase 1: Only the honest model produces steps.
    Purpose: establish a strong baseline trust in 'honest'.
    """
    history = []
    print("\n=== PHASE 1: BOOTSTRAP (Honest only) ===")
    idx = start_idx

    for _ in range(steps):
        h = hash_step(idx)
        sig = honest.sign(h)
        step = Step(idx, h, sig, honest.model_id, phase="boot")
        valid = verify_step(step)
        w, t = controller.get(step.model_id)
        print(f"[BOOT] step={idx} model=honest valid={valid} "
              f"-> weight={w:.2f}, theta={t:.2f}")
        history.append(step)
        idx += 1

    return history, idx

def run_phase_shadow_warmup(honest, shadow, start_idx, steps=20):
    """
    Phase 2: Honest and shadow alternate, but shadow behaves.
    Purpose: let shadow build some trust without cheating yet.
    """
    history = []
    print("\n=== PHASE 2: SHADOW WARM-UP (both honest) ===")
    idx = start_idx

    for _ in range(steps):
        # Alternate models: honest then shadow then honest...
        for model in (honest, shadow):
            h = hash_step(idx)
            sig = model.sign(h)
            step = Step(idx, h, sig, model.model_id, phase="warmup")
            valid = verify_step(step)
            w, t = controller.get(model.model_id)
            print(f"[WARMUP] step={idx} model={model.model_id} "
                  f"valid={valid} -> weight={w:.2f}, theta={t:.2f}")
            history.append(step)
            idx += 1

    return history, idx

def run_phase_shadow_attack(honest, shadow, start_idx, steps=40, cheat_prob=0.5):
    """
    Phase 3: Shadow starts cheating with some probability while honest stays clean.
    Models still alternate. We watch controller separate them.
    """
    history = []
    print("\n=== PHASE 3: SHADOW ATTACK (oscillation) ===")
    idx = start_idx
    shadow.cheat_prob = cheat_prob  # enable cheating

    shadow_bad_count = 0
    shadow_good_count = 0

    for _ in range(steps):
        for model in (honest, shadow):
            h = hash_step(idx)
            sig = model.sign(h)
            step = Step(idx, h, sig, model.model_id, phase="attack")
            valid = verify_step(step)
            w, t = controller.get(model.model_id)

            label = "GOOD"
            if model.model_id == "shadow":
                # We can infer GOOD/BAD from validity under its own key
                if valid:
                    shadow_good_count += 1
                else:
                    shadow_bad_count
