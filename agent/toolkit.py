from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .brain import _hash_intent
from .chain import BaseChain, simulate_transfer
from .config import config
from .guard import Guard, cid_key
from .memory import CAT_PAYMENT, MemoryStore, fmt_amount, now_iso, parse_ts
from .policy import PayRequest

USDC_DECIMALS = 10 ** 6


def _to_units(amount_usdc: float) -> int:
    return int(round(float(amount_usdc) * USDC_DECIMALS))


@dataclass
class ActorCtx:
    """Everything a tool needs: the shared memory and whose hands it runs in."""
    actor: str
    memory: MemoryStore | None


def _need_memory(ctx: ActorCtx) -> MemoryStore | None:
    return ctx.memory


def _fmt_recall(rec: dict) -> str:
    lines: list[str] = []
    for hit in rec.get("matches", []):
        lines.append(f"  memory: {hit}")
    for ev in rec.get("events", []):
        lines.append(f"  journal: {ev}")
    rule = rec.get("latest_rule")
    if rule:
        body = rule.get("body") or {}
        lines.append(
            f"  standing rule {rule.get('name')}: cap "
            f"{fmt_amount(int(body.get('max_amount', 0)))} from {body.get('effective_from')}"
        )
    d = rec.get("latest_directive")
    if d:
        body = d.get("body") or {}
        cap = body.get("max_amount")
        lines.append(
            f"  standing directive '{body.get('title')}': {body.get('text')}"
            + (f" (cap {fmt_amount(int(cap))})" if cap is not None else "")
        )
    if not lines:
        return "recall: memory holds nothing relevant to that query."
    return "recall:\n" + "\n".join(lines)


