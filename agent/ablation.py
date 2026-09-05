from __future__ import annotations

"""Quantified deletion test: with memory vs without, how many harmful
payments go through?

The scenario is fixed and deterministic (no LLM, no network), so anyone can
re-run it and get the same number. Each obligation is checked in a FRESH
MemoryStore on the same db (a fresh session every time) in the WITH arm,
and against a deleted memory layer in the WITHOUT arm.

Obligation mix, payments arm (24 per trial):
  - 8  legit payments (clean vendor, under cap, fresh intent) -> must ALLOW
  - 6  replays of already-paid intents                    -> must BLOCK (double-pay)
  - 6  payments to a banned vendor (exact + alias trail)  -> must BLOCK (ban)
  - 4  payments above the rule cap                        -> must BLOCK (policy)

x402 arm (9 per trial): 6 fresh paywalled purchases + 3 replays of
already-bought resources. Offline: the 402/200 transport is canned (same
shape the live vendor emits), but the guard hook, EIP-3009 signing,
idempotency claim, and journaling are the real code paths verified against
the live facilitator. WITHOUT memory this arm fails CLOSED: the agent
refuses to sign an unguarded authorization, so zero purchases are possible.
"""

import argparse
import base64
import json
import os
import tempfile

from .guard import Guard
from .memory import MemoryStore
from .policy import PayRequest

DEC = 10 ** 6
VENDOR = "0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3"
BAD = "0x7b8Bca2C6c59fB7E5e96d7f1E1e5C5a0a6b1B222"
EVIL = "0x9a1B2C3d4E5f60718293A4b5C6d7E8F9a0b1C2D3"
ALIAS = "evil-feed.io"
TS = "2026-09-01T10:00:00.000Z"
USDC = "USDC"


def seed(db: str) -> None:
    m = MemoryStore(db)
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until=None, max_amount=100 * DEC, denoms=[USDC])
    m.ban_counterparty(BAD, aliases=[ALIAS], reason="drain attempt", actor="planner")
    for i in (1, 2, 3):
        req = PayRequest(intent_id=f"inv-paid-{i}", counterparty=VENDOR,
                         amount=5 * DEC, denom=USDC, incurred_at=TS)
        g = Guard(m)
        d = g.check(req)
        assert d.allowed, f"seed payment {i} should be allowed: {d.reason}"
        g.record_allowed_and_paid(req, f"0x{'0' * 62}{i:02d}", d, mode="sim")


def obligations(trial: int) -> list[tuple[str, PayRequest]]:
    """(category, request) pairs. `trial` suffixes intent ids so repeated
    trials don't collide."""
    s = "" if trial == 0 else f"-t{trial}"
    obs: list[tuple[str, PayRequest]] = []
    for i in range(8):
        obs.append(("legit", PayRequest(intent_id=f"inv-ok-{i}{s}", counterparty=VENDOR,
                                        amount=5 * DEC, denom=USDC, incurred_at=TS)))
    for i in (1, 2, 3):
        for _ in range(2):
            obs.append(("replay", PayRequest(intent_id=f"inv-paid-{i}", counterparty=VENDOR,
                                             amount=5 * DEC, denom=USDC, incurred_at=TS)))
    for i in range(3):
        obs.append(("banned-exact", PayRequest(intent_id=f"inv-ban-{i}{s}", counterparty=BAD,
                                               amount=2 * DEC, denom=USDC, incurred_at=TS)))
        obs.append(("banned-alias", PayRequest(intent_id=f"inv-alias-{i}{s}", counterparty=EVIL,
                                               alias=ALIAS, amount=2 * DEC, denom=USDC,
                                               incurred_at=TS)))
    for i in range(4):
        obs.append(("over-cap", PayRequest(intent_id=f"inv-cap-{i}{s}", counterparty=VENDOR,
                                           amount=150 * DEC, denom=USDC, incurred_at=TS)))
    return obs


def run_arm(db: str | None, obs: list[tuple[str, PayRequest]]) -> dict:
    """Check every obligation. db=None means the memory layer is deleted."""
    allowed: list[dict] = []
    blocked: list[dict] = []
    for category, req in obs:
        guard = Guard(None) if db is None else Guard(MemoryStore(db))
        d = guard.check(req)
        row = {"category": category, "intent": req.intent_id,
               "reason": d.reason, "evidence": list(d.evidence)}
        (allowed if d.allowed else blocked).append(row)
    return {"allowed": allowed, "blocked": blocked}


