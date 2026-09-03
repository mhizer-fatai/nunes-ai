from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sibyl_memory_client import MemoryClient
from sibyl_memory_client.exceptions import NotFoundError

from .config import config

CAT_PAYMENT = "payment"
CAT_COUNTERPARTY = "counterparty"
CAT_RULE = "rule"

STATUS_PAID = "paid"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
STATUS_BANNED = "banned"
STATUS_APPROVED = "approved"

BAN_KIND = "ban"
APPROVE_KIND = "approve"


class NoMemory(Exception):
    """Raised when the memory layer has been removed (ablation)."""


def now_iso() -> str:
    """UTC ISO-8601 timestamp with milliseconds, ending in 'Z'."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_ts(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp. Naive timestamps are assumed UTC."""
    norm = ts.strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    dt = datetime.fromisoformat(norm)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fmt_amount(units: int, denom: str = "USDC") -> str:
    dec = 10 ** 6
    val = units / dec
    text = f"{val:.6f}".rstrip("0").rstrip(".")
    return f"{text} {denom}"


class MemoryStore:
    """Thin, purpose-built wrapper over the Sibyl Memory five-tier store.

    Tiers used:
      HOT        -> session policy snapshot (which rule version is live right now)
      WARM       -> entities: paid intents, counterparties (approved / banned),
                    spending rules
      COLD       -> append-only decision journal: every allow/block, with tx hashes
      FTS5       -> cross-tier recall ("have we paid this? was this vendor flagged?")
    """

    def __init__(self, db_path: Path | str | None = None, *, live: bool = True) -> None:
        if not live:
            raise NoMemory("memory layer deleted")
        path = Path(str(db_path or config.memory_db)).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client = MemoryClient.local(path)
        self._db_path = path

    @property
    def db_path(self) -> Path:
        return self._db_path

    # -- raw client passthroughs ----------------------------------------------

    def write_event(self, *, evaluated=None, acted=None, forward=None, extra=None) -> str:
        return self.client.write_event(
            evaluated=evaluated, acted=acted, forward=forward, extra=extra
        )

    def read_events(self, *, limit: int = 50, since: str | None = None, until: str | None = None) -> list[dict]:
        return self.client.read_events(limit=limit, since=since, until=until)

    # -- HOT session state ----------------------------------------------------

    def set_session_policy(self, rule_version: str) -> None:
        self.client.set_state("active_policy", {"rule_version": rule_version})

    def session_policy(self) -> dict | None:
        return self.client.get_state("active_policy")

    # -- WARM entity helpers --------------------------------------------------

    def get_entity(self, category: str, name: str) -> dict | None:
        try:
            return self.client.get_entity(category, name)
        except NotFoundError:
            return None

    def list_entities(self, category: str | None = None, *, status: str | None = None, limit: int = 500) -> list[dict]:
        return self.client.list_entities(category, status=status, limit=limit)

    def _fuzzy(self, query: str, *, category: str | None = None, limit: int = 20) -> list[dict]:
        """FTS5 recall across WARM entities."""
        try:
            results = self.client.search_entities(query, limit=limit, category=category)
        except Exception:
            return []
        if not results:
            return []
        out: list[dict] = []
        for item in results:
            if isinstance(item, dict):
                out.append(item)
        return out

    # -- payments (idempotency) ----------------------------------------------

    def is_paid(self, key: str) -> dict | None:
        """Return the paid-payment entity for `key`, or None."""
        ent = self.get_entity(CAT_PAYMENT, key)
        if ent is not None and ent.get("status") == STATUS_PAID:
            return ent
        return None

    def payment_status(self, key: str) -> str | None:
        """Current lifecycle status of a payment intent: paid / pending /
        failed / None."""
        ent = self.get_entity(CAT_PAYMENT, key)
        if ent is None:
            return None
        return ent.get("status")

    def claim_intent(self, key: str, counterparty: str, amount: int, denom: str) -> bool:
        """Reserve the intent BEFORE anything is broadcast.

        Returns True if we now own the claim. Returns False if the intent is
        already paid or pending (another worker won, or a previous attempt is
        still in flight). This is the compare-and-set that makes the
        check -> broadcast -> record sequence safe against concurrent
        double-pays and crash-after-broadcast retries."""
        status = self.payment_status(key)
        if status in (STATUS_PAID, STATUS_PENDING):
            return False
        self.client.set_entity(
            CAT_PAYMENT,
            key,
            {
                "counterparty": counterparty,
                "amount": amount,
                "denom": denom,
                "claimed_at": now_iso(),
            },
            status=STATUS_PENDING,
        )
        return True

    def mark_failed(self, key: str, reason: str) -> None:
        """Record a failed attempt (e.g. reverted receipt) so the intent can
        be retried rather than blocking forever."""
        self.client.set_entity(
            CAT_PAYMENT,
            key,
            {"failed_at": now_iso(), "reason": reason},
            status=STATUS_FAILED,
        )
        self.write_event(
            acted=[f"FAILED {key}: {reason}"],
            extra={"kind": "failure", "key": key, "reason": reason},
        )

    def record_paid(self, key: str, counterparty: str, amount: int, denom: str, tx_hash: str,
                    mode: str = "live") -> None:
        self.client.set_entity(
            CAT_PAYMENT,
            key,
            {
                "counterparty": counterparty,
                "amount": amount,
                "denom": denom,
                "tx_hash": tx_hash,
                "mode": mode,
                "paid_at": now_iso(),
            },
            status=STATUS_PAID,
        )
        self.write_event(
            acted=[f"PAID {fmt_amount(amount, denom)} to {counterparty} for {key}"],
            extra={"kind": "payment", "key": key, "tx_hash": tx_hash,
                   "mode": mode, "counterparty": counterparty},
        )

    # -- counterparties (approved / banned) ----------------------------------

    def ban_counterparty(self, address: str, aliases: list[str] | tuple[str, ...] = (), reason: str = "") -> None:
        """Ban an address and every alias it is known under, so a banned vendor
        re-emerging under a NEW address but the same alias is still refused."""
        norm = address.lower()
        aliases = [a.lower() for a in aliases]
        self.client.set_entity(
            CAT_COUNTERPARTY,
            norm,
            {"address": norm, "aliases": aliases, "reason": reason, "kind": BAN_KIND},
            status=STATUS_BANNED,
        )
        for alias in aliases:
            self.client.set_entity(
                CAT_COUNTERPARTY,
                alias,
                {"address": norm, "aliases": aliases, "reason": reason, "kind": BAN_KIND},
                status=STATUS_BANNED,
            )
        self.write_event(
            acted=[f"BANNED {address} ({', '.join(aliases) or 'no alias'}): {reason}"],
            extra={"kind": BAN_KIND, "address": norm, "aliases": aliases, "reason": reason},
        )

    def approve_counterparty(self, address: str, aliases: list[str] | tuple[str, ...] = (), note: str = "") -> None:
        norm = address.lower()
        aliases = [a.lower() for a in aliases]
        self.client.set_entity(
            CAT_COUNTERPARTY,
            norm,
            {"address": norm, "aliases": aliases, "note": note, "kind": APPROVE_KIND},
            status=STATUS_APPROVED,
        )
        for alias in aliases:
            self.client.set_entity(
                CAT_COUNTERPARTY,
                alias,
                {"address": norm, "aliases": aliases, "note": note, "kind": APPROVE_KIND},
                status=STATUS_APPROVED,
            )
        self.write_event(
            acted=[f"APPROVED {address} ({', '.join(aliases) or 'no alias'}): {note}"],
            extra={"kind": APPROVE_KIND, "address": norm, "aliases": aliases, "note": note},
        )

    def counterparty_status(self, address: str, alias: str | None = None) -> tuple[str | None, list[str]]:
        """Recall whether a counterparty is banned/approved.

        Returns (status, evidence). Exact WARM lookup on the address first;
        if the address is unknown, recall the alias trail (exact alias entity
        plus FTS5 over the counterparty tier) so a banned vendor under a new
        address is still caught.
        """
        evidence: list[str] = []
        norm = address.lower()

        exact = self.get_entity(CAT_COUNTERPARTY, norm)
        if exact is not None:
            status = exact.get("status")
            body = exact.get("body") or {}
            evidence.append(f"counterparty {norm} -> {status} (kind={body.get('kind')})")
            return status, evidence

        if alias:
            alias_ent = self.get_entity(CAT_COUNTERPARTY, alias.lower())
            if alias_ent is not None:
                status = alias_ent.get("status")
                body = alias_ent.get("body") or {}
                canonical = body.get("address") or alias_ent.get("name")
                evidence.append(
                    f"alias '{alias}' -> {status} (banned address {canonical})"
                )
                return status, evidence
            for hit in self._fuzzy(alias, category=CAT_COUNTERPARTY, limit=20):
                status = hit.get("status")
                if status in (STATUS_BANNED, STATUS_APPROVED):
                    body = hit.get("body") or {}
                    name = hit.get("name")
                    if alias.lower() in (name or "") or alias.lower() in (body.get("aliases") or []):
                        evidence.append(
                            f"FTS5 alias recall: '{alias}' matched {name} -> {status}"
                        )
                        return status, evidence

        return None, evidence

    # -- spending rules (temporal recall) ------------------------------------

    def set_rule(
        self,
        version: str,
        *,
        effective_from: str,
        effective_until: str | None = None,
        max_amount: int,
        denoms: list[str] | tuple[str, ...] = ("USDC",),
    ) -> None:
        """Store a spending rule. Rules are never deleted: obligations are
        judged under the rule that was in force when they were incurred."""
        body = {
            "version": version,
            "effective_from": effective_from,
            "effective_until": effective_until,
            "max_amount": max_amount,
            "denoms": list(denoms),
        }
        self.client.set_entity(CAT_RULE, version, body, status="active")
        self.set_session_policy(version)
        self.write_event(
            acted=[
                f"RULE {version}: cap {fmt_amount(max_amount)} from {effective_from}"
                + (f" until {effective_until}" if effective_until else "")
            ],
            extra={"kind": "rule", **body},
        )

    def rules(self) -> list[dict]:
        return self.client.list_entities(CAT_RULE, limit=500)

    def rule_at(self, ts: str) -> dict | None:
        """Which rule was in force at `ts`? The rule with the latest
        effective_from that satisfies effective_from <= ts < effective_until
        (an absent effective_until means open-ended)."""
        when = parse_ts(ts)
        best: dict | None = None
        for ent in self.list_entities(CAT_RULE, limit=500):
            body = ent.get("body") or {}
            eff_from = body.get("effective_from")
            eff_until = body.get("effective_until")
            if not eff_from:
                continue
            if parse_ts(eff_from) > when:
                continue
            if eff_until and parse_ts(eff_until) <= when:
                continue
            if best is None or parse_ts(best["body"]["effective_from"]) < parse_ts(eff_from):
                best = {"name": ent.get("name"), "status": ent.get("status"), "body": body}
        return best
