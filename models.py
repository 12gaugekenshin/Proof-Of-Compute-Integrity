# models.py
from typing import Optional
from nacl.signing import SigningKey, VerifyKey
from crypto_utils import generate_keypair, hash_payload, sign_event, now_ts
from lineage import Event, LineageStore


class BaseModel:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.signing_key: SigningKey
        self.verify_key: VerifyKey
        self.signing_key, self.verify_key = generate_keypair()
        self.index = 0

    def make_event(
        self,
        store: LineageStore,
        payload: bytes,
        cheat: bool = False
    ) -> Event:
        prev = store.last_hash(self.model_id)
        ts = now_ts()
        payload_h = hash_payload(self.model_id, self.index, prev, payload, ts)

        # message to sign is the event hash input bytes
        msg_bytes = f"{self.model_id}|{self.index}|{prev}|{payload_h}|{ts}".encode()

        if cheat:
            # malicious: sign reversed message or random bytes
            msg_to_sign = msg_bytes[::-1]
        else:
            msg_to_sign = msg_bytes

        sig = sign_event(self.signing_key, msg_to_sign)

        # event hash = hash of the (correct) structure, independent of cheating
        ev_hash = hash_payload(self.model_id, self.index, prev, payload, ts)

        ev = Event(
            model_id=self.model_id,
            index=self.index,
            ts=ts,
            payload_hash=payload_h,
            prev_hash=prev,
            event_hash=ev_hash,
            signature=sig,
        )
        self.index += 1
        return ev


class HonestModel(BaseModel):
    pass  # uses cheat=False in run_demo


class AttackerModel(BaseModel):
    """
    Attacker that sometimes cheats on signing.
    Pattern controlled externally (e.g. every 3rd step).
    """
    pass
