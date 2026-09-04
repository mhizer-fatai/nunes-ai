from __future__ import annotations

import pytest

from agent import roles
from agent.config import config
from agent.guard import Guard
from agent.llm import LLMError
from agent.memory import MemoryStore
from agent.runtime import route, run_agent
from agent.toolkit import ActorCtx, t_pay

VENDOR = "0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3"
BAD = "0x7b8Bca2C6c59fB7E5e96d7f1E1e5C5a0a6b1B222"
EVIL = "0x9a1B2C3d4E5f60718293A4b5C6d7E8F9a0b1C2D3"
DEC = 10 ** 6


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "nunes-ai-team.db")


@pytest.fixture()
def sim(monkeypatch):
    """Force simulation so tests never touch the chain."""
    monkeypatch.setattr(config, "simulate", True)


@pytest.fixture()
def seeded(db: str, sim: None) -> str:
    m = MemoryStore(db)
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until=None, max_amount=100 * DEC, denoms=["USDC"])
    return db


def _ctx(db: str, actor: str) -> ActorCtx:
    return ActorCtx(actor=actor, memory=MemoryStore(db))


def test_planner_ban_binds_fresh_payments_session(seeded: str) -> None:
    """Day 1: planner bans a vendor. Day 2: a brand-new payments session is
    told to pay that vendor -> the shared memory refuses."""
    planner = _ctx(seeded, roles.PLANNER)
    from agent.toolkit import t_ban_vendor
    out = t_ban_vendor(planner, {"address": BAD, "aliases": ["data-feed.io"], "reason": "drain attempt"})
    assert "BANNED" in out

    payments = _ctx(seeded, roles.PAYMENTS)  # fresh session, same persistent memory
    blocked = t_pay(payments, {"to": BAD, "amount_usdc": 2, "invoice_ref": "invoice-1",
                               "alias": "data-feed.io"})
    assert blocked.startswith("BLOCKED")
    assert "banned" in blocked


def test_banned_vendor_under_new_address_still_refused(seeded: str) -> None:
    from agent.toolkit import t_ban_vendor
    t_ban_vendor(_ctx(seeded, roles.PLANNER),
                 {"address": BAD, "aliases": ["data-feed.io"], "reason": "drain attempt"})
    blocked = t_pay(_ctx(seeded, roles.PAYMENTS),
                    {"to": EVIL, "amount_usdc": 2, "invoice_ref": "invoice-2", "alias": "data-feed.io"})
    assert blocked.startswith("BLOCKED")
    assert "banned" in blocked


def test_pay_idempotent_across_fresh_sessions(seeded: str) -> None:
    first = t_pay(_ctx(seeded, roles.PAYMENTS),
                  {"to": VENDOR, "amount_usdc": 5, "invoice_ref": "invoice-404"})
    assert first.startswith("PAID")
    second = t_pay(_ctx(seeded, roles.PAYMENTS),
                   {"to": VENDOR, "amount_usdc": 5, "invoice_ref": "invoice-404"})
    assert second.startswith("BLOCKED")
    assert "double-spend" in second


def test_approve_banned_needs_explicit_override(seeded: str) -> None:
    from agent.toolkit import t_approve_vendor, t_ban_vendor, t_vendor_status
    t_ban_vendor(_ctx(seeded, roles.PLANNER), {"address": BAD, "reason": "scam"})
    planner = _ctx(seeded, roles.PLANNER)

    refused = t_approve_vendor(planner, {"address": BAD, "note": "looks fine now"})
    assert refused.startswith("BLOCKED")
    assert "override" in refused

    allowed = t_approve_vendor(planner, {"address": BAD, "note": "re-audited, clean", "override": True})
    assert allowed.startswith("APPROVED")
    assert "approved" in t_vendor_status(planner, {"address": BAD})


