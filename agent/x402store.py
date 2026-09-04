from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from eth_account import Account

from .brain import _hash_intent
from .config import config
from .guard import Guard, cid_key
from .memory import MemoryStore, fmt_amount, now_iso
from .policy import PayRequest

# x402 (official SDK) drives the protocol; our memory guard interposes
# between the 402 and the signature - the signature is the point of no
# return, because anyone holding it can settle it.
try:
    from x402 import (
        AbortResult,
        PaymentRequired,
        PaymentResponseContext,
        x402ClientSync,
    )
    from x402.http.x402_http_client import x402HTTPClientSync
    from x402.mechanisms.evm.exact import ExactEvmScheme
    from x402 import prefer_network
    _X402_AVAILABLE = True
except Exception:  # pragma: no cover - exercised by tests via monkeypatching
    _X402_AVAILABLE = False

X402_BASE_SEPOLIA = "eip155:84532"
USDC_DECIMALS = 10 ** 6


class X402Error(Exception):
    """Raised when an x402 purchase cannot proceed."""


class X402Unavailable(X402Error):
    """The x402 layer is disabled (no SDK / no key / no memory)."""


def _require_stack() -> None:
    if not _X402_AVAILABLE:
        raise X402Unavailable("x402 SDK not installed (pip install 'x402[evm]')")
    if not config.private_key:
        raise X402Unavailable("BASE_PRIVATE_KEY is not set - nothing to sign with")


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _probe(url: str) -> tuple[int, dict, bytes]:
    """Plain GET with no payment machinery. Returns (status, headers, body)."""
    req = urllib.request.Request(url, headers={"User-Agent": "nunes-ai/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read() if hasattr(exc, "read") else b""


def _get(url: str, headers: dict) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "nunes-ai/0.1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read()
        except Exception:
            pass
        return exc.code, dict(exc.headers or {}), body


def _header(headers: dict, name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def parse_payment_required(status: int, headers: dict, body: bytes) -> PaymentRequired:
    """Parse a 402 into the SDK's PaymentRequired model (V2)."""
    http = _http_helper()
    parsed_body = None
    if body:
        try:
            parsed_body = json.loads(body.decode("utf-8"))
        except Exception:
            parsed_body = None
    return http.get_payment_required_response(_header_fn(headers), parsed_body)


def _header_fn(headers: dict):
    def get(name: str) -> str | None:
        return _header(headers, name)
    return get


_http_client_singleton: list = []


def _http_helper():
    if not _http_client_singleton:
        from x402 import x402ClientSync as _Sync
        _http_client_singleton.append(x402HTTPClientSync(_Sync()))
    return _http_client_singleton[0]


def choose_option(payment_required: PaymentRequired):
    """Pick the USDC-on-Base-Sepolia accept. Anything else is refused: the
    team's wallet, rules, and funding all live on that network/asset."""
    accepts = list(payment_required.accepts or [])
    for opt in accepts:
        if (opt.scheme == "exact"
                and opt.network == X402_BASE_SEPOLIA
                and (opt.asset or "").lower() == config.usdc_address.lower()):
            return opt
    raise X402Error(
        "no payable option: the resource offers no exact/USDC accept on "
        f"{X402_BASE_SEPOLIA} (offered: "
        + ", ".join(f"{a.scheme}/{a.network}/{a.asset}" for a in accepts)
        + ")"
    )


def _fmt_option(opt) -> str:
    units = int(opt.amount)
    return (f"{units / USDC_DECIMALS:.6f} USDC -> {opt.pay_to} "
            f"({opt.network}, {opt.scheme}, timeout {opt.max_timeout_seconds}s)")


def build_buy_client(*, memory: MemoryStore | None, actor: str, url: str,
                     budget_units: int | None) -> "x402ClientSync":
    """An x402 client whose signature is gated by Sibyl memory.

    The before-payment hook runs the full guard on the server's own terms
    (payTo + amount from the 402, never from the LLM): idempotency, vendor
    ban (address or host alias), rule cap, and the caller's budget. A refusal
    aborts the signature - nothing signable ever leaves the agent.
    """
    _require_stack()
    signer = Account.from_key(config.private_key)
    client = x402ClientSync()
    client.register(X402_BASE_SEPOLIA, ExactEvmScheme(signer))
    client.register_policy(prefer_network(X402_BASE_SEPOLIA))

    host = _host(url)

    def guard_hook(pctx) -> "AbortResult | None":
        # NOTE: the SDK's PaymentAbortedError carries only `reason`, so the
        # refusal evidence is embedded in the reason string itself.
        sel = pctx.selected_requirements
        try:
            amount_units = int(sel.amount)
        except (TypeError, ValueError):
            return AbortResult(reason=f"bad amount {sel.amount!r} in 402 - refused")
        pay_to = str(sel.pay_to or "")
        if budget_units is not None and amount_units > budget_units:
            return AbortResult(
                reason=(f"resource demands {amount_units / USDC_DECIMALS:.6f} USDC, "
                        f"above the {budget_units / USDC_DECIMALS:.6f} USDC budget - refused"))
        if memory is None:
            # Ablation: signing an EIP-3009 anyone can settle is the point of
            # no return, and there is no safe simulation of it - refuse.
            return AbortResult(reason="memory layer deleted - refusing to sign an unguarded x402 authorization")
        from .memory import normalize_address, BadAddress
        try:
            canonical = normalize_address(pay_to)
        except BadAddress:
            return AbortResult(reason=f"402 payTo {pay_to!r} is not a well-formed address - refused")

        intent_id = _hash_intent(f"x402:{url.strip().lower()}", to=canonical,
                                 amount_units=amount_units, denom="USDC")
        req = PayRequest(intent_id=intent_id, counterparty=canonical,
                         amount=amount_units, denom="USDC", alias=host or None,
                         incurred_at=now_iso())
        guard = Guard(memory)
        decision = guard.check(req)
        if not decision.allowed:
            guard.record_blocked(req, decision, actor=actor)
            evidence = "; ".join(decision.evidence)
            return AbortResult(reason=f"memory guard refused: {decision.reason} [{evidence}]")
        key = cid_key(req)
        if not memory.claim_intent(key, canonical, amount_units, "USDC"):
            return AbortResult(reason="this exact purchase is already paid or in flight - refusing to sign a duplicate")
        return None

    client.on_before_payment_creation(guard_hook)

    def journal_hook(pctx: PaymentResponseContext) -> None:
        # Best-effort journaling of the settlement result; never crash the flow.
        try:
            tx_hash = None
            settle = getattr(pctx, "settle_response", None)
            if settle is not None:
                tx_hash = getattr(settle, "transaction", None)
            sel = getattr(pctx, "requirements", None)
            if sel is not None:
                from .memory import normalize_address
                canonical = normalize_address(str(sel.pay_to))
                amount_units = int(sel.amount)
                intent_id = _hash_intent(f"x402:{url.strip().lower()}", to=canonical,
                                         amount_units=amount_units, denom="USDC")
                key = f"Chain/Intent/Denom:{intent_id}:USDC"
                memory.record_paid(key, canonical, amount_units, "USDC",
                                   str(tx_hash or "x402-settled"), mode="live", actor=actor)
                memory.write_event(
                    acted=[f"{actor.upper()} X402 {fmt_amount(amount_units)} -> {canonical} "
                           f"for {url} tx {tx_hash or 'unknown'}"],
                    extra={"kind": "x402", "actor": actor, "url": url,
                           "tx_hash": tx_hash, "key": key},
                )
        except Exception:
            pass

    client.on_payment_response(journal_hook)
    return client


def buy(memory: MemoryStore | None, actor: str, url: str,
        budget_usdc: float | None = None) -> str:
    """Buy a paywalled resource through x402, memory-guarded.

    1. Plain GET -> expect 402 + PAYMENT-REQUIRED (a 200 means it is free).
    2. Pick the USDC-on-Base-Sepolia accept; refuse anything else.
    3. Build a guarded client: the memory guard runs on the server's terms
       before anything is signed; a refusal aborts the signature.
    4. Retry with PAYMENT-SIGNATURE; surface the resource + settlement.
    """
    _require_stack()
    budget_units = int(round(float(budget_usdc) * USDC_DECIMALS)) if budget_usdc is not None else None

    status, headers, body = _probe(url)
    if status == 200:
        text = body.decode("utf-8", "replace")[:500]
        return f"NO PAYMENT NEEDED: {url} returned 200 without a challenge.\n{text}"
    if status != 402:
        raise X402Error(f"expected HTTP 402 from {url}, got {status}")

    payment_required = parse_payment_required(status, headers, body)
    option = choose_option(payment_required)
    if budget_units is not None and int(option.amount) > budget_units:
        return (f"BLOCKED: {url} demands {_fmt_option(option)}, above the "
                f"{budget_usdc} USDC budget - refused before signing.")

    client = build_buy_client(memory=memory, actor=actor, url=url,
                              budget_units=budget_units)
    http = x402HTTPClientSync(client)
    from x402 import PaymentAbortedError
    try:
        payload = client.create_payment_payload(payment_required)  # guard runs here
    except PaymentAbortedError as exc:
        return f"BLOCKED: {exc.reason}"
    sig_headers = http.encode_payment_signature_header(payload)
    status2, headers2, body2 = _get(url, dict(sig_headers))
    settle = None
    try:
        result = http.process_payment_result(payload, _header_fn(headers2), status2)
        settle = result.settle_response
    except Exception:
        pass
    tx_hash = (getattr(settle, "transaction", None) if settle else None
               ) or _header(headers2, "PAYMENT-RESPONSE")
    text = body2.decode("utf-8", "replace")[:2000]
    if status2 == 200:
        head = f"PAID via x402: {_fmt_option(option)}\n  resource: {url}"
        if tx_hash:
            head += f"\n  settlement: {tx_hash}"
        return head + f"\n  content:\n{text}"
    raise X402Error(f"paid request failed: HTTP {status2} from {url}\n{text[:500]}")
