import random
import uuid

# ============================================================
# MODEL CLASS (same 12g-ACE / 12g-AFL style controller)
# ============================================================

class Model:
    def __init__(self, name, alpha=0.05, beta=0.05):
        self.name = name
        self.theta = 0.0      # strictness
        self.w = 1.0          # trust weight
        self.alpha = alpha
        self.beta = beta
        self.consistency_history = []
        self.w_history = []
        self.theta_history = []
        self.bad_count = 0

    def update(self, s_t, is_bad):
        # record consistency
        self.consistency_history.append(s_t)
        if is_bad:
            self.bad_count += 1

        # update strictness
        self.theta += (1 - s_t) * self.alpha

        # update trust weight
        self.w += self.beta * (s_t - self.w)

        # store history
        self.w_history.append(self.w)
        self.theta_history.append(self.theta)


# ============================================================
# SINGLE MODEL RUN
# ============================================================

def run_single_model(n_steps=1000, noisy_rate=0.0, bad_low=0.0, bad_high=0.8, seed=None):
    """
    noisy_rate: probability of a bad proof per event (0.0 = fully honest)
    bad_low/bad_high: range for s_t on bad events
    seed: set for reproducible runs
    """
    if seed is not None:
        random.seed(seed)

    m = Model(f"noise_{noisy_rate:.2f}")

    for _ in range(n_steps):
        r = random.random()
        if r < noisy_rate:
            # bad / malformed proof
            s = random.uniform(bad_low, bad_high)
            m.update(s, is_bad=True)
        else:
            # honest event
            s = 1.0
            m.update(s, is_bad=False)

    mean_s = sum(m.consistency_history) / len(m.consistency_history)

    return {
        "name": m.name,
        "noise_rate": noisy_rate,
        "steps": n_steps,
        "bad_count": m.bad_count,
        "bad_pct": m.bad_count / n_steps * 100.0,
        "final_consistency": m.consistency_history[-1],
        "mean_consistency": mean_s,
        "final_theta": m.theta,
        "final_w": m.w,
    }


# ============================================================
# MAIN: PARAMETER SWEEP
# ============================================================

def main():
    N_STEPS = 1000
    NOISE_LEVELS = [0.0, 0.1, 0.2, 0.5]

    print("=== PoCI v7: Parameter Sweep over Noise Rates ===\n")
    print(f"Steps per run: {N_STEPS}")
    print("Noise levels tested: " + ", ".join(str(n) for n in NOISE_LEVELS) + "\n")

    print(f"{'noise':>6} | {'bad%':>6} | {'mean_s':>7} | {'final_w':>7} | {'theta':>7}")
    print("-" * 44)

    # summary table
    for i, nr in enumerate(NOISE_LEVELS):
        stats = run_single_model(n_steps=N_STEPS, noisy_rate=nr, seed=1234 + i)
        print(
            f"{nr:6.2f} | {stats['bad_pct']:6.1f} | "
            f"{stats['mean_consistency']:7.3f} | {stats['final_w']:7.3f} | "
            f"{stats['final_theta']:7.3f}"
        )

    # detailed blocks
    print("\nDetails by level:")
    for i, nr in enumerate(NOISE_LEVELS):
        stats = run_single_model(n_steps=N_STEPS, noisy_rate=nr, seed=1234 + i)
        block = (
            "\n--- Noise rate {nr:.2f} ---\n"
            "Bad proofs: {bad}/{steps} ({bad_pct:.1f}%)\n"
            "Mean consistency: {mean_s:.3f}\n"
            "Final consistency (last event): {final_s:.3f}\n"
            "Final theta: {theta:.3f}\n"
            "Final w: {w:.3f}\n"
        ).format(
            nr=nr,
            bad=stats["bad_count"],
            steps=stats["steps"],
            bad_pct=stats["bad_pct"],
            mean_s=stats["mean_consistency"],
            final_s=stats["final_consistency"],
            theta=stats["final_theta"],
            w=stats["final_w"],
        )
        print(block)


if __name__ == "__main__":
    main()
