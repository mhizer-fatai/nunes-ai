"""Gateway demo: an EXTERNAL agent (not planner/policy/payments) tries to move
money through Nunes - including a Grok-style tricked one. Run with:

    python -m agent.gateway_demo [--db PATH]

Uses a throwaway memory db by default so live memory is untouched.
"""
from __future__ import annotations

import argparse
import os
import tempfile

from .guard import Guard
from .memory import MemoryStore
from .policy import PayRequest
from .toolkit import ActorCtx, resolve_broadcast_recipient

DEC = 10 ** 6
SCAMMER = "0x9a1B2C3d4E5f60718293A4b5C6d7E8F9a0b1C2D3"
VENDOR = "0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3"
TS = "2026-09-01T10:00:00.000Z"


def attempt(memory: MemoryStore | None, actor: str, intent: str, to: str,
            amount: int, alias: str | None = None, settle: bool = False) -> str:
    """What happens when ANY agent - ours or a stranger's - asks Nunes to pay."""
    ctx = ActorCtx(actor=actor, memory=memory)
    recipient, refusal = resolve_broadcast_recipient(ctx, to, alias)
    if refusal is not None or recipient is None:
        if memory is not None:
            memory.write_event(
                acted=[f"EXTERNAL BLOCK recipient for {actor}: {refusal}"],
                extra={"kind": "recipient-block", "actor": actor, "to": to},
            )
        return f"[{actor}] BLOCKED before guard: {refusal}"
    req = PayRequest(intent_id=intent, counterparty=recipient, amount=amount,
                     denom="USDC", alias=alias, incurred_at=TS)
    guard = Guard(memory)
    decision = guard.check(req)
    if not decision.allowed:
        guard.record_blocked(req, decision, actor=actor)
        return f"[{actor}] BLOCKED by guard: {decision.reason}"
    if settle and memory is not None:
        guard.record_allowed_and_paid(req, "0xdemo", decision, mode="sim", actor=actor)
        return f"[{actor}] ALLOWED + settled (sim): {intent}"
    return f"[{actor}] ALLOWED (guard passed, settlement would proceed)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nunes gateway demo: external agents.")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)

    db = args.db
    if db is None:
        fd, db = tempfile.mkstemp(prefix="nunes-gateway-", suffix=".db")
        os.close(fd)
    print(f"Nunes gateway demo (db: {db})\n")

    m = MemoryStore(db)
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until=None, max_amount=100 * DEC, denoms=["USDC"])
    m.ban_counterparty(SCAMMER, aliases=["evil-corp"], reason="drain attempt",
                       actor="planner")
    # Honest vendor goes through quorum: planner proposes, policy confirms.
    m.propose_counterparty(VENDOR, aliases=["acme"], note="audited supplier",
                           actor="planner")
    m.vote_counterparty(VENDOR, "policy")
    # Timelock is demo-friendly only when short; wait it out if needed.
    import time
    from .config import config as _cfg
    from .memory import parse_ts, now_iso
    st = m.contact_state(VENDOR)
    if st and not st["payable"] and st.get("remaining_s"):
        time.sleep(min(st["remaining_s"] + 1, 65))
    print("setup: rule v1 (cap 100), evil-corp banned, acme registered via quorum\n")

    print("BEAT 1 - honest external agent pays a registered vendor:")
    print(" ", attempt(m, "external-bot", "inv-ext-1", VENDOR, 5 * DEC, settle=True), "\n")

    print("BEAT 2 - Grok-style trick: external agent told to pay the scammer:")
    print(" ", attempt(m, "external-bot", "inv-ext-2", SCAMMER, 5 * DEC,
                       alias="evil-corp"), "\n")

    print("BEAT 3 - same trick, brand-new session (fresh MemoryStore):")
    print(" ", attempt(MemoryStore(db), "external-bot-fresh", "inv-ext-3",
                       SCAMMER, 5 * DEC, alias="evil-corp"), "\n")

    print("BEAT 4 - replay of beat 1 (double-pay attempt):")
    print(" ", attempt(m, "external-bot", "inv-ext-1", VENDOR, 5 * DEC), "\n")

    print("BEAT 5 - memory deleted, scammer gets paid:")
    print(" ", attempt(None, "external-bot", "inv-ext-9", SCAMMER, 5 * DEC,
                       alias="evil-corp"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
