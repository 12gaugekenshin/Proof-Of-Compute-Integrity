import time
from datetime import datetime, timedelta, UTC
import hashlib
import json
import random

# ----------------------------------------------------------
# Adaptive Controller
# ----------------------------------------------------------
class Controller:
    def __init__(self):
        self.theta = 1.0
        self.w = 1.0
        self.s = 0.0

    def update(self, sig_good):
        if sig_good:
            self.s = min(1.0, self.s + 0.05)
            self.w = min(1.0, self.w + 0.03)
            self.theta = max(1.0, self.theta - 0.05)
        else:
            self.s = max(0.0, self.s - 0.10)
            self.w = max(0.0, self.w - 0.08)
            self.theta = min(10.0, self.theta + 0.15)

    def __repr__(self):
        return f"s={self.s:.2f} | w={self.w:.2f} | θ={self.theta:.2f}"


# ----------------------------------------------------------
# Proof generator with noise injection
# ----------------------------------------------------------
def generate_noisy_proof(noise_level):
    """
    noise_level:
        0.0 = good
        0.2–0.4 = borderline
        1.0 = bad
    """

    ts = datetime.now(UTC)
    event = {
        "ts": ts.isoformat(),
        "payload": "compute_step",
        "noise": noise_level
    }

    serialized = json.dumps(event, sort_keys=True).encode()
    proof_hash = hashlib.sha256(serialized).hexdigest()

    return {
        "event": event,
        "proof_hash": proof_hash,
        "ts": event["ts"],
        "noise": noise_level
    }


# ----------------------------------------------------------
# Noise-based validity checker
# ----------------------------------------------------------
def noise_to_valid(noise):
    """
    Converts noise into validity.

    If noise == 0.0 → always GOOD  
    If noise >= 0.8 → always BAD  
    If 0.1–0.6 → 50/50 chance  
    """
    if noise == 0.0:
        return True
    if noise >= 0.8:
        return False

    # borderline → probabilistic validity
    return random.random() > noise


# ----------------------------------------------------------
# Run Noise Stability Test
# ----------------------------------------------------------
print("\n=== Test 3: Noise Stability / Learnability Equilibrium ===\n")

controller = Controller()

noise_levels = [
    0.0, 0.0,               # clean start
    0.2, 0.3, 0.25,         # light noise
    0.0,                    # recovery
    0.8, 1.0,               # strong noise
    0.0,                    # reset
    0.15, 0.4, 0.35,        # more mid-noise
    1.0, 0.8,               # attacks
    0.0, 0.0,               # stabilization
    0.3, 0.25, 0.2,         # light turbulence
    0.0                     # final stabilization
]

step = 1
for noise in noise_levels:
    proof = generate_noisy_proof(noise)
    sig_good = noise_to_valid(noise)

    controller.update(sig_good)
    status = "GOOD" if sig_good else "BAD"

    print(f"step {step:03} | noise={noise:<4} | sig={status:<4} | {controller}")

    step += 1
    time.sleep(0.15)
