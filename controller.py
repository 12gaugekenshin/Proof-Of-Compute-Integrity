# controller.py
class Controller:
    def __init__(self):
        self.state = {}  # model_id -> {'weight': float, 'theta': float}

    def _ensure(self, model_id: str):
        if model_id not in self.state:
            self.state[model_id] = {"weight": 1.0, "theta": 1.0}

    def update(self, model_id: str, valid: bool):
        self._ensure(model_id)
        m = self.state[model_id]

        if valid:
            # modest forgiveness
            m["weight"] = min(1.0, m["weight"] + 0.03)
            m["theta"] = max(0.5, m["theta"] - 0.08)
        else:
            # strong punishment
            m["weight"] = max(0.0, m["weight"] - 0.10)
            m["theta"] = min(5.0, m["theta"] + 0.30)

    def get(self, model_id: str):
        self._ensure(model_id)
        m = self.state[model_id]
        return m["weight"], m["theta"]

    def summary(self):
        print("\n=== FINAL CONTROLLER SUMMARY ===")
        for mid, m in sorted(self.state.items()):
            print(f"{mid:10s} | weight={m['weight']:.2f}, theta={m['theta']:.2f}")
