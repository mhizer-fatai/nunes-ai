from __future__ import annotations

import os
import tempfile

import pytest

from agent.guard import Guard
from agent.memory import MemoryStore
from agent.policy import PayRequest

VENDOR = "0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3B"
BAD_VENDOR_ADDR = "0x7b8Bca2C6c59fB7E5e96d7f1E1e5C5a0a6b1B222"
EVIL = "0x9a1B2C3d4E5f60718293A4b5C6d7E8F9a0b1C2D3"
DEC = 10 ** 6


@pytest.fixture()
def db(tmp_path) -> str:
    return str(tmp_path / "nunes-ai-test.db")


@pytest.fixture()
def seeded(db: str) -> None:
    m = MemoryStore(db)
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until="2026-08-31T23:59:59.000Z",
               max_amount=100 * DEC, denoms=["USDC"])
    m.set_rule("v2", effective_from="2026-09-01T00:00:00.000Z",
               effective_until=None, max_amount=10 * DEC, denoms=["USDC"])
    m.ban_counterparty(BAD_VENDOR_ADDR, aliases=["data-feed.io"],
                       reason="drain attempt")


def test_idempotency_across_fresh_sessions(db: str, seeded: None) -> None:
    """Session 1 pays; a genuinely fresh MemoryStore (new session, same db)
    must refuse the replay."""
    first = Guard(MemoryStore(db))
    req = PayRequest(intent_id="inv-1", counterparty=VENDOR,
                     amount=5 * DEC, incurred_at="2026-08-30T10:00:00.000Z")
    d1 = first.check(req)
    assert d1.allowed
    first.record_allowed_and_paid(req, "0xabc", d1)

    second = Guard(MemoryStore(db))  # fresh session, same persistent memory
    d2 = second.check(req)
    assert not d2.allowed
    assert "double-spend" in d2.reason


def test_banned_counterparty_via_alias(db: str, seeded: None) -> None:
    """A banned vendor reappearing under a NEW address is still refused:
    FTS5 recall of the alias trail in the journal."""
    m = MemoryStore(db)
    guard = Guard(m)
    req = PayRequest(intent_id="inv-2", counterparty=EVIL, alias="data-feed.io",
                     amount=2 * DEC, incurred_at="2026-09-01T10:00:00.000Z")
    d = guard.check(req)
    assert not d.allowed
    assert "banned" in d.reason


def test_temporal_rule_recall(db: str, seeded: None) -> None:
    """50 USDC is legal under the rule in force on Aug 25 (v1, cap 100) but
    illegal under the rule in force on Sep 1 (v2, cap 10)."""
    m = MemoryStore(db)
    guard = Guard(m)

    old = PayRequest(intent_id="inv-3", counterparty=VENDOR,
                     amount=50 * DEC, incurred_at="2026-08-25T10:00:00.000Z")
    d_old = guard.check(old)
    assert d_old.allowed and d_old.rule_version == "v1"

    new = PayRequest(intent_id="inv-4", counterparty=VENDOR,
                     amount=50 * DEC, incurred_at="2026-09-01T09:00:00.000Z")
    d_new = guard.check(new)
    assert not d_new.allowed
    assert "exceeds limit" in d_new.reason


def test_ablation_allows_double_pay() -> None:
    """Delete the memory layer and the same request sails through again -
    that is the double-pay the whole project exists to prevent."""
    m = MemoryStore(os.path.join(tempfile.gettempdir(), "nunes-ai-abl.db"))
    guard = Guard(m)
    req = PayRequest(intent_id="inv-x", counterparty=VENDOR,
                     amount=5 * DEC, incurred_at="2026-09-01T10:00:00.000Z")
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until=None, max_amount=100 * DEC, denoms=["USDC"])
    guard.record_allowed_and_paid(req, "0xfirst", guard.check(req))

    naked = Guard(None)  # memory deleted
    d = naked.check(req)
    assert d.allowed
