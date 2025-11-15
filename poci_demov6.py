import random
import uuid

# ============================================================
# MODEL CLASS (12g-ACE / 12g-AFL IMPLEMENTATION)
# ============================================================

class Model:
    def __init__(self, name, alpha=0.05, beta=0.05):
        self.name = name
        self.theta = 0.0      # strictness
        self.w = 1.0          # trust weight
        self.alpha = alpha    # learning rate for theta
        self.beta = beta      # smoothing rate for w
        self.consistency_history = []
        self.w_history = []
        self.theta_history = []
        self.bad_count = 0

    def update(self, s_t):
        # Record consistency
        self.consistency_history.append(s_t)

        # Update strictness
        self.theta += (1 - s_t) * self.alpha

        # Update trust weight
        self.w += self.beta * (s_t - self.w)

        # Record history
        self.w_history.append(self.w)
        self.theta_history.append(self.theta)


# ============================================================
# EVENT GENERATION
# ============================================================

def create_event(is_bad=False):
    """
    Honest event → s_t = 1.0
    Bad event   → s_t = random noise below 1.0
    """
    if is_bad:
        # Simulate malformed proof with consistency [0.0 – 0.8]
        s = random.uniform(0.0, 0.8)
    else:
        s = 1.0

    return {
        "id": str(uuid.uuid4()),
        "consistency": s
    }


# ============================================================
# BIG DEMO RUNNER (1000 events)
# ============================================================

def run_big_demo(n_steps=1000, noisy_rate=0.21):
    honest = Model("honest_model")
    noisy = Model("noisy_model")

    for step in range(n_steps):

        # ----- Honest Model -----
        e_h = create_event(is_bad=False)
        honest.update(e_h["consistency"])

        # ----- Noisy Model -----
        if random.random() < noisy_rate:
            e_n = create_event(is_bad=True)
            noisy.bad_count += 1
        else:
            e_n = create_event(is_bad=False)

        noisy.update(e_n["consistency"])

    # =====================================================
    # FINAL SUMMARY OUTPUT
    # =====================================================

    print("=== FINAL STATS ===\n")

    print("Model:", honest.name)
    print(f"  Bad proofs:        0 (0.0%)")
    print(f"  Final consistency: {honest.consistency_history[-1]:.3f}")
    print(f"  Final theta:       {honest.theta:.3f}")
    print(f"  Final w:           {honest.w:.3f}\n")

    print("Model:", noisy.name)
    bad_pct = (noisy.bad_count / n_steps) * 100
    print(f"  Bad proofs:        {noisy.bad_count} ({bad_pct:.1f}%)")
    print(f"  Final consistency: {noisy.consistency_history[-1]:.3f}")
    print(f"  Final theta:       {noisy.theta:.3f}")
    print(f"  Final w:           {noisy.w:.3f}\n")

    print("=== RUN COMPLETE ===")


# ============================================================
# RUN DEMO
# ============================================================

if __name__ == "__main__":
    run_big_demo(n_steps=1000, noisy_rate=0.21)
