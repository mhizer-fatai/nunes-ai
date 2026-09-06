from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sibyl_memory_client import MemoryClient
from sibyl_memory_client.exceptions import NotFoundError

from .config import config

CAT_PAYMENT = "payment"
CAT_COUNTERPARTY = "counterparty"
CAT_RULE = "rule"
CAT_DIRECTIVE = "directive"
CAT_VOTE = "vote"

STATUS_PAID = "paid"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
STATUS_BANNED = "banned"
STATUS_APPROVED = "approved"
STATUS_VOTED = "voted"

BAN_KIND = "ban"
APPROVE_KIND = "approve"
CONTACT_KIND = "contact"

# Loop B: a brand-new payee becomes payable only when this many distinct
# roles have recorded an explicit confirmation vote in memory, AND the
# quorum timelock (config.vendor_timelock_seconds) has passed. A single
# compromised agent can never make a new address payable on its own.
QUORUM_REQUIRED = 2


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


class BadAddress(ValueError):
    """Raised when a purported 0x address is not a well-formed 40-hex address."""


def normalize_address(value: str) -> str:
    """Validate and normalize an EVM address to lowercase.

    Fails fast on anything that is not exactly 0x + 40 hex chars, so a
    corrupted or truncated address can never become a standing record or a
    broadcast target.
    """
    text = (value or "").strip()
    if len(text) != 42 or not text.startswith("0x"):
        raise BadAddress(f"not a 0x address: {value!r}")
    try:
        return "0x" + bytes.fromhex(text[2:]).hex()
    except ValueError:
        raise BadAddress(f"not a 0x address: {value!r}") from None


