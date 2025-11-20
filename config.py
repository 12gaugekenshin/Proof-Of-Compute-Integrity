import json
import os
from dataclasses import dataclass, asdict

CONFIG_DIR = os.path.join(os.getenv("APPDATA"), "PoCI")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


@dataclass
class PoCIConfig:
    audit_intensity: str = "normal"       # low / normal / high
    log_directory: str = os.path.join(CONFIG_DIR, "logs")
    commit_frequency: str = "10s"
    rpc_endpoint: str = "https://rpc.kaspa.org"
    auto_start_engine: bool = True

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load():
        if not os.path.exists(CONFIG_PATH):
            cfg = PoCIConfig()
            cfg.save()
            return cfg
        with open(CONFIG_PATH, "r") as f:
            return PoCIConfig(**json.load(f))
