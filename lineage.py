# lineage.py
from dataclasses import dataclass
from typing import Optional, List, Dict
from crypto_utils import hash_payload, now_ts


@dataclass
class Event:
    model_id: str
    index: int
    ts: int
    payload_hash: str
    prev_hash: str
    event_hash: str
    signature: bytes


class LineageStore:
    """
    Simple in-memory storage.
    In reality this could be a DB, IPFS, etc.
    """
    def __init__(self):
        self.events_by_model: Dict[str, List[Event]] = {}

    def append(self, event: Event):
        self.events_by_model.setdefault(event.model_id, []).append(event)

    def last_hash(self, model_id: str) -> str:
        events = self.events_by_model.get(model_id, [])
        if not events:
            return "GENESIS"
        return events[-1].event_hash

    def get_chain(self, model_id: str) -> List[Event]:
        return self.events_by_model.get(model_id, [])
