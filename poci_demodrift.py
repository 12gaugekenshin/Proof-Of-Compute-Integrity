import time
from datetime import datetime, timedelta, UTC

# ----------------------------------------------------------
# PoCI Adaptive Controller (simple model)
# ----------------------------------------------------------
class Controller:
    def __init__(self):
        self.theta = 1.0     # scrutiny / difficulty
        self.w = 1.0         # trust weight
        self.s = 0.0         # success score (0–1)

    def update(self, sig_good):
        if sig_good:
            # good proof: reward slightly
            self.s = min(1.0, self.s + 0.10)
            self.w = min(1.0, self.w + 0.05)
            self.theta = max(1.0, self.theta - 0.10)
        else:
            # bad proof: penalize / tighten scrutiny
            self.s = max(0.0, self.s - 0.20)
            self.w = max(0.0, self.w - 0.15)
            self.theta = min(10.0, self.theta + 0.50)

    def __repr__(self):
        return f"s={self.s:.2f} | w={self.w:.2f} | θ={self.theta:.2f}"

# ----------------------------------------------------------
# Timestamp drift detector (using timezone-aware UTC)
# ----------------------------------------------------------
def check_timestamp(event_ts_iso, max_drift_sec=30):
    """
    Reject events with unrealistic timestamp drift.
    max_drift_sec = allowed difference window.
    """
    event_ts = datetime.fromisoformat(event_ts_iso)
    now = datetime.now(UTC)
    delta = abs((now - event_ts).total_seconds())
    return delta <= max_drift_sec

# ----------------------------------------------------------
# Generate events (timezone-aware)
# ----------------------------------------------------------
def generate_event(ts_offset_seconds=0):
    ts = datetime.now(UTC) + timedelta(seconds=ts_offset_seconds)
    return {
        "ts": ts.isoformat(),
        "payload": "compute_step",
    }

# ----------------------------------------------------------
# Verification step
# ----------------------------------------------------------
def verify_event(event):
    sig_good = check_timestamp(event["ts"])
    return sig_good

# ----------------------------------------------------------
# Run Test 1
# ----------------------------------------------------------
controller = Controller()

good_event = generate_event(0)            # correct timestamp
drifted_event = generate_event(3600)      # 1 hour drift (attack)

events = [
    ("GOOD_EVENT", good_event),
    ("DRIFT_ATTACK", drifted_event),
]

print("\n=== Test 1: Timestamp Drift Attack (UTC-Safe) ===\n")

step = 1
for label, ev in events:
    sig_good = verify_event(ev)
    controller.update(sig_good)

    status = "GOOD" if sig_good else "BAD"
    print(f"step {step:03} | {label:<12} | sig={status:<4} | {controller}")

    step += 1
    time.sleep(0.2)
