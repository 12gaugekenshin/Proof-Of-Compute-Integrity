import random
import time

# ----------------------------------------------------------
# Adaptive PoCI Controller (per agent)
# ----------------------------------------------------------
class Controller:
    def __init__(self, name):
        self.name = name
        self.theta = 1.0   # scrutiny
        self.w = 1.0       # trust weight
        self.s = 0.0       # success score

    def update(self, sig_good):
        if sig_good:
            self.s = min(1.0, self.s + 0.02)
            self.w = min(1.0, self.w + 0.015)
            self.theta = max(1.0, self.theta - 0.02)
        else:
            self.s = max(0.0, self.s - 0.04)
            self.w = max(0.0, self.w - 0.03)
            self.theta = min(10.0, self.theta + 0.05)

    def __repr__(self):
        return f"s={self.s:.2f}|w={self.w:.2f}|θ={self.theta:.2f}"


# ----------------------------------------------------------
# PERSONALITY PROFILES
# ----------------------------------------------------------
def honest_noise():
    return random.uniform(0.0, 0.2)

def attacker_noise():
    return random.uniform(0.7, 1.0)

def opportunist_noise(theta):
    if theta > 4.0:
        return random.uniform(0.0, 0.2)   # play nice under scrutiny
    else:
        return random.uniform(0.2, 0.8)   # misbehave when trusted

def chaotic_noise():
    return random.uniform(0.0, 1.0)

def drifter_noise(step):
    base = (0.5 + 0.5 * random.random() * random.choice([-1, 1]))
    shift = (step % 100) / 100.0
    return min(1.0, max(0.0, base + shift / 3))


# ----------------------------------------------------------
# Proof validity from noise
# ----------------------------------------------------------
def noise_to_valid(noise):
    if noise == 0.0:
        return True
    if noise >= 0.9:
        return False
    return random.random() > noise


# ----------------------------------------------------------
# Assign random personalities (hidden)
# ----------------------------------------------------------
personalities = ["HONEST", "ATTACKER", "OPPORTUNIST", "CHAOTIC", "DRIFTER"]

agents = []
for i in range(50):
    persona = random.choice(personalities)
    agents.append({
        "name": f"AGENT_{i:02}",
        "persona": persona,   # hidden during simulation
        "ctrl": Controller(f"AGENT_{i:02}")
    })


# ----------------------------------------------------------
# Dynamic personality evolution (still hidden)
# ----------------------------------------------------------
def evolve_persona(agent, step):
    p = agent["persona"]

    if p == "ATTACKER" and step % 100 == 0:
        agent["persona"] = random.choice(["OPPORTUNIST", "DRIFTER"])

    elif p == "HONEST" and step % 120 == 0:
        agent["persona"] = random.choice(["HONEST", "OPPORTUNIST"])

    elif p == "OPPORTUNIST" and step % 150 == 0:
        agent["persona"] = random.choice(["HONEST", "CHAOTIC"])

    elif p == "CHAOTIC" and step % 80 == 0:
        agent["persona"] = random.choice(["DRIFTER", "HONEST"])

    elif p == "DRIFTER" and step % 100 == 0:
        agent["persona"] = random.choice(personalities)


# ----------------------------------------------------------
# Get noise without exposing persona
# ----------------------------------------------------------
def get_noise(agent, step):
    p = agent["persona"]
    ctrl = agent["ctrl"]

    if p == "HONEST":
        return honest_noise()
    if p == "ATTACKER":
        return attacker_noise()
    if p == "OPPORTUNIST":
        return opportunist_noise(ctrl.theta)
    if p == "CHAOTIC":
        return chaotic_noise()
    if p == "DRIFTER":
        return drifter_noise(step)


# ----------------------------------------------------------
# RUN SIMULATION (MYSTERY MODE)
# ----------------------------------------------------------
print("\n=== MYSTERY MODE: 50 AGENTS, NO PERSONALITY LABELS ===\n")

steps = 300

for step in range(1, steps + 1):

    for agent in agents:
        evolve_persona(agent, step)

        noise = get_noise(agent, step)
        sig_good = noise_to_valid(noise)
        agent["ctrl"].update(sig_good)

    if step % 50 == 0:

        print(f"\n--- SNAPSHOT at step {step} (Top 5 / Bottom 5) ---")

        sorted_agents = sorted(agents, key=lambda a: a["ctrl"].w, reverse=True)

        print("\nTOP 5 (HIGHEST TRUST):")
        for a in sorted_agents[:5]:
            print(a["name"], a["ctrl"])

        print("\nBOTTOM 5 (LOWEST TRUST):")
        for a in sorted_agents[-5:]:
            print(a["name"], a["ctrl"])

    time.sleep(0.05)


# ----------------------------------------------------------
# FINAL STATE (NO LABELS)
# ----------------------------------------------------------
print("\n=== FINAL STATE (Top 10) ===")
sorted_agents = sorted(agents, key=lambda a: a["ctrl"].w, reverse=True)
for a in sorted_agents[:10]:
    print(a["name"], a["ctrl"])


# ----------------------------------------------------------
# FINAL REVEAL — Persona truth table
# ----------------------------------------------------------
print("\n=== FINAL REVEAL: TRUE PERSONA OF EACH AGENT ===")
for agent in agents:
    print(agent["name"], "→", agent["persona"])