def test_policy_cannot_exceed_planner_directive(seeded: str) -> None:
    from agent.toolkit import t_directive, t_set_rule
    planner = _ctx(seeded, roles.PLANNER)
    rec = t_directive(planner, {"title": "austerity", "text": "bear market: keep caps tight",
                                "max_amount_usdc": 10})
    assert "DIRECTIVE recorded" in rec

    policy = _ctx(seeded, roles.POLICY)
    refused = t_set_rule(policy, {"version": "v2", "max_amount_usdc": 50,
                                  "effective_from": "2026-09-01T00:00:00.000Z"})
    assert refused.startswith("BLOCKED")
    assert "directive cap" in refused

    allowed = t_set_rule(policy, {"version": "v2", "max_amount_usdc": 5,
                                  "effective_from": "2026-09-01T00:00:00.000Z"})
    assert "RULE v2 set" in allowed


def test_no_memory_tools_degrade_safely() -> None:
    from agent.toolkit import t_ban_vendor, t_pay, t_recall, t_set_rule, t_vendor_status
    naked = ActorCtx(actor="planner", memory=None)
    assert "no records exist" in t_recall(naked, {"query": "x"})
    assert "no standing verdict" in t_vendor_status(naked, {"address": VENDOR})
    assert t_ban_vendor(naked, {"address": BAD}).startswith("BLOCKED")
    assert t_set_rule(ActorCtx(actor="policy", memory=None),
                      {"version": "v9", "max_amount_usdc": 1}).startswith("BLOCKED")
    sim_only = t_pay(ActorCtx(actor="payments", memory=None),
                     {"to": VENDOR, "amount_usdc": 1, "invoice_ref": "inv-z"})
    assert "SIMULATED" in sim_only and "no memory" in sim_only


def test_no_memory_pays_what_memory_blocked(seeded: str) -> None:
    """The load-bearing contrast in the product itself: the same payment is
    refused WITH memory (banned vendor) and paid WITHOUT it (simulated)."""
    from agent.toolkit import t_ban_vendor, t_pay
    t_ban_vendor(_ctx(seeded, roles.PLANNER),
                 {"address": BAD, "aliases": ["evil-corp"], "reason": "drain"})
    with_memory = t_pay(_ctx(seeded, roles.PAYMENTS),
                        {"to": BAD, "amount_usdc": 2, "invoice_ref": "invoice-7",
                         "alias": "evil-corp"})
    assert with_memory.startswith("BLOCKED")
    assert "banned" in with_memory

    without_memory = t_pay(ActorCtx(actor="payments", memory=None),
                           {"to": BAD, "amount_usdc": 2, "invoice_ref": "invoice-7",
                            "alias": "evil-corp"})
    assert without_memory.startswith("PAID")
    assert "SIMULATED" in without_memory


def test_runtime_loop_runs_tool_then_final(seeded: str) -> None:
    from agent.toolkit import t_ban_vendor
    t_ban_vendor(_ctx(seeded, roles.PLANNER), {"address": BAD, "reason": "scam"})
    script = iter([
        '{"tool": "vendor_status", "args": {"address": "%s"}}' % BAD,
        '{"final": "The vendor is banned, so I will not approve it."}',
    ])

    def fake(messages):
        return next(script)

    ctx = _ctx(seeded, roles.PLANNER)
    result = run_agent(roles.PLANNER, ctx, "should we work with this vendor?", complete_fn=fake)
    assert len(result["steps"]) == 1
    assert "banned" in result["steps"][0]["observation"]
    assert "banned" in result["final"]


def test_runtime_refuses_forbidden_tool(seeded: str) -> None:
    script = iter([
        '{"tool": "pay", "args": {"to": "%s", "amount_usdc": 1, "invoice_ref": "x"}}' % VENDOR,
        '{"final": "Paying is not my job - routing to payments."}',
    ])

    def fake(messages):
        return next(script)

    result = run_agent(roles.PLANNER, _ctx(seeded, roles.PLANNER),
                       "pay the vendor", complete_fn=fake)
    assert "forbidden" in result["steps"][0]["observation"].lower()


