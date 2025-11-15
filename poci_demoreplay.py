import time
from datetime import datetime, timedelta, UTC
import hashlib
import json

# ----------------------------------------------------------
# PoCI Adaptive Controller
# ----------------------------------------------------------
class Controller:
    def __init__(self):
        self.theta = 1.0     # scrutiny / difficulty
        self.w = 1.0         # trust weight
        self.s = 0.0         # success score
        self.proof_cache = set()  # store hashes of seen proofs (replay detector)

    def update(self, sig_good):
        if sig_good:
            # good proof
            self.s = min(1.0, self.s + 0.10)
            self.w = min(1.0, self.w + 0.05)
            self.theta = max(1.0, self.theta - 0.10)
        else:
            # replay or invalid proof
            self.s = max(0.0, self.s - 0.20)
            self.w = max(0.0, self.w - 0.15)
            self.theta = min(10.0, self.theta + 0.50)

    def __repr__(self):
        return f"s={self.s:.2f} | w={self.w:.2f} | θ={self.theta:.2f}"


# ----------------------------------------------------------
# Proof creation (hash of event)
# ----------------------------------------------------------
def generate_proof(event):
    serialized = json.dumps(event, sort_keys=True).encode()
    h = hashlib.sha256(serialized).hexdigest()
    return {
        "event": event,
        "proof_hash": h,
        "ts": event["ts"]
    }


# ----------------------------------------------------------
# Timestamp checker (same as drift test)
# ----------------------------------------------------------
def check_timestamp(event_ts_iso, max_drift_sec=30):
    event_ts = datetime.fromisoformat(event_ts_iso)
    now = datetime.now(UTC)
    delta = abs((now - event_ts).total_seconds())
    return delta <= max_drift_sec


# ----------------------------------------------------------
# Replay + timestamp verification
# ----------------------------------------------------------
def verify_proof(controller, proof):
    proof_hash = proof["proof_hash"]

    # 1. timestamp integrity
    ts_good = check_timestamp(proof["ts"])

    # 2. replay detection: proof hash already seen?
    replay = proof_hash in controller.proof_cache

    # Add to cache AFTER check to ensure first pass is allowed
    controller.proof_cache.add(proof_hash)

    sig_good = ts_good and not replay
    return sig_good, replay


# ----------------------------------------------------------
# Run Test 2 — Replay Attack
# ----------------------------------------------------------
print("\n=== Test 2: Replay Attack Simulation ===\n")

controller = Controller()

# Event
event = {
    "ts": datetime.now(UTC).isoformat(),
    "payload": "compute_step",
}

# Generate a proof
proof = generate_proof(event)

# Submit proof twice
submissions = [
    ("FIRST_SUBMISSION", proof),
    ("REPLAY_SUBMISSION", proof),
]

step = 1
for label, p in submissions:
    sig_good, replay = verify_proof(controller, p)
    controller.update(sig_good)

    status = "GOOD" if sig_good else "BAD"
    replay_flag = "REPLAY" if replay else "NO_REPLAY"

    print(f"step {step:03} | {label:<17} | sig={status:<4} | {replay_flag:<8} | {controller}")

    step += 1
    time.sleep(0.2)
