# crypto_utils.py
import time
import hashlib
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


def now_ts() -> int:
    """Unix timestamp in seconds."""
    return int(time.time())


def hash_payload(model_id: str, index: int, prev_hash: str, payload: bytes, ts: int) -> str:
    """
    Deterministic hash over the event contents.
    In real life payload = hash(model_input || model_output).
    """
    h = hashlib.blake2b(digest_size=32)
    h.update(model_id.encode())
    h.update(index.to_bytes(8, "big"))
    h.update(prev_hash.encode())
    h.update(payload)
    h.update(ts.to_bytes(8, "big"))
    return h.hexdigest()


def generate_keypair():
    """Generate an Ed25519 keypair."""
    sk = SigningKey.generate()
    vk = sk.verify_key
    return sk, vk


def sign_event(sk: SigningKey, message: bytes) -> bytes:
    """Sign bytes with Ed25519 private key."""
    signed = sk.sign(message)
    return signed.signature  # just the signature part


def verify_signature(vk: VerifyKey, message: bytes, signature: bytes) -> bool:
    """Verify signature, returning True/False."""
    try:
        vk.verify(message, signature)
        return True
    except BadSignatureError:
        return False
