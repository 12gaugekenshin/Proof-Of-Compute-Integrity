#!/usr/bin/env python3
import json, random, os
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

# ----------------------------------------------------------------------
# PO CI STATE MACHINE (adaptive trust)
# ----------------------------------------------------------------------

class PoCIState:
    def __init__(self):
        self.w = 1.0       # trust weight
        self.theta = 0.0   # strictness parameter

    def update(self, s_t):
        """
        Update the adaptive trust loop.
        s_t = 1.0 if signature verifies, else <1.
        """
        # trust-weight update
        self.w = max(0.0, min(1.0, self.w + 0.1 * (s_t - 1.0)))

        # strictness update
        self.theta += (1.0 - s_t)
        if self.theta < 0:
            self.theta = 0.0


# ----------------------------------------------------------------------
# EVENT: message → JSON → hash
# ----------------------------------------------------------------------
def create_event(i, prev_hash):
    return {
        "step": i,
        "prev": prev_hash,
        "payload": f"compute_output_{i}"
    }


def event_bytes(event):
    return json.dumps(event, sort_keys=True).encode()


# ----------------------------------------------------------------------
# SIGNATURE VALIDATION
# ----------------------------------------------------------------------
def sign_event(event, signing_key):
    msg = event_bytes(event)
    signature = signing_key.sign(msg).signature  # 64 bytes
    return signature


def verify_signature(event, verify_key, signature):
    msg = event_bytes(event)
    try:
        verify_key.verify(msg, signature)
        return True
    except BadSignatureError:
        return False


# ----------------------------------------------------------------------
# SAFE SIGNATURE CORRUPTION (keeps 64 bytes)
# ----------------------------------------------------------------------
def corrupt_signature(signature: bytes) -> bytes:
    """Flip one random byte so the signature stays 64 bytes but is invalid."""
    sig_list = list(signature)
    pos = os.urandom(1)[0] % 64
    sig_list[pos] ^= 0xFF  # flip bits
    return bytes(sig_list)


# ----------------------------------------------------------------------
# DEMO LOOP
# ----------------------------------------------------------------------
def run_demo(steps=20, noise_rate=0.25):
    print(f"Running Ed25519 PoCI demo — {steps} steps, noise={noise_rate}\n")

    # create real keys
    sk = SigningKey.generate()
    vk = sk.verify_key

    # create trust state
    state = PoCIState()

    prev_hash = "GENESIS"

    for i in range(1, steps + 1):

        # 1. Create event
        event = create_event(i, prev_hash)

        # 2. Sign correctly
        signature = sign_event(event, sk)

        # 3. Optional corruption for noisy models
        if random.random() < noise_rate:
            signature = corrupt_signature(signature)
            label = "BAD"
        else:
            label = "GOOD"

        # 4. Verify
        valid = verify_signature(event, vk, signature)
        s_t = 1.0 if valid else 0.0

        # 5. Update PoCI adaptive loop
        state.update(s_t)

        # 6. Derive hash-like value to chain events
        prev_hash = str(hash(event_bytes(event)))

        print(
            f"step {i:03d} | sig={label:<4} | s={s_t:.1f} | "
            f"w={state.w:.3f} | theta={state.theta:.3f}"
        )

    print("\n=== FINAL STATS ===")
    print(f"Bad proofs: {sum(1 for _ in range(steps) if random.random() < noise_rate)}?")
    print(f"Final w:     {state.w:.3f}")
    print(f"Final theta: {state.theta:.3f}")


# ----------------------------------------------------------------------
# RUN IT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    run_demo(steps=50, noise_rate=0.25)
