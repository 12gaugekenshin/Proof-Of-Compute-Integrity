import time
import random
from datetime import datetime, UTC, timedelta
import hashlib
import json

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
            # reward
            self.s = min(1.0, self.s + 0.03)
            self.w = min(1.0, self.w + 0.02)
            self.theta = max(1.0, self.theta - 0.03)
        else:
            # penalize
            self.s = max(0.0, self.s - 0.05)
            self.w = max(0.0, self.w - 0.04)
            self.theta = min(10.0, self.theta + 0.07)

    def __repr__(self):
        return f"s={self.s:.2f} | w={self.w:.2f} | θ={self.theta:.2f}"

# ----------------------------------------------------------
# Generate noisy proof
# ----------------------------------------------------------
def generate_noisy_proof(noise_level):
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
        "ts": event["ts"],
        "noise": noise_level,
        "proof_hash": proof_hash
    }

# ----------------------------------------------------------
# Noise → validity
# ----------------------------------------------------------
def noise_to_valid(noise):
    if noise == 0.0:
        return True
    if noise >= 0.9:
        return False
    return random.random() > noise

# ----------------------------------------------------------
# Generate random chaos noise pattern
# ----------------------------------------------------------
def chaos_noise_step(step):
    # Phase shifts like a real network
    if step % 120 < 40:      # calm zone
        return random.uniform(0.0, 0.2)
    elif step % 120 < 80:    # turbulence
        return random.uniform(0.2, 0.6)
    else:                    # attack zone
        return random.uniform(0.7, 1.0)

# ----------------------------------------------------------
# Run Long-Horizon Chaos Test (500 steps)
# ----------------------------------------------------------
print("\n=== Long-Horizon Chaos Test (500 Steps) ===\n")
controller = Controller()

for step in range(1, 501):
    noise = chaos_noise_step(step)
    proof = generate_noisy_proof(noise)
    sig_good = noise_to_valid(noise)

    controller.update(sig_good)
    status = "GOOD" if sig_good else "BAD"

    print(f"step {step:03} | noise={noise:.2f} | sig={status:<4} | {controller}")

    time.sleep(0.03)  # fast but readable