def _actor_tag(actor: str | None) -> tuple[str, dict]:
    """Prefix label + event extra for journaled actions, so any teammate can
    see *which agent* made every decision when they recall memory later."""
    if not actor:
        return "", {}
    return f"{actor.upper()} ", {"actor": actor}


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
        be retried rather than blocking forever. Preserves the original claim
        body (counterparty, amount) so the failed attempt stays attributable."""
        ent = self.get_entity(CAT_PAYMENT, key)
        body = dict((ent.get("body") or {}) if ent else {})
        body.update({"failed_at": now_iso(), "reason": reason})
        self.client.set_entity(
            CAT_PAYMENT,
            key,
            body,
            status=STATUS_FAILED,
        )
        self.write_event(
            acted=[f"FAILED {key}: {reason}"],
            extra={"kind": "failure", "key": key, "reason": reason},
        )

    def record_paid(self, key: str, counterparty: str, amount: int, denom: str, tx_hash: str,
                    mode: str = "live", actor: str | None = None) -> None:
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
        tag, extra_actor = _actor_tag(actor)
        self.write_event(
            acted=[f"{tag}PAID {fmt_amount(amount, denom)} to {counterparty} for {key}"],
            extra={"kind": "payment", "key": key, "tx_hash": tx_hash,
                   "mode": mode, "counterparty": counterparty, **extra_actor},
        )

    # -- counterparties (approved / banned) ----------------------------------

    def ban_counterparty(self, address: str, aliases: list[str] | tuple[str, ...] = (), reason: str = "",
                         actor: str | None = None) -> None:
        """Ban an address and every alias it is known under, so a banned vendor
        re-emerging under a NEW address but the same alias is still refused."""
        norm = normalize_address(address)
        aliases = [a.lower() for a in aliases]
        tag, extra_actor = _actor_tag(actor)
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
            acted=[f"{tag}BANNED {address} ({', '.join(aliases) or 'no alias'}): {reason}"],
            extra={"kind": BAN_KIND, "address": norm, "aliases": aliases, "reason": reason, **extra_actor},
        )

    def approve_counterparty(self, address: str, aliases: list[str] | tuple[str, ...] = (), note: str = "",
                             actor: str | None = None) -> None:
        norm = normalize_address(address)
        aliases = [a.lower() for a in aliases]
        tag, extra_actor = _actor_tag(actor)
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
            acted=[f"{tag}APPROVED {address} ({', '.join(aliases) or 'no alias'}): {note}"],
            extra={"kind": APPROVE_KIND, "address": norm, "aliases": aliases, "note": note, **extra_actor},
        )

    # -- Loop B: memory-mediated consent (zero-human for new payees) ------------

    def propose_counterparty(self, address: str, aliases: list[str] | tuple[str, ...] = (),
                             note: str = "", actor: str | None = None) -> str:
        """Register a NEW payee as `pending`. It is not payable until it earns
        QUORUM_REQUIRED confirmation votes from distinct roles AND the timelock
        passes. One compromised agent cannot make a fresh address payable."""
        norm = normalize_address(address)
        aliases = [a.lower() for a in aliases]
        body = {"address": norm, "aliases": aliases, "note": note,
                "kind": CONTACT_KIND, "proposed_by": actor, "proposed_at": now_iso(),
                "quorum_at": None, "payable_at": None}
        self.client.set_entity(CAT_COUNTERPARTY, norm, body, status=STATUS_PENDING)
        for alias in aliases:
            self.client.set_entity(CAT_COUNTERPARTY, alias, dict(body), status=STATUS_PENDING)
        tag, extra_actor = _actor_tag(actor)
        self.write_event(
            acted=[f"{tag}PROPOSED {address} ({', '.join(aliases) or 'no alias'}): {note} - "
                   f"pending, needs {QUORUM_REQUIRED} role confirmations"],
            extra={"kind": CONTACT_KIND, "address": norm, "aliases": aliases,
                   "note": note, "status": STATUS_PENDING, **extra_actor},
        )
        if actor:
            self.vote_counterparty(norm, actor, note=note)
        return norm

    def vote_counterparty(self, address: str, actor: str, note: str = "") -> dict:
        """Record one role's confirmation vote for a pending payee. Distinct
        roles only: the same role voting twice counts once. Returns
        {votes, quorum_met, payable, payable_at|None}."""
        norm = normalize_address(address)
        ent = self.get_entity(CAT_COUNTERPARTY, norm)
        if ent is None or (ent.get("status") not in (STATUS_PENDING, STATUS_VOTED, STATUS_APPROVED)):
            raise ValueError(f"{norm} is not a pending payee")
        body = ent.get("body") or {}

        # one vote per role - idempotent
        existing = self.get_entity(CAT_VOTE, f"vote:{norm}:{actor}")
        if existing is None:
            self.client.set_entity(
                CAT_VOTE, f"vote:{norm}:{actor}",
                {"address": norm, "role": actor, "voted_at": now_iso(), "note": note},
                status=STATUS_VOTED,
            )

        roles = sorted(self.counterparty_votes(norm))
        quorum_met = len(roles) >= QUORUM_REQUIRED
        if quorum_met and not body.get("quorum_at"):
            body = dict(body)
            body["quorum_at"] = now_iso()
            self.client.set_entity(CAT_COUNTERPARTY, norm, body, status=STATUS_VOTED)
        self.write_event(
            acted=[f"{actor.upper()} CONFIRMED {norm} ({len(roles)}/{QUORUM_REQUIRED} votes)"],
            extra={"kind": "vote", "address": norm, "role": actor,
                   "votes": len(roles), "quorum_met": quorum_met},
        )

        payable_at = None
        if quorum_met and body.get("quorum_at"):
            q = parse_ts(body["quorum_at"])
            payable_at = q + timedelta(seconds=int(getattr(config, "vendor_timelock_seconds", 0)))
            if parse_ts(now_iso()) >= payable_at:
                body = dict(body)
                body["payable_at"] = payable_at.isoformat().replace("+00:00", "Z")
                self.client.set_entity(CAT_COUNTERPARTY, norm, body, status=STATUS_APPROVED)
        return {"votes": len(roles), "quorum_met": quorum_met,
                "payable": payable_at is not None and parse_ts(now_iso()) >= payable_at,
                "payable_at": payable_at.isoformat().replace("+00:00", "Z") if payable_at else None}

    def counterparty_votes(self, address: str) -> list[str]:
        norm = normalize_address(address)
        out: list[str] = []
        for ent in self.list_entities(CAT_VOTE, limit=500):
            name = ent.get("name") or ""
            if name.startswith(f"vote:{norm}:"):
                body = ent.get("body") or {}
                role = body.get("role") or name.rsplit(":", 1)[-1]
                if role not in out:
                    out.append(role)
        return out

    def contact_state(self, address: str) -> dict | None:
        """Loop B status for a pending/proposed payee: votes, quorum, timelock
        remaining. Returns None if the address isn't a pending contact."""
        norm = normalize_address(address)
        try:
            ent = self.get_entity(CAT_COUNTERPARTY, norm)
        except Exception:
            return None
        if ent is None or (ent.get("body") or {}).get("kind") != CONTACT_KIND:
            return None
        body = ent.get("body") or {}
        votes = self.counterparty_votes(norm)
        quorum_met = len(votes) >= QUORUM_REQUIRED
        payable = False
        remaining = None
        if quorum_met and body.get("quorum_at"):
            payable_at = parse_ts(body["quorum_at"]) + timedelta(
                seconds=int(getattr(config, "vendor_timelock_seconds", 0)))
            payable = parse_ts(now_iso()) >= payable_at
            if not payable:
                remaining = int((payable_at - parse_ts(now_iso())).total_seconds())
        return {"status": STATUS_APPROVED if payable else STATUS_PENDING,
                "votes": votes, "quorum_met": quorum_met, "payable": payable,
                "remaining_s": remaining, "proposed_by": body.get("proposed_by"),
                "note": body.get("note")}

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

    def resolve_counterparty(self, address: str | None, alias: str | None = None) -> str | None:
        """Resolve a payment recipient to the canonical address stored in the
        vendor directory (shared memory).

        Only PAYABLE addresses resolve: an approved vendor, or a pending
        contact whose quorum is met and whose timelock has passed. A pending
        contact that has not earned the quorum resolves to None - the money
        path must refuse it. When nothing is registered, nothing is trusted.
        """
        candidates: list[str] = []
        if address:
            try:
                candidates.append(normalize_address(address))
            except BadAddress:
                pass
        if alias:
            candidates.append(alias.strip().lower())
        for cand in candidates:
            ent = self.get_entity(CAT_COUNTERPARTY, cand)
            if ent is None:
                continue
            body = ent.get("body") or {}
            canonical = body.get("address")
            # Pending contacts (Loop B) must earn quorum + timelock before
            # they are a valid broadcast destination. `cand` may be an alias,
            # so the consent check runs against the canonical address.
            if body.get("kind") == CONTACT_KIND:
                try:
                    check = normalize_address(str(canonical)) if canonical else None
                except BadAddress:
                    check = None
                if not check or not self.contact_state(check) or not self.contact_state(check).get("payable"):
                    continue
            if canonical:
                try:
                    return normalize_address(str(canonical))
                except BadAddress:
                    continue
        return None

    # -- spending rules (temporal recall) ------------------------------------

    def set_rule(
        self,
        version: str,
        *,
        effective_from: str,
        effective_until: str | None = None,
        max_amount: int,
        denoms: list[str] | tuple[str, ...] = ("USDC",),
        actor: str | None = None,
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
        tag, extra_actor = _actor_tag(actor)
        self.client.set_entity(CAT_RULE, version, body, status="active")
        self.set_session_policy(version)
        self.write_event(
            acted=[
                f"{tag}RULE {version}: cap {fmt_amount(max_amount)} from {effective_from}"
                + (f" until {effective_until}" if effective_until else "")
            ],
            extra={"kind": "rule", **body, **extra_actor},
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

    # -- planner directives (cross-agent binding decisions) -------------------

    def set_directive(self, title: str, text: str, *, max_amount: int | None = None,
                      actor: str | None = None) -> str:
        """Record a binding planner directive. A directive with a `max_amount`
        cap binds every future spending rule: Policy may not set a rule with a
        higher cap while the directive is active.

        The entity name is time-ordered, so agents (and the guard) can always
        find the latest directive without remembering IDs."""
        created = now_iso()
        millis = int(parse_ts(created).timestamp() * 1000)
        name = f"directive-{millis}"
        body = {"title": title, "text": text, "max_amount": max_amount, "created": created}
        tag, extra_actor = _actor_tag(actor)
        self.client.set_entity(CAT_DIRECTIVE, name, body, status="active")
        self.write_event(
            acted=[f"{tag}DIRECTIVE '{title}': {text}"
                   + (f" (cap {fmt_amount(max_amount)})" if max_amount is not None else "")],
            extra={"kind": "directive", "directive": name, **body, **extra_actor},
        )
        return name

    def directives(self) -> list[dict]:
        ents = self.client.list_entities(CAT_DIRECTIVE, limit=500)
        out = [
            {"name": e.get("name"), "status": e.get("status"), "body": e.get("body") or {}}
            for e in ents
        ]
        out.sort(key=lambda e: str(e["body"].get("created", "")))
        return out

    def latest_directive(self) -> dict | None:
        active = [e for e in self.directives() if e.get("status") == "active"]
        return active[-1] if active else None

    # -- cross-session recall (the agents' shared memory read path) -----------

    def recall(self, query: str, *, limit: int = 20) -> dict:
        """Everything a teammate needs to know before acting on `query`:

        - exact + fuzzy counterparty status (bans, approvals, alias trail)
        - the latest spending rule + the latest planner directive
        - the most relevant journal events mentioning the query
        """
        matches = self._fuzzy(query, limit=limit)
        hits: list[str] = []
        for item in matches[:limit]:
            cat = item.get("category")
            name = item.get("name")
            status = item.get("status")
            body = item.get("body") or {}
            hits.append(f"{cat}/{name} [{status}] {str(body)[:200]}")
        events: list[str] = []
        try:
            for ev in self.read_events(limit=limit * 2):
                blob = str(ev.get("acted")) + str(ev.get("forward")) + str(ev.get("extra"))
                if query.lower() in blob.lower():
                    acted = ev.get("acted")
                    text = "; ".join(acted) if isinstance(acted, list) else str(acted)
                    events.append(f"{ev.get('ts')}: {text}")
        except Exception:
            pass
        return {
            "matches": hits,
            "events": events[:limit],
            "latest_rule": self.rules()[-1] if self.rules() else None,
            "latest_directive": self.latest_directive(),
        }

    def journal_note(self, actor: str, text: str, **extra) -> None:
        """Freeform journal entry by an agent - a teammate's reasoning that the
        next session must be able to read back."""
        self.write_event(acted=[f"{actor.upper()} NOTE: {text}"],
                         extra={"kind": "note", "actor": actor, **extra})
