from __future__ import annotations

from .memory import MemoryStore, fmt_amount, now_iso
from .policy import GuardDecision, PayRequest

# Idempotency dimension: (chain, intent_id, denom). Chain is fixed to Base for
# the hackathon build but kept as a string so the key is future-proof.
CID = "Chain/Intent/Denom"


def cid_key(req: PayRequest) -> str:
    return f"{CID}:{req.intent_id}:{req.denom}"


class Guard:
    """The memory guard.

    Every payment intent is checked against persistent, append-only Sibyl
    memory before anything is signed or sent:

      1. Idempotency   - have we already paid this intent on this chain?
      2. Counterparty  - is this address / vendor flagged or banned?
      3. Temporal rule - which spending rule was in force when the obligation
                         was incurred, and does this request fit it?

    After the action the guard writes an immutable decision record
    (intent -> recalled context -> policy applied -> outcome) to the COLD
    journal. Delete the memory and all three checks disappear: the agent
    double-pays, re-approves rejects, and enforces no policy.
    """

    def __init__(self, memory: MemoryStore | None) -> None:
        self.memory = memory

    # -- the gate ------------------------------------------------------------

    def check(self, req: PayRequest) -> GuardDecision:
        """Recall, then decide. No writes here - decisions are recorded by
        the caller only after the outcome (allow + executed, or block)."""
        if self.memory is None:
            return GuardDecision(
                allowed=True,
                reason=(
                    "memory layer deleted - no idempotency, no policy, no "
                    "counterparty recall. The agent will double-pay, re-approve "
                    "rejected contracts, and fall for prompt-injected drains."
                ),
            )

        key = cid_key(req)
        ts = req.incurred_at or now_iso()
        evidence: list[str] = []

        # 1. Idempotency: already paid this intent on this chain?
        paid = self.memory.is_paid(key)
        if paid is not None:
            body = paid.get("body") or {}
            tx_hash = body.get("tx_hash", "?")
            evidence.append(f"payment {key} -> status paid, tx_hash {tx_hash}")
            return GuardDecision(
                allowed=False,
                reason=(
                    f"double-spend refused: {req.intent_id} was already paid "
                    f"({req.denom}) on this chain - tx {tx_hash}"
                ),
                evidence=tuple(evidence),
            )

        # 2. Counterparty: banned / approved, exact plus FTS5 alias recall.
        status, notes = self.memory.counterparty_status(req.counterparty, alias=req.alias)
        evidence.extend(notes)
        if status == "banned":
            return GuardDecision(
                allowed=False,
                reason=f"counterparty {req.counterparty} is banned in memory",
                evidence=tuple(evidence),
            )

        # 3. Temporal spending rule in force when the obligation was incurred.
        rule = self.memory.rule_at(ts)
        if rule is None:
            evidence.append(f"no rule entity in force at {ts}")
            return GuardDecision(
                allowed=False,
                reason=f"no spending rule was in force at {ts}",
                evidence=tuple(evidence),
            )

        version = str(rule.get("name"))
        body = rule.get("body") or {}
        max_amount = int(body.get("max_amount", 0))
        denoms = list(body.get("denoms", []))
        eff_from = body.get("effective_from", "?")
        eff_until = body.get("effective_until")

        window = f"{eff_from}..{eff_until or 'open'}"
        evidence.append(
            f"rule {version} in force at {ts}: max {fmt_amount(max_amount)} "
            f"window {window}"
        )

        if req.denom not in denoms:
            return GuardDecision(
                allowed=False,
                reason=f"{req.denom} not covered by rule {version} (denoms: {', '.join(denoms)})",
                rule_version=version,
                evidence=tuple(evidence),
            )
        if req.amount > max_amount:
            return GuardDecision(
                allowed=False,
                reason=(
                    f"amount {fmt_amount(req.amount, req.denom)} exceeds limit "
                    f"{fmt_amount(max_amount, req.denom)} under rule {version} "
                    f"in force at {ts}"
                ),
                rule_version=version,
                evidence=tuple(evidence),
            )

        evidence.append("counterparty not banned")
        return GuardDecision(
            allowed=True,
            reason=f"allowed under rule {version} (in force at {ts})",
            rule_version=version,
            evidence=tuple(evidence),
        )

    # -- recording (writes happen only after an outcome) ----------------------

    def record_allowed_and_paid(self, req: PayRequest, tx_hash: str, decision: GuardDecision) -> None:
        """Journal a settlement that actually happened."""
        if self.memory is None:
            return
        key = cid_key(req)
        self.memory.record_paid(
            key, req.counterparty, req.amount, req.denom, tx_hash
        )
        self.memory.write_event(
            evaluated=req.as_dict(),
            acted=[
                f"ALLOW {fmt_amount(req.amount, req.denom)} -> {req.counterparty} "
                f"({decision.reason}) tx {tx_hash}"
            ],
            forward=[f"do not pay {key} again"],
            extra={
                "kind": "allow",
                "key": key,
                "tx_hash": tx_hash,
                "rule_version": decision.rule_version,
            },
        )

    def record_blocked(self, req: PayRequest, decision: GuardDecision) -> None:
        """Journal a refusal."""
        if self.memory is None:
            return
        self.memory.write_event(
            evaluated=req.as_dict(),
            acted=[
                f"BLOCK {fmt_amount(req.amount, req.denom)} -> {req.counterparty} "
                f"({decision.reason})"
            ],
            forward=["do not pay this intent"],
            extra={
                "kind": "block",
                "key": cid_key(req),
                "rule_version": decision.rule_version,
                "evidence": list(decision.evidence),
            },
        )