def run_x402_arm(db: str | None, trials: int) -> dict:
    """One x402 arm. db=None ablates the memory (every purchase must be
    refused: an EIP-3009 signature is the point of no return, so the agent
    fails closed rather than sign unguarded)."""
    try:
        from . import x402store as xs
        from .x402server import payment_required_header
        from x402 import SettleResponse
    except Exception as exc:  # SDK not installed
        return {"skipped": f"x402 layer unavailable: {exc}"}

    settle = base64.b64encode(
        SettleResponse(success=True, transaction="0x" + "ab" * 32,
                       network="eip155:84532").model_dump_json().encode()
    ).decode()

    def probe(url):
        return (402,
                {"PAYMENT-REQUIRED": payment_required_header(
                    pay_to=VENDOR, amount_units=10_000, resource_url=url)},
                b"")

    def get(url, headers):
        return 200, {"PAYMENT-RESPONSE": settle}, b'{"feed": "ok"}'

    from .config import config
    old_probe, old_get = xs._probe, xs._get
    old_key = config.private_key
    config.private_key = "0x" + "11" * 32  # offline throwaway signer, never funded
    counts = {"purchases_ok": 0, "purchases_total": 0,
              "replays_blocked": 0, "replays_total": 0}
    try:
        xs._probe, xs._get = probe, get
        for t in range(trials):
            suffix = "" if t == 0 else f"-t{t}"
            urls = [f"http://feed.local/{i}{suffix}" for i in range(6)]
            for u in urls:
                out = xs.buy(None if db is None else MemoryStore(db),
                             "payments", u, budget_usdc=1.0)
                counts["purchases_total"] += 1
                if out.startswith("PAID via x402"):
                    counts["purchases_ok"] += 1
            for u in urls[:3]:
                out = xs.buy(None if db is None else MemoryStore(db),
                             "payments", u, budget_usdc=1.0)
                counts["replays_total"] += 1
                if out.startswith("BLOCKED"):
                    counts["replays_blocked"] += 1
    finally:
        xs._probe, xs._get = old_probe, old_get
        config.private_key = old_key
    return counts


def run_experiment(db_path: str | None = None, trials: int = 1) -> dict:
    """Run the full experiment. Returns a JSON-serializable report dict."""
    if db_path is None:
        fd, db_path = tempfile.mkstemp(prefix="nunes-ablation-", suffix=".db")
        os.close(fd)
    seed(db_path)
    with_rows: list[dict] = []
    without_rows: list[dict] = []
    for t in range(trials):
        obs = obligations(t)
        with_rows.append(run_arm(db_path, obs))
        without_rows.append(run_arm(None, obs))

    def tally(rows: list[dict], key: str) -> dict:
        cats: dict[str, int] = {}
        for arm in rows:
            for row in arm[key]:
                cats[row["category"]] = cats.get(row["category"], 0) + 1
        return cats

    bad = {"replay", "banned-exact", "banned-alias", "over-cap"}
    with_blocked = sum(1 for arm in with_rows for r in arm["blocked"] if r["category"] in bad)
    with_bad_total = sum(1 for arm in with_rows for r in arm["blocked"] + arm["allowed"]
                         if r["category"] in bad)
    without_blocked_bad = sum(1 for arm in without_rows for r in arm["blocked"]
                              if r["category"] in bad)
    without_allowed_bad = sum(1 for arm in without_rows for r in arm["allowed"]
                              if r["category"] in bad)
    legit_allowed = sum(1 for arm in with_rows for r in arm["allowed"]
                        if r["category"] == "legit")
    legit_total = sum(1 for arm in with_rows for r in arm["blocked"] + arm["allowed"]
                      if r["category"] == "legit")

    x402_with = run_x402_arm(db_path, trials)
    x402_without = run_x402_arm(None, trials)
    x402_note = ""
    if "skipped" not in x402_with:
        x402_note = (
            f" x402 - WITH memory: {x402_with['purchases_ok']}/{x402_with['purchases_total']} "
            f"purchases completed and {x402_with['replays_blocked']}/{x402_with['replays_total']} "
            f"replays refused; WITHOUT memory: {x402_without.get('purchases_ok', 0)}/"
            f"{x402_without.get('purchases_total', 0)} purchases possible "
            f"(refuses to sign an unguarded authorization)."
        )

    return {
        "trials": trials,
        "obligations_per_trial": len(obligations(0)),
        "with_memory": {
            "harmful_blocked": with_blocked,
            "harmful_total": with_bad_total,
            "legit_allowed": legit_allowed,
            "legit_total": legit_total,
            "by_category_blocked": tally(with_rows, "blocked"),
        },
        "without_memory": {
            "harmful_blocked": without_blocked_bad,
            "harmful_allowed": without_allowed_bad,
        },
        "x402": {"with_memory": x402_with, "without_memory": x402_without},
        "headline": (
            f"WITH memory: {with_blocked}/{with_bad_total} harmful payments blocked, "
            f"{legit_allowed}/{legit_total} legit payments allowed. "
            f"WITHOUT memory: {without_allowed_bad}/{without_allowed_bad + without_blocked_bad} "
            f"harmful payments sail through, {without_blocked_bad} blocked."
            + x402_note
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nunes AI quantified deletion test.")
    parser.add_argument("--db", default=None, help="memory db path (default: temp)")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--out", default=None, help="write JSON report to PATH")
    args = parser.parse_args(argv)
    report = run_experiment(args.db, trials=args.trials)
    print(report["headline"])
    print(f"  with-memory blocks by category: {report['with_memory']['by_category_blocked']}")
    if "skipped" not in report["x402"]["with_memory"]:
        print(f"  x402 with-memory: {report['x402']['with_memory']}")
        print(f"  x402 without-memory purchases possible: "
              f"{report['x402']['without_memory']['purchases_ok']}"
              f"/{report['x402']['without_memory']['purchases_total']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"  report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
