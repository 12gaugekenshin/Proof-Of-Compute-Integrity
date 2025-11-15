# run_demo.py
from nacl.signing import VerifyKey
from crypto_utils import verify_signature
from lineage import LineageStore
from models import HonestModel, AttackerModel
from controller import Controller


def verify_event(event, vk: VerifyKey, controller: Controller, phase: str):
    # Reconstruct the *correct* message that SHOULD have been signed
    msg_bytes = f"{event.model_id}|{event.index}|{event.prev_hash}|{event.payload_hash}|{event.ts}".encode()

    ok = verify_signature(vk, msg_bytes, event.signature)
    controller.update(event.model_id, ok)
    w, t = controller.get(event.model_id)
    status = "GOOD" if ok else "BAD"
    print(f"[{phase:9s}] idx={event.index:03d} | {event.model_id:10s} | {status} | w={w:.2f}, θ={t:.2f}")
    return ok


if __name__ == "__main__":
    store = LineageStore()
    ctrl = Controller()

    honest = HonestModel("honest_core")
    attacker = AttackerModel("attacker")

    models = [honest, attacker]

    # PHASE 1: honest behavior from both
    print("=== PHASE 1: BOTH HONEST ===")
    for step in range(5):
        for m in models:
            ev = m.make_event(store, payload=b"some_ai_compute", cheat=False)
            store.append(ev)
            verify_event(ev, m.verify_key, ctrl, "BOOTSTRAP")

    # PHASE 2: attacker starts cheating periodically
    print("\n=== PHASE 2: ATTACKER CHEATS EVERY OTHER EVENT ===")
    for step in range(10):
        # honest always good
        ev_h = honest.make_event(store, payload=b"some_ai_compute", cheat=False)
        store.append(ev_h)
        verify_event(ev_h, honest.verify_key, ctrl, "ATTACK")

        # attacker: cheat on odd steps
        cheat = (step % 2 == 1)
        ev_a = attacker.make_event(store, payload=b"evil_ai_compute", cheat=cheat)
        store.append(ev_a)
        verify_event(ev_a, attacker.verify_key, ctrl, "ATTACK")

    ctrl.summary()
    print("\n=== REAL-CRYPTO DEMO COMPLETE ===")
