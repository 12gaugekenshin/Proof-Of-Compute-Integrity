import hashlib
import random

# ============================================================
# Utility
# ============================================================

def hash_event(global_step, model_id, logical_idx):
    """Deterministic event hash."""
    base = f"{global_step}|{model_id}|{logical_idx}"
    return hashlib.sha256(base.encode()).hexdigest()

def verify_signature(key, signature, message):
    return signature == f"{key}:{message}"

# ============================================================
# Model Types
# ============================================================

class BaseModel:
    def __init__(self, model_id, key):
        self.model_id = model_id
        self.key = key
        self.logical_idx = 0  # per-model step counter

    def next_hash(self, global_step):
        h = hash_event(global_step, self.model_id, self.logical_idx)
        self.logical_idx += 1
        return h

    def sign(self, message, context):
        """Override in subclasses."""
        return f"{self.key}:{message}"

class HonestModel(BaseModel):
    def sign(self, message, context):
        return f"{self.key}:{message}"

class ShadowModel(BaseModel):
    """Sybil-type model: mostly honest, sometimes bursts of cheating."""
    def __init__(self, model_id, key):
        super().__init__(model_id, key)
        self.cheat_prob = 0.0

    def sign(self, message, context):
        # context may include 'mode' or 'round'
        mode = context.get("mode", "normal")
        if mode == "sybil_attack":
            # In attack rounds, higher cheat prob
            self.cheat_prob = 0.4
        else:
            self.cheat_prob = 0.05  # light noise otherwise

        if random.random() < self.cheat_prob:
            return f"{self.key}:{message[::-1]}"
        return f"{self.key}:{message}"

class DriftModel(BaseModel):
    """Gradually degrades, then (maybe) recovers."""
    def __init__(self, model_id, key):
        super().__init__(model_id, key)
        self.phase = "stable"
        self.drift_step = 0

    def sign(self, message, context):
        self.phase = context.get("drift_phase", "stable")
        cheat_prob = 0.0

        if self.phase == "stable":
            cheat_prob = 0.0
        elif self.phase == "drift":
            # ramp up 0 -> 0.7 over time
            self.drift_step += 1
            cheat_prob = min(0.7, self.drift_step / 30.0 * 0.7)
        elif self.phase == "recovery":
            # ramp down 0.7 -> 0.0
            self.drift_step = max(0, self.drift_step - 1)
            cheat_prob = max(0.0, self.drift_step / 30.0 * 0.7)

        if random.random() < cheat_prob:
            return f"{self.key}:{message[::-1]}"
        return f"{self.key}:{message}"

class AdversarialModel(BaseModel):
    """Patterned attacker: oscillation, bursts, threshold-dodging."""
    def __init__(self, model_id, key):
        super().__init__(model_id, key)
        self.mode = "low_noise"
        self.local_step = 0

    def sign(self, message, context):
        self.mode = context.get("adv_mode", "low_noise")
        self.local_step += 1

        force_bad = False
        if self.mode == "low_noise":
            force_bad = (self.local_step % 10 == 0)
        elif self.mode == "burst":
            force_bad = (self.local_step % 2 == 0)
        elif self.mode == "oscillate":
            force_bad = (self.local_step % 2 == 1)
        elif self.mode == "late_spike":
            # behave nice for first N, then go evil
            force_bad = (self.local_step > 20)
        elif self.mode == "random":
            force_bad = random.random() < 0.3

        if force_bad:
            return f"{self.key}:{message[::-1]}"
        return f"{self.key}:{message}"

class TimeAttackModel(BaseModel):
    """Tries replay and timestamp attacks."""
    def __init__(self, model_id, key):
        super().__init__(model_id, key)
        self.replay_hash = None
        self.replay_sig = None
        self.mode = "normal"

    def sign(self, message, context):
        self.mode = context.get("time_mode", "normal")
        if self.mode == "normal":
            sig = f"{self.key}:{message}"
            # cache a proof to replay later
            if self.replay_hash is None:
                self.replay_hash = message
                self.replay_sig = sig
            return sig
        elif self.mode == "replay":
            # reuse old hash+sig
            if self.replay_hash and self.replay_sig:
                return self.replay_sig
            return f"{self.key}:{message}"
        else:
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
            m["weight"] = min(1.0, m["weight"] + 0.03)
            m["theta"]  = max(0.5, m["theta"] - 0.08)
        else:
            m["weight"] = max(0.0, m["weight"] - 0.10)
            m["theta"]  = min(5.0, m["theta"] + 0.30)

    def get(self, model_id):
        self._ensure(model_id)
        m = self.state[model_id]
        return m["weight"], m["theta"]

    def summary(self):
        print("\n=== FINAL CONTROLLER SUMMARY ===")
        for mid, m in sorted(self.state.items()):
            print(f"{mid:10s} | weight={m['weight']:.2f}, theta={m['theta']:.2f}")

