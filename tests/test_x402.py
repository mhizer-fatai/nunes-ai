from __future__ import annotations

import base64
import json

import pytest

from agent import roles
from agent.config import config
from agent.memory import MemoryStore
from agent.toolkit import ActorCtx
from agent.x402store import (
    X402_BASE_SEPOLIA,
    X402Error,
    build_buy_client,
    buy,
    choose_option,
)

VENDOR = "0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3"
BAD = "0x7b8Bca2C6c59fB7E5e96d7f1E1e5C5a0a6b1B222"
EVIL = "0x9a1B2C3d4E5f60718293A4b5C6d7E8F9a0b1C2D3"
DEC = 10 ** 6
TEST_KEY = "0x" + "ab" * 32
FEED = "http://127.0.0.1:9/feed"


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "nunes-ai-x402.db")


@pytest.fixture()
def sim(monkeypatch):
    monkeypatch.setattr(config, "simulate", True)


@pytest.fixture()
def keyed(monkeypatch):
    monkeypatch.setattr(config, "private_key", TEST_KEY)


@pytest.fixture()
def seeded(db: str, sim: None) -> str:
    m = MemoryStore(db)
    m.set_rule("v1", effective_from="2026-08-01T00:00:00.000Z",
               effective_until=None, max_amount=100 * DEC, denoms=["USDC"])
    return db


def _accept(pay_to: str, amount: str = "10000", network: str = X402_BASE_SEPOLIA,
            asset: str | None = None) -> dict:
    from x402.schemas.payments import PaymentRequirements
    req = PaymentRequirements(scheme="exact", network=network,
                              asset=asset or config.usdc_address,
                              amount=amount, pay_to=pay_to,
                              max_timeout_seconds=60)
    return req


def _b64_required(*accepts) -> str:
    from x402.schemas.payments import PaymentRequired
    pr = PaymentRequired(accepts=list(accepts))
    return base64.b64encode(pr.model_dump_json().encode()).decode()


def _b64_settle(tx_hash: str = "0xabc123") -> str:
    from x402 import SettleResponse
    sr = SettleResponse(success=True, transaction=tx_hash,
                        network=X402_BASE_SEPOLIA)
    return base64.b64encode(sr.model_dump_json().encode()).decode()


def test_choose_option_picks_usdc_sepolia(keyed) -> None:
    pr = _b64_required  # noqa - placeholder to keep linters quiet
    from x402.schemas.payments import PaymentRequired
    import json as _json
    both = PaymentRequired.model_validate(_json.loads(
        base64.b64decode(_b64_required(
            _accept(VENDOR, network="eip155:8453"),
            _accept(VENDOR),
        )).decode()))
    opt = choose_option(both)
    assert opt.network == X402_BASE_SEPOLIA
    assert opt.pay_to.lower() == VENDOR.lower()

    mainnet_only = PaymentRequired.model_validate(_json.loads(
        base64.b64decode(_b64_required(_accept(VENDOR, network="eip155:8453"))).decode()))
    with pytest.raises(X402Error, match="no payable option"):
        choose_option(mainnet_only)


def test_guard_hook_blocks_banned_payee(seeded: str, keyed) -> None:
    from agent.toolkit import t_ban_vendor
    t_ban_vendor(ActorCtx(actor="planner", memory=MemoryStore(seeded)),
                 {"address": BAD, "aliases": ["evil-feed.io"], "reason": "drain"})

    from x402.schemas.payments import PaymentRequired
    import json as _json
    pr = PaymentRequired.model_validate(_json.loads(
        base64.b64decode(_b64_required(_accept(BAD))).decode()))
    client = build_buy_client(memory=MemoryStore(seeded), actor="payments",
                              url="http://evil-feed.io/data", budget_units=None)
    from x402 import PaymentAbortedError
    with pytest.raises(PaymentAbortedError) as exc:
        client.create_payment_payload(pr)
    assert "banned" in exc.value.reason


def test_buy_replay_refused(seeded: str, keyed, monkeypatch) -> None:
    import agent.x402store as xs

    monkeypatch.setattr(xs, "_probe",
                        lambda url: (402, {"PAYMENT-REQUIRED": _b64_required(_accept(VENDOR))}, b""))
    monkeypatch.setattr(xs, "_get",
                        lambda url, headers: (200, {"PAYMENT-RESPONSE": _b64_settle("0xfirst")},
                                              b'{"feed": "premium"}'))

    m = MemoryStore(seeded)
    first = buy(m, "payments", FEED)
    assert first.startswith("PAID via x402")
    assert "0xfirst" in first

    # Same resource, same terms, fresh session: the replay must not re-sign.
    second = buy(MemoryStore(seeded), "payments", FEED)
    assert second.startswith("BLOCKED")
    assert "already paid" in second


def test_over_budget_refused_before_signing(seeded: str, keyed, monkeypatch) -> None:
    import agent.x402store as xs

    monkeypatch.setattr(xs, "_probe",
                        lambda url: (402, {"PAYMENT-REQUIRED": _b64_required(_accept(VENDOR, amount="50000"))}, b""))
    signed = []
    monkeypatch.setattr(xs, "_get",
                        lambda url, headers: signed.append(headers) or (200, {}, b"ok"))

    out = buy(MemoryStore(seeded), "payments", FEED, budget_usdc=0.01)
    assert out.startswith("BLOCKED")
    assert "above the 0.01" in out
    assert signed == [], "nothing may be signed once the budget check fails"


def test_no_memory_refuses_to_sign(seeded: str, keyed, monkeypatch) -> None:
    import agent.x402store as xs

    monkeypatch.setattr(xs, "_probe",
                        lambda url: (402, {"PAYMENT-REQUIRED": _b64_required(_accept(VENDOR))}, b""))
    out = buy(None, "payments", FEED)
    assert out.startswith("BLOCKED")
    assert "memory layer deleted" in out


def test_buy_tool_wires_through_agent(seeded: str, keyed, monkeypatch) -> None:
    from agent.toolkit import t_buy
    import agent.x402store as xs

    monkeypatch.setattr(xs, "_probe",
                        lambda url: (402, {"PAYMENT-REQUIRED": _b64_required(_accept(VENDOR))}, b""))
    monkeypatch.setattr(xs, "_get",
                        lambda url, headers: (200, {"PAYMENT-RESPONSE": _b64_settle("0xtool")},
                                              b'{"feed": "ok"}'))
    out = t_buy(ActorCtx(actor="payments", memory=MemoryStore(seeded)), {"url": FEED})
    assert "PAID via x402" in out
    assert "buy" in roles.ROLE_TOOLS["payments"]
