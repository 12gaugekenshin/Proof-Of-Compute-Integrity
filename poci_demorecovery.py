import time
import random

# ----------------------------------------------------------
# Base Adaptive Controller
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
# Controller WITH forgetting / decay
# ----------------------------------------------------------
class DecayController(Controller):
    def __init__(self, name, decay_rate=0.01):
        super().__init__(name)
        self.decay_rate = decay_rate
        # neutral baselines it drifts toward
        self.s_neutral = 0.5
        self.w_neutral = 0.5
        self.theta_neutral = 3.0

    def decay(self):
        d = self.decay_rate

        # pull toward neutral values a tiny bit each step
        self.s = self.s * (1 - d) + self.s_neutral * d
        self.w = self.w * (1 - d) + self.w_neutral * d
        self.theta = self.theta * (1 - d) + self.theta_neutral * d

    def update(self, sig_good):
        # apply decay first (time passes), then normal update
        self.decay()
        super().update(sig_good)


# ----------------------------------------------------------
# Noise -> validity helper
# ----------------------------------------------------------
def noise_to_valid(noise):
    if noise == 0.0:
        return True
    if noise >= 0.9:
        return False
    return random.random() > noise


# ----------------------------------------------------------
# Noise schedule: bad first, then good
# ----------------------------------------------------------
def scenario_noise(step):
    # Steps 1–80: behaves like an attacker
    if step <= 80:
        return random.uniform(0.7, 1.0)
    # Steps 81–160: reforms and behaves honestly
    else:
        return random.uniform(0.0, 0.2)


# ----------------------------------------------------------
# Run Reputation Recovery A/B Test
# ----------------------------------------------------------
print("\n=== Reputation Recovery Test (Static vs Decay) ===\n")

static_ctrl = Controller("STATIC_NO_DECAY")
decay_ctrl = DecayController("WITH_DECAY", decay_rate=0.02)

for step in range(1, 161):
    noise = scenario_noise(step)
    sig_good = noise_to_valid(noise)
    status = "GOOD" if sig_good else "BAD"

    # both controllers see the exact same events
    static_ctrl.update(sig_good)
    decay_ctrl.update(sig_good)

    # print every step (or comment out for less spam)
    print(
        f"step {step:03} | noise={noise:.2f} sig={status:<4} | "
        f"STATIC {static_ctrl} || DECAY {decay_ctrl}"
    )

    time.sleep(0.03)

print("\n=== FINAL STATE ===")
print(f"STATIC_NO_DECAY -> {static_ctrl}")
print(f"WITH_DECAY      -> {decay_ctrl}")