controller = PerModelController()

# ============================================================
# Global timing + replay layer
# ============================================================

MODEL_KEYS = {}
last_timestamp = {}  # model_id -> last_seen_ts
used_proofs = set()  # (model_id, hash, sig)

MAX_FUTURE_DRIFT = 30
MAX_BACKWARD_DRIFT = 10

def verify_event(global_step, model, phase, timestamp, h, sig):
    """
    Full PoCI-style verification:
      - signature
      - replay
      - timing monotonicity
    """
    model_id = model.model_id
    key = MODEL_KEYS[model_id]
    reason = "OK"

    # 1) Signature
    if not verify_signature(key, sig, h):
        controller.update(model_id, False)
        w,t = controller.get(model_id)
        print(f"[{phase:10s}] step={global_step:03d} | {model_id:10s} | BAD  | reason=BAD_SIGNATURE   | w={w:.2f}, θ={t:.2f}")
        return False

    # 2) Replay
    pid = (model_id, h, sig)
    if pid in used_proofs:
        controller.update(model_id, False)
        w,t = controller.get(model_id)
        print(f"[{phase:10s}] step={global_step:03d} | {model_id:10s} | BAD  | reason=REPLAY          | w={w:.2f}, θ={t:.2f}")
        return False

    # 3) Timing checks
    last_t = last_timestamp.get(model_id, None)
    # global_time ~ timestamp of this event
    global_time = timestamp

    # future check (relative to global_time we assume external)
    # here we treat global_time as 'wall clock', so allow small slack only.
    if timestamp > global_time + MAX_FUTURE_DRIFT:
        controller.update(model_id, False)
        w,t = controller.get(model_id)
        print(f"[{phase:10s}] step={global_step:03d} | {model_id:10s} | BAD  | reason=TIME_FUTURE     | w={w:.2f}, θ={t:.2f}")
        return False

    # backward monotonic check
    if last_t is not None:
        if timestamp + MAX_BACKWARD_DRIFT < last_t:
            controller.update(model_id, False)
            w,t = controller.get(model_id)
            print(f"[{phase:10s}] step={global_step:03d} | {model_id:10s} | BAD  | reason=TIME_BACKDATED | w={w:.2f}, θ={t:.2f}")
            return False

    # All good
    used_proofs.add(pid)
    last_timestamp[model_id] = timestamp
    controller.update(model_id, True)
    w,t = controller.get(model_id)
    print(f"[{phase:10s}] step={global_step:03d} | {model_id:10s} | GOOD | reason=OK             | w={w:.2f}, θ={t:.2f}")
    return True

# ============================================================
# Phases
# ============================================================

def phase_bootstrap(models, start_step, start_time):
    print("\n=== PHASE 1: NETWORK BOOTSTRAP (all honest) ===")
    g = start_step
    t = start_time
    for _ in range(10):
        for m in models:
            h = m.next_hash(g)
            sig = f"{m.key}:{h}"  # force honest for bootstrap
            verify_event(g, m, "BOOTSTRAP", t, h, sig)
            g += 1
            t += 5
    return g, t

def phase_mixed_normal(models, start_step, start_time):
    print("\n=== PHASE 2: MIXED NORMAL OPERATION (light noise) ===")
    g = start_step
    t = start_time
    for _ in range(15):
        for m in models:
            ctx = {}
            if isinstance(m, DriftModel):
                ctx["drift_phase"] = "stable"
            if isinstance(m, AdversarialModel):
                ctx["adv_mode"] = "low_noise"
            if isinstance(m, TimeAttackModel):
                ctx["time_mode"] = "normal"

            h = m.next_hash(g)
            sig = m.sign(h, ctx)
            verify_event(g, m, "NORMAL", t, h, sig)
            g += 1
            t += 5
    return g, t

