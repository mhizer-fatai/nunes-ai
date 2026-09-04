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

        # 1. Idempotency: already paid (or already in flight) on this chain?
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
        if self.memory.payment_status(key) == "pending":
            evidence.append(f"payment {key} -> status pending (claim already held)")
            return GuardDecision(
                allowed=False,
                reason=(
                    f"intent {req.intent_id} is already in flight (pending claim) - "
                    "refusing to broadcast a possible duplicate"
                ),
                evidence=tuple(evidence),
            )
        if self.memory.payment_status(key) == "failed":
            evidence.append(f"payment {key} -> status failed (previous attempt reverted; retry allowed)")

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

    def record_allowed_and_paid(self, req: PayRequest, tx_hash: str, decision: GuardDecision,
                                 mode: str = "live", actor: str | None = None) -> None:
        """Journal a settlement that actually happened."""
        if self.memory is None:
            return
        key = cid_key(req)
        self.memory.record_paid(
            key, req.counterparty, req.amount, req.denom, tx_hash, mode=mode, actor=actor
        )
        tag = f"{actor.upper()} " if actor else ""
        self.memory.write_event(
            evaluated=req.as_dict(),
            acted=[
                f"{tag}ALLOW {fmt_amount(req.amount, req.denom)} -> {req.counterparty} "
                f"({decision.reason}) tx {tx_hash}"
            ],
            forward=[f"do not pay {key} again"],
            extra={
                "kind": "allow",
                "key": key,
                "tx_hash": tx_hash,
                "rule_version": decision.rule_version,
                **({"actor": actor} if actor else {}),
            },
        )

    def record_blocked(self, req: PayRequest, decision: GuardDecision,
                       actor: str | None = None) -> None:
        """Journal a refusal."""
        if self.memory is None:
            return
        tag = f"{actor.upper()} " if actor else ""
        self.memory.write_event(
            evaluated=req.as_dict(),
            acted=[
                f"{tag}BLOCK {fmt_amount(req.amount, req.denom)} -> {req.counterparty} "
                f"({decision.reason})"
            ],
            forward=["do not pay this intent"],
            extra={
                "kind": "block",
                "key": cid_key(req),
                "rule_version": decision.rule_version,
                "evidence": list(decision.evidence),
                **({"actor": actor} if actor else {}),
            },
        )

    # -- cross-agent governance (contradiction-blocking between roles) ---------

    def decide_vendor_change(self, address: str, *, alias: str | None = None,
                             target: str, override: bool = False) -> GuardDecision:
        """A Planner agent wants to write a new vendor verdict (`approve` or
        `ban`). The guard refuses writes that contradict a standing verdict:

        - approving a banned vendor without an explicit override is refused
        - banning an already-banned vendor is allowed as an idempotent no-op,
          but recorded as already-in-force rather than a fresh decision
        - with memory deleted the write goes through unguarded (the ablation)
        """
        if self.memory is None:
            return GuardDecision(
                allowed=True,
                reason=("memory layer deleted - vendor verdicts cannot be checked; "
                        "this write may contradict a standing decision"),
            )
        status, notes = self.memory.counterparty_status(address, alias=alias)
        evidence = tuple(notes)
        if target == "approve" and status == "banned" and not override:
            return GuardDecision(
                allowed=False,
                reason=(f"refused: {address} is BANNED in memory and this approval "
                        f"contradicts it - re-issue with override=true if the team "
                        f"has genuinely reversed the ban"),
                evidence=evidence,
            )
        if target == "ban" and status == "banned":
            return GuardDecision(
                allowed=True,
                reason=f"already banned in memory - verdict stands, no new decision needed",
                evidence=evidence,
            )
        if target == "approve" and status == "approved":
            return GuardDecision(
                allowed=True,
                reason="already approved in memory - verdict stands",
                evidence=evidence,
            )
        return GuardDecision(
            allowed=True,
            reason=f"no standing verdict contradicts this {target}",
            evidence=evidence,
        )

    def decide_rule(self, max_amount: int, *, version: str) -> GuardDecision:
        """A Policy agent wants to set a spending rule. The guard refuses rules
        that exceed the cap of the latest active Planner directive: within one
        team, Policy may not silently override what Planner decided.

        With memory deleted the rule goes through unguarded (the ablation).
        """
        if self.memory is None:
            return GuardDecision(
                allowed=True,
                reason=("memory layer deleted - directives cannot be checked; "
                        "this rule may contradict a standing planner cap"),
            )
        directive = self.memory.latest_directive()
        evidence: list[str] = []
        if directive is not None:
            body = directive.get("body") or {}
            cap = body.get("max_amount")
            dname = directive.get("name")
            evidence.append(f"latest directive {dname}: '{body.get('title')}' cap={cap}")
            if cap is not None and max_amount > int(cap):
                return GuardDecision(
                    allowed=False,
                    reason=(f"refused: rule {version} cap {fmt_amount(max_amount)} exceeds "
                            f"the standing planner directive cap {fmt_amount(int(cap))} "
                            f"({dname}) - the planner must raise the directive first"),
                    evidence=tuple(evidence),
                )
        return GuardDecision(
            allowed=True,
            reason=f"rule {version} fits the standing directive" if directive else "no standing directive to contradict",
            evidence=tuple(evidence),
        )
