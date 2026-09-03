from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PayRequest:
    """A payment obligation the agent wants to settle onchain.

    `intent_id` is the obligation key. It MUST be minted by the caller before
    the model runs - never by the LLM - or a re-prompt hands back a fresh key
    and the guard is bypassed (the durable-execution idempotency lesson).
    """

    intent_id: str
    counterparty: str
    amount: int  # base units (USDC micro-units: 1 USDC = 10**6)
    denom: str = "USDC"
    alias: str | None = None
    incurred_at: str | None = None  # ISO-8601; defaults to now when None

    def as_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "counterparty": self.counterparty,
            "amount": self.amount,
            "denom": self.denom,
            "alias": self.alias,
            "incurred_at": self.incurred_at,
        }


@dataclass(frozen=True)
class GuardDecision:
    """What the memory guard decided, and the memory it recalled to decide."""

    allowed: bool
    reason: str
    rule_version: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