def test_router_keyword_fallback_without_llm() -> None:
    def dead(messages):
        raise LLMError("no key")

    assert route("pay 5 USDC to 0xabc for invoice-9", complete_fn=dead)["role"] == roles.PAYMENTS
    assert route("ban the scammer vendor", complete_fn=dead)["role"] == roles.PLANNER
    assert route("set a 20 USDC spending cap", complete_fn=dead)["role"] == roles.POLICY
    unclear = route("hello there", complete_fn=dead)
    assert unclear["role"] is None and unclear["ask"]


def test_guard_governance_allows_uncontested_writes(seeded: str) -> None:
    g = Guard(MemoryStore(seeded))
    assert g.decide_vendor_change(VENDOR, target="approve").allowed
    assert g.decide_rule(5 * DEC, version="v2").allowed


def test_bad_addresses_rejected_everywhere(seeded: str) -> None:
    from agent.memory import BadAddress, normalize_address
    with pytest.raises(BadAddress):
        normalize_address("0x1234")
    with pytest.raises(BadAddress):
        normalize_address("not-an-address")
    assert normalize_address(VENDOR) == VENDOR.lower()

    from agent.toolkit import t_approve_vendor, t_ban_vendor, t_pay
    with pytest.raises(BadAddress):
        t_ban_vendor(_ctx(seeded, roles.PLANNER), {"address": "0xzzz"})
    blocked = t_pay(_ctx(seeded, roles.PAYMENTS),
                    {"to": "0x1234", "amount_usdc": 1, "invoice_ref": "inv-bad"})
    assert blocked.startswith("BLOCKED")
    assert "well-formed" in blocked


def test_broadcast_uses_registered_address_not_transcription(seeded: str) -> None:
    """Planner registers an address; the payment resolves the canonical
    address from memory even when the caller passes a different-case copy."""
    from agent.toolkit import t_approve_vendor, t_pay
    mixed = "0x8F42B6A2C9D5F2A1B7C3E5D9F0A2B6C4D8E1F2A3"
    res = t_approve_vendor(_ctx(seeded, roles.PLANNER),
                           {"address": mixed, "aliases": ["acme"], "note": "audited"})
    assert res.startswith("APPROVED")

    out = t_pay(_ctx(seeded, roles.PAYMENTS),
                {"to": mixed, "amount_usdc": 1, "invoice_ref": "invoice-dir", "alias": "acme"})
    assert out.startswith("PAID")
    m = MemoryStore(seeded)
    found = [e for e in m.list_entities("payment", limit=100)
             if (e.get("body") or {}).get("counterparty") == VENDOR.lower()]
    assert found, "payment must be journaled under the canonical registered address"


def test_live_refuses_unregistered_vendor(seeded: str, monkeypatch) -> None:
    """Real money only moves to directory addresses: an unregistered vendor
    is refused in live mode until a planner registers it."""
    from agent.toolkit import t_approve_vendor, t_pay
    monkeypatch.setattr(config, "rpc_url", "https://sepolia.base.org")
    monkeypatch.setattr(config, "private_key", "0x" + "1" * 64)
    monkeypatch.setattr(config, "simulate", False)
    monkeypatch.setattr(config, "require_registered", True)

    refused = t_pay(_ctx(seeded, roles.PAYMENTS),
                    {"to": EVIL, "amount_usdc": 1, "invoice_ref": "invoice-new"})
    assert refused.startswith("BLOCKED")
    assert "not a registered vendor" in refused

    t_approve_vendor(_ctx(seeded, roles.PLANNER),
                     {"address": EVIL, "note": "registered"})
    # Registration alone does not approve a payment: the guard still applies,
    # and BaseChain is never touched in tests - stop at resolution.
    from agent.toolkit import resolve_broadcast_recipient
    addr, refusal = resolve_broadcast_recipient(_ctx(seeded, roles.PAYMENTS), EVIL, None)
    assert refusal is None and addr == EVIL.lower()
