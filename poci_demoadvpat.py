import hashlib
import random

# ============================================================
# Utility Functions
# ============================================================

def hash_step(i):
    return hashlib.sha256(f"step-{i}".encode()).hexdigest()

def verify_signature(key, signature, msg):
    return signature == f"{key}:{msg}"

# ============================================================
# Adversarial Model
# ============================================================

class AdversarialModel:
    def __init__(self, key="ADV_KEY", model_id="adv"):
        self.key = key
        self.model_id = model_id
        self.cheat_prob = 0.0
    
    def sign(self, msg, force_bad=False):
        """force_bad=True overrides cheat_prob"""
        if force_bad or (random.random() < self.cheat_prob):
            return f"{self.key}:{msg[::-1]}"
        return f"{self.key}:{msg}"

# ============================================================
# Adaptive Controller
# ============================================================

class Controller:
    def __init__(self):
        self.weight = 1.0
        self.theta = 1.0

    def update(self, valid):
        if valid:
            self.weight = min(1.0, self.weight + 0.03)
            self.theta  = max(0.5, self.theta - 0.08)
        else:
            self.weight = max(0.0, self.weight - 0.10)
            self.theta  = min(5.0, self.theta + 0.30)

    def snapshot(self):
        return self.weight, self.theta

controller = Controller()

# ============================================================
# Verification Logic
# ============================================================

def verify_step(step_num, model, phase_label, force_bad=False):
    h = hash_step(step_num)
    sig = model.sign(h, force_bad=force_bad)
    valid = verify_signature(model.key, sig, h)
    controller.update(valid)
    w,t = controller.snapshot()
    label = "GOOD" if valid else "BAD"
    print(f"[{phase_label}] step={step_num:03d} | {label:4s} | weight={w:.2f}, theta={t:.2f}")
    return valid

# ============================================================
# Adversarial Pattern Phases
# ============================================================

def phase_periodic(model, start, steps=20, period=5):
    print("\n=== PHASE 1: PERIODIC LOW-FREQUENCY CHEATING ===")
    i = start
    for k in range(steps):
        force_bad = (k % period == 0)  # cheat on every Nth step
        verify_step(i, model, "PERIODIC", force_bad)
        i += 1
    return i

def phase_burst(model, start, burst_length=10, bursts=2, gap=5):
    print("\n=== PHASE 2: CLUSTERED BURST ATTACKS ===")
    i = start
    for b in range(bursts):
        # normal gap
        for _ in range(gap):
            verify_step(i, model, "BURST-GAP", force_bad=False)
            i += 1
        # burst of pure cheating
        for _ in range(burst_length):
            verify_step(i, model, "BURST-ATTACK", force_bad=True)
            i += 1
    return i

def phase_oscillation(model, start, steps=20):
    print("\n=== PHASE 3: HIGH-FREQUENCY OSCILLATION ===")
    i = start
    for k in range(steps):
        force_bad = (k % 2 == 1)  # BAD on odd steps
        verify_step(i, model, "OSCILLATE", force_bad)
        i += 1
    return i

def phase_threshold_cheat(model, start, steps=30, theta_threshold=0.7):
    print("\n=== PHASE 4: THRESHOLD-DODGING CHEATING ===")
    i = start
    for _ in range(steps):
        w, t = controller.snapshot()
        # cheat ONLY when skepticism is low
        force_bad = (t <= theta_threshold)
        verify_step(i, model, "THRESH-HACK", force_bad)
        i += 1
    return i

def phase_late_attack(model, start, steps=10):
    print("\n=== PHASE 5: LATE-STAGE SURPRISE ATTACK ===")
    i = start
    # behave nicely first
    for _ in range(5):
        verify_step(i, model, "LATE-NICE", force_bad=False)
        i += 1
    # sudden sharp cheating spike
    for _ in range(steps):
        verify_step(i, model, "LATE-BAD", force_bad=True)
        i += 1
    return i

def phase_random_noise(model, start, steps=30):
    print("\n=== PHASE 6: FULL RANDOM ADVERSARIAL NOISE ===")
    i = start
    for _ in range(steps):
        force_bad = random.random() < 0.3  # 30% random maliciousness
        verify_step(i, model, "RANDOM", force_bad)
        i += 1
    return i

# ============================================================
# Main Runner
# ============================================================

if __name__ == "__main__":
    random.seed(42)

    model = AdversarialModel()

    idx = 0
    idx = phase_periodic(model, idx)
    idx = phase_burst(model, idx)
    idx = phase_oscillation(model, idx)
    idx = phase_threshold_cheat(model, idx)
    idx = phase_late_attack(model, idx)
    idx = phase_random_noise(model, idx)

    w,t = controller.snapshot()
    print("\n=== FINAL CONTROLLER STATE ===")
    print(f"weight={w:.2f}, theta={t:.2f}")
    print("\n=== ADVERSARIAL PATTERN TEST COMPLETE ===")