def phase_attack(models_dict, start_step, start_time):
    print("\n=== PHASE 3: ATTACK PHASE (sybil, drift, adversarial, time attacks) ===")
    g = start_step
    t = start_time

    honest = models_dict["honest_core"]
    shadows = [models_dict["shadow_0"], models_dict["shadow_1"]]
    drift = models_dict["drift_0"]
    adv = models_dict["adv_0"]
    time_attacker = models_dict["time_0"]

    for round_idx in range(10):
        # Honest core
        h = honest.next_hash(g)
        sig = honest.sign(h, {})
        verify_event(g, honest, "ATTACK", t, h, sig)
        g += 1
        t += 5

        # Shadows in sybil mode
        for s in shadows:
            ctx = {"mode": "sybil_attack"}
            h = s.next_hash(g)
            sig = s.sign(h, ctx)
            verify_event(g, s, "ATTACK", t, h, sig)
            g += 1
            t += 5

        # Drift model in degradation
        ctx = {"drift_phase": "drift"}
        h = drift.next_hash(g)
        sig = drift.sign(h, ctx)
        verify_event(g, drift, "ATTACK", t, h, sig)
        g += 1
        t += 5

        # Adversarial patterned mode (oscillate/burst)
        ctx = {"adv_mode": "oscillate" if round_idx < 5 else "burst"}
        h = adv.next_hash(g)
        sig = adv.sign(h, ctx)
        verify_event(g, adv, "ATTACK", t, h, sig)
        g += 1
        t += 5

        # Time attacker: normal first few rounds, then replay/backdate
        if round_idx < 3:
            ctx = {"time_mode": "normal"}
            ts = t
        elif round_idx == 3:
            ctx = {"time_mode": "replay"}
            ts = t + 5  # replay later
        elif round_idx == 4:
            ctx = {"time_mode": "normal"}
            ts = t - 100  # backdated
        else:
            ctx = {"time_mode": "normal"}
            ts = t

        h = time_attacker.next_hash(g)
        sig = time_attacker.sign(h, ctx)
        verify_event(g, time_attacker, "ATTACK", ts, h, sig)
        g += 1
        t += 5

    return g, t

def phase_recovery(models_dict, start_step, start_time):
    print("\n=== PHASE 4: RECOVERY PHASE (some models try to redeem) ===")
    g = start_step
    t = start_time

    honest = models_dict["honest_core"]
    shadows = [models_dict["shadow_0"], models_dict["shadow_1"]]
    drift = models_dict["drift_0"]
    adv = models_dict["adv_0"]
    time_attacker = models_dict["time_0"]

    for _ in range(20):
        for m in [honest] + shadows + [drift, adv, time_attacker]:
            ctx = {}
            if isinstance(m, DriftModel):
                ctx["drift_phase"] = "recovery"
            if isinstance(m, AdversarialModel):
                ctx["adv_mode"] = "low_noise"
            if isinstance(m, TimeAttackModel):
                ctx["time_mode"] = "normal"
            if isinstance(m, ShadowModel):
                ctx["mode"] = "normal"

            h = m.next_hash(g)
            sig = m.sign(h, ctx)
            verify_event(g, m, "RECOVERY", t, h, sig)
            g += 1
            t += 5

    return g, t

# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    # Create models
    honest_core = HonestModel("honest_core", "HONEST_CORE_KEY")
    shadow_0 = ShadowModel("shadow_0", "SHADOW_KEY_0")
    shadow_1 = ShadowModel("shadow_1", "SHADOW_KEY_1")
    drift_0 = DriftModel("drift_0", "DRIFT_KEY_0")
    adv_0 = AdversarialModel("adv_0", "ADV_KEY_0")
    time_0 = TimeAttackModel("time_0", "TIME_KEY_0")

    models = [honest_core, shadow_0, shadow_1, drift_0, adv_0, time_0]
    models_dict = {m.model_id: m for m in models}

    # Register keys
    for m in models:
        MODEL_KEYS[m.model_id] = m.key

    g_step = 0
    cur_time = 1000

    g_step, cur_time = phase_bootstrap(models, g_step, cur_time)
    g_step, cur_time = phase_mixed_normal(models, g_step, cur_time)
    g_step, cur_time = phase_attack(models_dict, g_step, cur_time)
    g_step, cur_time = phase_recovery(models_dict, g_step, cur_time)

    controller.summary()
    print("\n=== FULL NETWORK SIMULATION COMPLETE ===")
