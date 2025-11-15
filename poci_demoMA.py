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
            # reward (slightly)
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
# Noise → validity mapping (same semantics as before)
# ----------------------------------------------------------
def noise_to_valid(noise):
    """
    noise == 0.0   -> always GOOD
    noise >= 0.9   -> always BAD
    0.0 < noise < 0.9 -> probabilistic (higher noise = more likely BAD)
    """
    if noise == 0.0:
        return True
    if noise >= 0.9:
        return False
    return random.random() > noise


# ----------------------------------------------------------
# Noise profiles for agents
# ----------------------------------------------------------
def honest_noise(step):
    """
    HONEST agent: mostly very low noise, with small rough patches.
    """
    # Every 50 steps, give a little turbulence
    if step % 50 < 40:
        return random.uniform(0.0, 0.15)  # super clean
    else:
        return random.uniform(0.15, 0.35) # mild turbulence


def attacker_noise(step):
    """
    ATTACKER agent: mostly high noise, with occasional 'trying to look good'.
    """
    if step % 60 < 45:
        return random.uniform(0.7, 1.0)   # heavy noise / attack phase
    else:
        return random.uniform(0.3, 0.8)   # still sketchy even when 'calm'


# ----------------------------------------------------------
# Run Multi-Agent Trust Separation Test
# ----------------------------------------------------------
print("\n=== Multi-Agent Trust Separation Test (HONEST vs ATTACKER) ===\n")

honest = Controller("HONEST")
attacker = Controller("ATTACKER")

for step in range(1, 201):
    # HONEST AGENT
    h_noise = honest_noise(step)
    h_good = noise_to_valid(h_noise)
    honest.update(h_good)
    h_status = "GOOD" if h_good else "BAD"

    # ATTACKER AGENT
    a_noise = attacker_noise(step)
    a_good = noise_to_valid(a_noise)
    attacker.update(a_good)
    a_status = "GOOD" if a_good else "BAD"

    print(
        f"step {step:03} | "
        f"HONEST   noise={h_noise:.2f} sig={h_status:<4} {honest} || "
        f"ATTACKER noise={a_noise:.2f} sig={a_status:<4} {attacker}"
    )

    time.sleep(0.04)  # fast but readable

print("\n=== Final State ===")
print(f"HONEST   -> {honest}")
print(f"ATTACKER -> {attacker}")
