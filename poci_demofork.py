import hashlib
import random
import time

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
# Honest / Fake Signing
# ============================================================

class HonestModel:
    def __init__(self, key="HONEST_KEY"):
        self.key = key

    def sign(self, message):
        return f"{self.key}:{message}"

class AttackerModel:
    def __init__(self, key="ATTACKER_KEY"):
        self.key = key

    def fake_sign(self, message):
        # attacker cannot create a valid honest signature
        return f"{self.key}:{message}"

# ============================================================
# Adaptive Controller
# ============================================================

class AdaptiveController:
    def __init__(self):
        self.theta = 1.0  # skepticism
        self.weight = 1.0 # trust in lineage

    def update(self, valid):
        if valid:
            self.weight = min(1.0, self.weight + 0.05)
            self.theta = max(0.5, self.theta - 0.1)
        else:
            self.weight = max(0.0, self.weight - 0.1)
            self.theta = min(5.0, self.theta + 0.3)

    def __repr__(self):
        return f"(weight={self.weight:.2f}, theta={self.theta:.2f})"

controller = AdaptiveController()

# ============================================================
# Step Structure
# ============================================================

class Step:
    def __init__(self, index, hash_value, signature, model_id):
        self.index = index
        self.hash = hash_value
        self.signature = signature
        self.model_id = model_id

    def __repr__(self):
        return (f"Step {self.index}: hash={self.hash[:8]}… "
                f"sig={self.signature.split(':')[0]} "
                f"model={self.model_id}")

# ============================================================
# Verification Logic
# ============================================================

def verify_step(step: Step, honest_key="HONEST_KEY"):
    """Returns True if step is valid."""
    message = step.hash
    if verify_signature(honest_key, step.signature, message):
        controller.update(True)
        return True
    else:
        controller.update(False)
        return False

def verify_lineage(chain):
    """Checks lineage consistency."""
    print("\n=== LINEAGE VERIFICATION START ===")

    for i, step in enumerate(chain):
        # 1. Signature check
        valid_sig = verify_step(step)
        if not valid_sig:
            print(f"[FAIL] Step {step.index}: INVALID SIGNATURE")
            return False

        # 2. Ancestor hash matching
        if i > 0:
            prev = chain[i-1]
            expected_hash = hash_step(prev.index + 1)
            if step.hash != expected_hash:
                print(f"[FAIL] Step {step.index}: HASH MISMATCH")
                print(f"Expected hash of step {prev.index+1}")
                print(f"Got: {step.hash}")
                return False

        print(f"[OK] Step {step.index} verified. Controller: {controller}")

    print("=== LINEAGE VERIFIED SUCCESSFULLY ===")
    return True

# ============================================================
# Real Honest Chain
# ============================================================

def build_real_lineage():
    honest = HonestModel()
    real_chain = []

    print("\n=== BUILDING REAL LINEAGE ===")

    for i in range(10):
        h = hash_step(i)
        sig = honest.sign(h)
        real_chain.append(Step(i, h, sig, "honest"))
        print(f"Real step {i} created.")

    return real_chain

# ============================================================
# Attacker Fork
# ============================================================

def build_attacker_fork(real_chain, fork_point=5):
    attacker = AttackerModel()
    forked = real_chain[:fork_point]

    print(f"\n=== ATTACKER FORKING AT STEP {fork_point} ===")

    for i in range(fork_point, 11):
        h = hash_step(i)
        sig = attacker.fake_sign(h)
        forked.append(Step(i, h, sig, "attacker"))
        print(f"Attacker created fake step {i}.")

    return forked

# ============================================================
# Run the Test
# ============================================================

if __name__ == "__main__":
    real_chain = build_real_lineage()
    attacker_chain = build_attacker_fork(real_chain)

    print("\n\n=== VERIFYING REAL CHAIN ===")
    verify_lineage(real_chain)

    print("\n\n=== VERIFYING ATTACKER FORK ===")
    verify_lineage(attacker_chain)

    print("\n\n=== TEST COMPLETE ===")

