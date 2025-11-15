import hashlib
import random

# ============================================================
# Utility
# ============================================================

def hash_event(global_step, model_id, logical_idx):
    base = f"{global_step}|{model_id}|{logical_idx}"
    return hashlib.sha256(base.encode()).hexdigest()

def verify_signature(key, signature, message):
    return signature == f"{key}:{message}"

# ============================================================
# Models
# ============================================================

class BaseModel:
    def __init__(self, model_id, key):
        self.model_id = model_id
        self.key = key
        self.logical_idx = 0

    def next_hash(self, global_step):
        h = hash_event(global_step, self.model_id, self.logical_idx)
        self.logical_idx += 1
        return h

    def sign(self, message, context):
        return f"{self.key}:{message}"

class HonestModel(BaseModel):
    def sign(self, message, context):
        return f"{self.key}:{message}"

class ByzantineModel(BaseModel):
    """
    Byzantine actor:
      - During bootstrap & pre-attack: honest
      - During attack: mostly malicious (bad signatures), with small chance of "fake good"
    """
    def sign(self, message, context):
        mode = context.get("mode", "honest")

        if mode in ("bootstrap", "pre"):
            # behave perfectly
            return f"{self.key}:{message}"

        if mode == "attack":
            # Byzantine: mostly bad signatures
            # small chance of good to mimic partial correctness
            if random.random() < 0.8:
                # malicious: corrupt message
                return f"{self.key}:{message[::-1]}"
            else:
                # occasional good proof
                return f"{self.key}:{message}"

        # fallback
        return f"{self.key}:{message}"

# ============================================================
# Adaptive Controller (per model)
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
            # modest forgiveness
            m["weight"] = min(1.0, m["weight"] + 0.03)
            m["theta"]  = max(0.5, m["theta"] - 0.08)
        else:
            # strong punishment
            m["weight"] = max(0.0, m["weight"] - 0.10)
            m["theta"]  = min(5.0, m["theta"] + 0.30)

    def get(self, model_id):
        self._ensure(model_id)
        m = self.state[model_id]
        return m["weight"], m["theta"]

    def summary(self):
        print("\n=== FINAL CONTROLLER SUMMARY ===")
        for mid, m in sorted(self.state.items()):
            print(f"{mid:12s} | weight={m['weight']:.2f}, theta={m['theta']:.2f}")

controller = PerModelController()

# ============================================================
# Verification
# ============================================================

MODEL_KEYS = {}

def verify_event(global_step, model, phase, h, sig):
    model_id = model.model_id
    key = MODEL_KEYS[model_id]

    if not verify_signature(key, sig, h):
        controller.update(model_id, False)
        w,t = controller.get(model_id)
        print(f"[{phase:10s}] step={global_step:03d} | {model_id:12s} | BAD  | w={w:.2f}, θ={t:.2f}")
        return False

    controller.update(model_id, True)
    w,t = controller.get(model_id)
    print(f"[{phase:10s}] step={global_step:03d} | {model_id:12s} | GOOD | w={w:.2f}, θ={t:.2f}")
    return True

# ============================================================
# Phases
# ============================================================

def phase_bootstrap(models, start_step):
    print("\n=== PHASE 1: BOOTSTRAP (everyone honest) ===")
    g = start_step
    for _ in range(5):
        for m in models:
            ctx = {"mode": "bootstrap"}
            h = m.next_hash(g)
            sig = m.sign(h, ctx)
            verify_event(g, m, "BOOTSTRAP", h, sig)
            g += 1
    return g

def phase_pre_attack(models, start_step):
    print("\n=== PHASE 2: PRE-ATTACK (network looks healthy) ===")
    g = start_step
    for _ in range(5):
        for m in models:
            ctx = {"mode": "pre"}
            h = m.next_hash(g)
            sig = m.sign(h, ctx)
            verify_event(g, m, "PRE-ATTACK", h, sig)
            g += 1
    return g

def phase_byzantine_attack(honest, byzantines, start_step):
    print("\n=== PHASE 3: BYZANTINE SUPERMAJORITY ATTACK (4/5 malicious) ===")
    g = start_step

    for round_idx in range(15):
        # Honest model always good
        h = honest.next_hash(g)
        sig = honest.sign(h, {"mode": "attack"})
        verify_event(g, honest, "ATTACK", h, sig)
        g += 1

        # Each Byzantine model acts with mostly bad signatures
        for bz in byzantines:
            ctx = {"mode": "attack"}
            h = bz.next_hash(g)
            sig = bz.sign(h, ctx)
            verify_event(g, bz, "ATTACK", h, sig)
            g += 1

    return g

def phase_aftershock(honest, byzantines, start_step):
    print("\n=== PHASE 4: AFTERMATH / EXTENDED RUN ===")
    g = start_step

    for round_idx in range(10):
        # Honest continues
        h = honest.next_hash(g)
        sig = honest.sign(h, {"mode": "attack"})
        verify_event(g, honest, "AFTER", h, sig)
        g += 1

        # Byzantines keep same behavior (mostly bad)
        for bz in byzantines:
            ctx = {"mode": "attack"}
            h = bz.next_hash(g)
            sig = bz.sign(h, ctx)
            verify_event(g, bz, "AFTER", h, sig)
            g += 1

    return g

# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    honest = HonestModel("honest_core", "HONEST_KEY")
    bz_1 = ByzantineModel("byz_1", "BYZ_KEY_1")
    bz_2 = ByzantineModel("byz_2", "BYZ_KEY_2")
    bz_3 = ByzantineModel("byz_3", "BYZ_KEY_3")
    bz_4 = ByzantineModel("byz_4", "BYZ_KEY_4")

    models = [honest, bz_1, bz_2, bz_3, bz_4]
    byz_list = [bz_1, bz_2, bz_3, bz_4]

    for m in models:
        MODEL_KEYS[m.model_id] = m.key

    g_step = 0
    g_step = phase_bootstrap(models, g_step)
    g_step = phase_pre_attack(models, g_step)
    g_step = phase_byzantine_attack(honest, byz_list, g_step)
    g_step = phase_aftershock(honest, byz_list, g_step)

    controller.summary()
    print("\n=== BYZANTINE SUPERMAJORITY TEST COMPLETE ===")
