import time
import random

# ----------------------------------------------------------
# Adaptive Controller (per agent)
# ----------------------------------------------------------
class Controller:
    def __init__(self, name):
        self.name = name
        self.theta = 1.0
        self.w = 1.0
        self.s = 0.0

    def update(self, sig_good):
        if sig_good:
            self.s = min(1.0, self.s + 0.03)
            self.w = min(1.0, self.w + 0.02)
            self.theta = max(1.0, self.theta - 0.03)
        else:
            self.s = max(0.0, self.s - 0.05)
            self.w = max(0.0, self.w - 0.04)
            self.theta = min(10.0, self.theta + 0.07)

    def __repr__(self):
        return f"s={self.s:.2f} | w={self.w:.2f} | θ={self.theta:.2f}"


# ----------------------------------------------------------
# Validity based on noise
# ----------------------------------------------------------
def noise_to_valid(noise):
    if noise == 0.0:
        return True
    if noise >= 0.9:
        return False
    return random.random() > noise


# ----------------------------------------------------------
# Noise functions for each agent
# ----------------------------------------------------------

def honest_noise(step):
    # almost always clean
    if step % 50 < 40:
        return random.uniform(0.0, 0.15)
    else:
        return random.uniform(0.15, 0.35)


def attacker_noise(step):
    # mostly hostile
    if step % 60 < 45:
        return random.uniform(0.7, 1.0)
    else:
        return random.uniform(0.3, 0.8)


def opportunist_noise(step, theta):
    """
    This is the strategic cheater:

    - If theta is HIGH (system suspicious), act clean.
    - If theta is LOW (system relaxed), cheat more.
    """
    if theta > 4.0:
        # behave very clean to restore trust
        return random.uniform(0.0, 0.15)
    else:
        # exploit low scrutiny
        return random.uniform(0.2, 0.8)


# ----------------------------------------------------------
# Run Triad Test
# ----------------------------------------------------------
print("\n=== TRIAD TEST: HONEST vs OPPORTUNIST vs ATTACKER ===\n")

honest = Controller("HONEST")
opportunist = Controller("OPPORTUNIST")
attacker = Controller("ATTACKER")

for step in range(1, 251):
    # HONEST agent
    h_noise = honest_noise(step)
    h_good = noise_to_valid(h_noise)
    honest.update(h_good)
    h_status = "GOOD" if h_good else "BAD"

    # OPPORTUNIST agent
    o_noise = opportunist_noise(step, opportunist.theta)
    o_good = noise_to_valid(o_noise)
    opportunist.update(o_good)
    o_status = "GOOD" if o_good else "BAD"

    # ATTACKER agent
    a_noise = attacker_noise(step)
    a_good = noise_to_valid(a_noise)
    attacker.update(a_good)
    a_status = "GOOD" if a_good else "BAD"

    print(
        f"step {step:03} | "
        f"HONEST noise={h_noise:.2f} sig={h_status:<4} {honest} || "
        f"OPPORTUNIST noise={o_noise:.2f} sig={o_status:<4} {opportunist} || "
        f"ATTACKER noise={a_noise:.2f} sig={a_status:<4} {attacker}"
    )

    time.sleep(0.04)

print("\n=== FINAL STATE ===")
print(f"HONEST      -> {honest}")
print(f"OPPORTUNIST -> {opportunist}")
print(f"ATTACKER    -> {attacker}")