def t_recall(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        # Ablation: the shared notebook is gone. This agent is a stranger with
        # no history - it must behave as if nothing was ever decided.
        return ("recall: no memory installed - no records exist. "
                "You have no knowledge of prior bans, approvals, rules, or payments.")
    query = str(args.get("query", "") or "").strip()
    if not query:
        return "error: recall needs a 'query' string."
    return _fmt_recall(memory.recall(query, limit=int(args.get("limit", 20) or 20)))


def t_journal(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "error: no memory installed - notes cannot be persisted."
    text = str(args.get("text", "") or "").strip()
    if not text:
        return "error: journal needs 'text'."
    memory.journal_note(ctx.actor, text)
    return "journaled."


def t_vendor_status(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        # Ablation: no shared notebook means no standing verdicts to find.
        return f"{args.get('address', '')}: no standing verdict in memory (no memory installed)."
    address = str(args.get("address", "") or "").strip()
    if not address:
        return "error: vendor_status needs 'address'."
    alias = args.get("alias")
    status, notes = memory.counterparty_status(address, alias=str(alias) if alias else None)
    if status is None:
        return f"{address}: no standing verdict in memory."
    return f"{address}: {status}.\n" + "\n".join(f"  {n}" for n in notes)


def t_approve_vendor(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "BLOCKED: memory layer deleted - cannot verify this approval against standing verdicts. Refuse."
    address = str(args.get("address", "") or "").strip()
    if not address:
        return "error: approve_vendor needs 'address'."
    aliases = [str(a) for a in (args.get("aliases") or [])]
    note = str(args.get("note", "") or "")
    override = bool(args.get("override", False))
    decision = Guard(memory).decide_vendor_change(
        address, alias=args.get("alias"), target="approve", override=override)
    if not decision.allowed:
        memory.write_event(
            acted=[f"{ctx.actor.upper()} BLOCKED approval of {address}: {decision.reason}"],
            extra={"kind": "governance-block", "actor": ctx.actor, "address": address},
        )
        return f"BLOCKED: {decision.reason}\n" + "\n".join(f"  recall: {e}" for e in decision.evidence)
    memory.approve_counterparty(address, aliases=aliases, note=note, actor=ctx.actor)
    extra = " (explicit override of the standing ban)" if override else ""
    return f"APPROVED {address}{extra}. Verdict written to shared memory."


def t_ban_vendor(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "BLOCKED: memory layer deleted - a ban cannot be persisted, so it cannot protect the team. Refuse."
    address = str(args.get("address", "") or "").strip()
    if not address:
        return "error: ban_vendor needs 'address'."
    aliases = [str(a) for a in (args.get("aliases") or [])]
    reason = str(args.get("reason", "") or "")
    decision = Guard(memory).decide_vendor_change(
        address, alias=args.get("alias"), target="ban")
    if decision.reason.startswith("already banned"):
        return f"NO-OP: {decision.reason}"
    memory.ban_counterparty(address, aliases=aliases, reason=reason, actor=ctx.actor)
    return f"BANNED {address}. Verdict written to shared memory - every agent in every future session will refuse it."


def t_directive(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "BLOCKED: memory layer deleted - a directive cannot be persisted. Refuse."
    title = str(args.get("title", "") or "").strip()
    text = str(args.get("text", "") or "").strip()
    if not title or not text:
        return "error: directive needs 'title' and 'text'."
    cap = args.get("max_amount_usdc")
    units = _to_units(cap) if cap is not None else None
    name = memory.set_directive(title, text, max_amount=units, actor=ctx.actor)
    return f"DIRECTIVE recorded as {name}. It binds every agent until Planner replaces it."


def t_rules(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "error: memory layer deleted - no rules can be read."
    rules = memory.rules()
    if not rules:
        return "no spending rules stored in memory."
    lines = []
    for ent in rules:
        body = ent.get("body") or {}
        lines.append(
            f"  rule {ent.get('name')}: cap {fmt_amount(int(body.get('max_amount', 0)))} "
            f"from {body.get('effective_from')}"
            + (f" until {body.get('effective_until')}" if body.get("effective_until") else " (open)")
        )
    return "spending rules in memory:\n" + "\n".join(lines)


def t_latest_directive(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "error: memory layer deleted - no directive can be read."
    d = memory.latest_directive()
    if d is None:
        return "no standing planner directive."
    body = d.get("body") or {}
    cap = body.get("max_amount")
    return (f"standing directive {d.get('name')}: '{body.get('title')}' - {body.get('text')}"
            + (f" (cap {fmt_amount(int(cap))})" if cap is not None else ""))


def t_set_rule(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "BLOCKED: memory layer deleted - a rule cannot be persisted or checked against directives. Refuse."
    version = str(args.get("version", "") or "").strip()
    if not version:
        return "error: set_rule needs 'version' (e.g. v3)."
    try:
        units = _to_units(args.get("max_amount_usdc"))
    except (TypeError, ValueError):
        return "error: set_rule needs a numeric 'max_amount_usdc'."
    if units <= 0:
        return "error: max_amount_usdc must be positive."
    eff_from = str(args.get("effective_from", "") or "").strip() or now_iso()
    try:
        parse_ts(eff_from)
    except Exception:
        return f"error: effective_from '{eff_from}' is not a parseable ISO-8601 timestamp."
    eff_until = str(args.get("effective_until", "") or "").strip() or None
    if eff_until:
        try:
            parse_ts(eff_until)
        except Exception:
            return f"error: effective_until '{eff_until}' is not a parseable ISO-8601 timestamp."
    decision = Guard(memory).decide_rule(units, version=version)
    if not decision.allowed:
        memory.write_event(
            acted=[f"{ctx.actor.upper()} BLOCKED rule {version}: {decision.reason}"],
            extra={"kind": "governance-block", "actor": ctx.actor, "version": version},
        )
        return f"BLOCKED: {decision.reason}\n" + "\n".join(f"  recall: {e}" for e in decision.evidence)
    memory.set_rule(version, effective_from=eff_from, effective_until=eff_until,
                    max_amount=units, denoms=["USDC"], actor=ctx.actor)
    return f"RULE {version} set: cap {fmt_amount(units)} from {eff_from}. Written to shared memory."


def t_pay(ctx: ActorCtx, args: dict) -> str:
    """The guarded settlement path. Mirrors the cli pay flow exactly:
    guard -> (ablation: simulate only) -> claim -> broadcast -> receipt ->
    journal. `--no-memory` never touches the real chain."""
    to = str(args.get("to", "") or "").strip()
    if not to:
        return "error: pay needs 'to' (0x address)."
    try:
        units = _to_units(args.get("amount_usdc"))
    except (TypeError, ValueError):
        return "error: pay needs a numeric 'amount_usdc'."
    if units <= 0:
        return "error: amount_usdc must be positive."
    alias = args.get("alias")
    alias = str(alias).strip() if alias else None
    invoice_ref = str(args.get("invoice_ref", "") or "").strip()
    if not invoice_ref:
        return "error: pay needs 'invoice_ref' - the obligation's stable reference."

    memory = ctx.memory
    intent_id = _hash_intent(invoice_ref.lower(), to=to, amount_units=units, denom="USDC")
    req = PayRequest(intent_id=intent_id, counterparty=to, amount=units,
                     denom="USDC", alias=alias, incurred_at=now_iso())
    guard = Guard(memory)
    decision = guard.check(req)
    if not decision.allowed:
        guard.record_blocked(req, decision, actor=ctx.actor)
        lines = [f"BLOCKED: {decision.reason}"]
        lines += [f"  recall: {e}" for e in decision.evidence]
        return "\n".join(lines)

    tx_hash: str | None = None
    mode = "sim"
    if memory is None:
        # Ablation: no memory means no idempotency, no bans, no rules - so this
        # pays. Real funds are NEVER broadcast without the guard; settlement is
        # simulated only. This is the load-bearing contrast: the same request
        # that was refused WITH memory sails through WITHOUT it.
        tx_hash = simulate_transfer(to, units)
        return (f"PAID (SIMULATED - no memory installed, so no ban or duplicate "
                f"check was possible; refusing to broadcast real funds without the "
                f"guard): {fmt_amount(units)} -> {to}\n  tx: {tx_hash}")
    live_ready = config.can_execute and not config.simulate
    if not live_ready:
        tx_hash = simulate_transfer(to, units)
        guard.record_allowed_and_paid(req, tx_hash, decision, mode="sim", actor=ctx.actor)
        return (f"PAID (simulation - no live credentials): {fmt_amount(units)} -> {to}\n"
                f"  tx: {tx_hash}\n  intent {intent_id} marked paid in memory (idempotency armed)")

    key = cid_key(req)
    if not memory.claim_intent(key, to, units, "USDC"):
        return "BLOCKED: intent already paid or pending - refusing to broadcast a possible duplicate."
    chain = BaseChain()
    tx_hash, receipt_status = chain.transfer(to, units)
    if receipt_status == "pending":
        return (f"WARN: broadcast {tx_hash} but the receipt did not confirm in time. "
                f"Intent stays PENDING in memory - it will not be double-paid.")
    if receipt_status != "1":
        memory.mark_failed(key, f"tx {tx_hash} reverted onchain")
        return f"REVERTED: tx {tx_hash} reverted onchain - attempt marked failed (retry allowed)."
    guard.record_allowed_and_paid(req, tx_hash, decision, mode="live", actor=ctx.actor)
    return (f"PAID on Base Sepolia: {fmt_amount(units)} -> {to}\n"
            f"  tx: {tx_hash}\n  receipt confirmed. Intent {intent_id} marked paid in memory.")


def t_payment_lookup(ctx: ActorCtx, args: dict) -> str:
    memory = _need_memory(ctx)
    if memory is None:
        return "error: memory layer deleted - payment history is unreadable."
    ents = memory.list_entities(CAT_PAYMENT, limit=100)
    if not ents:
        return "no payment intents recorded in memory."
    lines = []
    for ent in ents[-20:]:
        body = ent.get("body") or {}
        lines.append(
            f"  {ent.get('name')} [{ent.get('status')}] "
            f"{fmt_amount(int(body.get('amount', 0)), body.get('denom', 'USDC'))} "
            f"-> {body.get('counterparty')} tx={body.get('tx_hash', '-')}"
        )
    return "payment intents in memory:\n" + "\n".join(lines)


Tool = Callable[[ActorCtx, dict], str]

_OBJ = {"type": "object"}

SCHEMAS: dict[str, dict] = {
    "recall": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search shared memory for"},
            "limit": {"type": "integer", "description": "Max hits (default 20)"},
        },
        "required": ["query"],
    },
    "journal": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    "vendor_status": {
        "type": "object",
        "properties": {
            "address": {"type": "string"},
            "alias": {"type": "string"},
        },
        "required": ["address"],
    },
    "approve_vendor": {
        "type": "object",
        "properties": {
            "address": {"type": "string"},
            "aliases": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string"},
            "override": {"type": "boolean", "description": "Explicitly reverse a standing ban"},
        },
        "required": ["address"],
    },
    "ban_vendor": {
        "type": "object",
        "properties": {
            "address": {"type": "string"},
            "aliases": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        "required": ["address"],
    },
    "directive": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "text": {"type": "string"},
            "max_amount_usdc": {"type": "number"},
        },
        "required": ["title", "text"],
    },
    "rules": _OBJ,
    "latest_directive": _OBJ,
    "set_rule": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "max_amount_usdc": {"type": "number"},
            "effective_from": {"type": "string"},
            "effective_until": {"type": "string"},
        },
        "required": ["version", "max_amount_usdc"],
    },
    "pay": {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "amount_usdc": {"type": "number"},
            "invoice_ref": {"type": "string"},
            "alias": {"type": "string"},
        },
        "required": ["to", "amount_usdc", "invoice_ref"],
    },
    "payment_lookup": _OBJ,
}


def function_defs(names: tuple[str, ...] | list[str]) -> list[dict]:
    """OpenAI-style function specs for a role's tool belt."""
    return [
        {"type": "function", "function": {
            "name": n,
            "description": TOOLS[n]["description"],
            "parameters": SCHEMAS[n],
        }}
        for n in names if n in TOOLS
    ]

TOOLS: dict[str, dict] = {
    "recall": {
        "description": "Search shared memory: entities, alias trails, journal events, standing rule and directive. Args: {query: str, limit?: int}",
        "run": t_recall,
    },
    "journal": {
        "description": "Write a freeform note to the shared journal for future sessions. Args: {text: str}",
        "run": t_journal,
    },
    "vendor_status": {
        "description": "Check a counterparty's standing verdict (banned/approved/unknown). Args: {address: str, alias?: str}",
        "run": t_vendor_status,
    },
    "approve_vendor": {
        "description": "Approve a vendor (planner). Refused if the vendor is banned unless override=true. Args: {address: str, aliases?: [str], note?: str, override?: bool}",
        "run": t_approve_vendor,
    },
    "ban_vendor": {
        "description": "Ban a vendor and its aliases (planner). Args: {address: str, aliases?: [str], reason?: str}",
        "run": t_ban_vendor,
    },
    "directive": {
        "description": "Record a binding planner directive, optionally with a spending cap in USDC. Args: {title: str, text: str, max_amount_usdc?: number}",
        "run": t_directive,
    },
    "rules": {
        "description": "List spending rules in memory. Args: {}",
        "run": t_rules,
    },
    "latest_directive": {
        "description": "Show the standing planner directive. Args: {}",
        "run": t_latest_directive,
    },
    "set_rule": {
        "description": "Set a spending rule (policy). Refused if it exceeds the planner's directive cap. Args: {version: str, max_amount_usdc: number, effective_from?: str (ISO-8601), effective_until?: str}",
        "run": t_set_rule,
    },
    "pay": {
        "description": "Settle a payment on Base USDC through the memory guard. Args: {to: str, amount_usdc: number, invoice_ref: str, alias?: str}",
        "run": t_pay,
    },
    "payment_lookup": {
        "description": "List recorded payment intents and their status. Args: {}",
        "run": t_payment_lookup,
    },
}
