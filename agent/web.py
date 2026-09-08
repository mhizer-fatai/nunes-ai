from __future__ import annotations

"""Nunes AI web UI backend (stdlib only, no new dependencies).

Serves the single-page frontend in web/ plus a small JSON API over the
existing agent code:

  POST /api/chat      {message}            -> {agent, reply}
  GET  /api/journal?limit=N               -> {events: [{ts, actor, kind, text, tx}]}
  GET  /api/status                         -> {memory, chain, llm, rules, directives, counts}
  POST /api/ablation   {trials=1}          -> quantified deletion-test report (temp db)
  POST /api/demo                          -> guided-demo transcript (temp db, forced sim)

Errors always look like {"error": {"code": ..., "message": ...}}.
Inputs are validated at the boundary; the agent core is never trusted with
raw shapes. Binds 127.0.0.1 by default (local demo surface).
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import config

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
BASESCAN_TX = "https://sepolia.basescan.org/tx/"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}


def _err(code: str, message: str) -> bytes:
    return json.dumps({"error": {"code": code, "message": message}}).encode()


def _json(obj) -> bytes:
    return json.dumps(obj).encode()


def _memory():
    from .memory import MemoryStore
    return MemoryStore()


def api_chat(body: dict) -> tuple[int, bytes]:
    from .chat import handle_turn
    message = body.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return 422, _err("VALIDATION_ERROR", "message must be a non-empty string")
    if len(message) > 2000:
        return 422, _err("VALIDATION_ERROR", "message is too long (max 2000 chars)")
    if not config.llm_enabled:
        return 503, _err("BRAIN_DISABLED", "no LLM API key configured (INCEPTION_API_KEY)")
    try:
        from .runtime import route
        assignment = route(message.strip())
        if assignment["role"] is None:
            return 200, _json({"agent": None, "reply": assignment["ask"], "routed": False})
        reply = handle_turn(_memory(), message.strip())
        return 200, _json({"agent": assignment["role"], "reply": reply, "routed": True})
    except Exception as exc:
        return 500, _err("AGENT_ERROR", f"the team failed to answer: {exc}")


def api_journal(query: dict) -> tuple[int, bytes]:
    try:
        limit = int(query.get("limit", ["50"])[0])
    except (ValueError, TypeError, IndexError):
        return 422, _err("VALIDATION_ERROR", "limit must be an integer")
    limit = max(1, min(limit, 200))
    try:
        memory = _memory()
        events = memory.read_events(limit=limit)
    except Exception as exc:
        return 500, _err("MEMORY_ERROR", f"journal unreadable: {exc}")
    out = []
    for ev in reversed(events):
        acted = ev.get("acted")
        text = "; ".join(acted) if isinstance(acted, list) else str(acted)
        extra = ev.get("extra") or {}
        tx = extra.get("tx_hash")
        out.append({
            "ts": ev.get("ts"),
            "actor": extra.get("actor"),
            "kind": extra.get("kind"),
            "text": text,
            "tx": tx,
            "txUrl": (BASESCAN_TX + tx) if tx and str(tx).startswith("0x") else None,
        })
    return 200, _json({"events": out})


def api_status() -> tuple[int, bytes]:
    try:
        memory = _memory()
        rules = memory.rules()
        directive = memory.latest_directive()
        counters: dict[str, int] = {}
        for ent in memory.list_entities(limit=500):
            key = f"{ent.get('category')}/{ent.get('status')}"
            counters[key] = counters.get(key, 0) + 1
        db = str(memory.db_path)
    except Exception as exc:
        return 500, _err("MEMORY_ERROR", f"status unreadable: {exc}")
    return 200, _json({
        "memory": db,
        "chain": "live Base Sepolia" if config.can_execute and not config.simulate else "simulation",
        "llm": bool(config.llm_enabled),
        "rules": [
            {"name": r.get("name"),
             "cap": (r.get("body") or {}).get("max_amount"),
             "from": (r.get("body") or {}).get("effective_from")}
            for r in rules
        ],
        "directive": ((directive.get("body") or {}).get("title") if directive else None),
        "quorum": {"required": 2, "timelock_s": int(getattr(config, "vendor_timelock_seconds", 60))},
        "counts": counters,
    })


def api_stats() -> tuple[int, bytes]:
    """Live aggregates from shared memory for stat cards. All real counts,
    no invented metrics: journal size, blocks, payments, USDC moved."""
    try:
        memory = _memory()
        events = memory.read_events(limit=2000)
        blocked = paid = 0
        usdc_units = 0
        txs: list[dict] = []
        for ent in memory.list_entities("payment", limit=500):
            body = ent.get("body") or {}
            if ent.get("status") == "paid":
                paid += 1
                try:
                    usdc_units += int(body.get("amount", 0) or 0)
                except (TypeError, ValueError):
                    pass
                tx = body.get("tx_hash")
                if tx and str(tx).startswith("0x"):
                    txs.append({"tx": tx, "to": body.get("counterparty"),
                                "amount": body.get("amount")})
        for ev in events:
            kind = (ev.get("extra") or {}).get("kind", "")
            if kind in ("block", "governance-block", "recipient-block"):
                blocked += 1
    except Exception as exc:
        return 500, _err("MEMORY_ERROR", f"stats unreadable: {exc}")
    txs.sort(key=lambda t: str(t["tx"]))
    return 200, _json({
        "calls": len(events),
        "blocked": blocked,
        "paid": paid,
        "usdc": usdc_units / 1_000_000,
        "txs": txs[-6:],
    })


def api_ablation(body: dict) -> tuple[int, bytes]:
    try:
        trials = int(body.get("trials", 1))
    except (ValueError, TypeError):
        return 422, _err("VALIDATION_ERROR", "trials must be an integer")
    if trials < 1 or trials > 3:
        return 422, _err("VALIDATION_ERROR", "trials must be between 1 and 3")
    try:
        from .ablation import run_experiment
        report = run_experiment(None, trials=trials)  # always a temp db: never pollutes live memory
    except Exception as exc:
        return 500, _err("EXPERIMENT_ERROR", f"ablation failed: {exc}")
    return 200, _json({
        "headline": report["headline"],
        "withBlocked": report["with_memory"]["harmful_blocked"],
        "withTotal": report["with_memory"]["harmful_total"],
        "withoutAllowed": report["without_memory"]["harmful_allowed"],
        "withoutTotal": report["without_memory"]["harmful_allowed"] + report["without_memory"]["harmful_blocked"],
        "byCategory": report["with_memory"]["by_category_blocked"],
    })


_BANNED = "0x7b8Bca2C6c59fB7E5e96d7f1E1e5C5a0a6b1B222"
_VENDOR = "0xeB3DD0faF85FC7C6aB13B41cC9371b1FE0797842"
_DEMO_DB: Path | None = None


def _demo_db() -> Path:
    """A throwaway db for the guided demo - never the live ~/.sibyl-memory."""
    db = Path(tempfile.gettempdir()) / "nunes-ui-demo.db"
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(str(db) + suffix)
        except FileNotFoundError:
            pass
    return db


def _cli(argv: list[str]) -> str:
    """Run the real agent CLI against the demo db, forcing simulation so no
    real funds can ever be broadcast from a demo."""
    env = dict(os.environ)
    env["NUNES_AI_SIMULATE"] = "1"
    cmd = [sys.executable, "-m", "agent.cli", "--db", str(_DEMO_DB)] + argv
    try:
        res = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True,
                             text=True, timeout=30)
    except Exception as exc:
        return f"error: demo step failed to run: {exc}"
    text = (res.stdout or "").strip("\n") or (res.stderr or "").strip("\n")
    return text or f"(exit {res.returncode})"


def _guided_demo() -> dict:
    """Execute the guided story against a fresh throwaway db and return the
    transcript for the UI console: the guard refusing what memory forbids,
    then the ablation paying the same request when memory is deleted."""
    db = _demo_db()
    global _DEMO_DB
    _DEMO_DB = db

    def step(banner: str, cmd: str, argv: list[str]) -> dict:
        return {"banner": banner, "cmd": cmd, "out": _cli(argv)}

    steps = [
        step(
            "SESSION 1 — policy writes the spending rule the guard will enforce",
            f"python -m agent.cli set-rule --version v1 --max-amount 100 --effective-from 2026-08-01T00:00:00.000Z",
            ["set-rule", "--version", "v1",
             "--effective-from", "2026-08-01T00:00:00.000Z", "--max-amount", "100"],
        ),
        step(
            "SESSION 1 — payments settles invoice inv-900 (5 USDC)",
            f"python -m agent.cli pay --intent inv-900 --to {_VENDOR} --amount 5",
            ["pay", "--intent", "inv-900", "--to", _VENDOR, "--amount", "5"],
        ),
        step(
            "SESSION 2 — a genuinely fresh process, the same invoice returns",
            f"python -m agent.cli pay --intent inv-900 --to {_VENDOR} --amount 5",
            ["pay", "--intent", "inv-900", "--to", _VENDOR, "--amount", "5"],
        ),
        step(
            "SESSION 3 — the planner bans the drainer (alias evil-corp)",
            f"python -m agent.cli ban --address {_BANNED} --aliases evil-corp --reason \"drained a partner wallet\"",
            ["ban", "--address", _BANNED, "--aliases", "evil-corp",
             "--reason", "drained a partner wallet"],
        ),
        step(
            "SESSION 4 — a fresh process is asked to pay the banned vendor",
            f"python -m agent.cli pay --intent inv-77 --to {_BANNED} --amount 2",
            ["pay", "--intent", "inv-77", "--to", _BANNED, "--amount", "2"],
        ),
        step(
            "DELETE THE MEMORY",
            "python -m agent.cli wipe",
            ["wipe"],
        ),
        step(
            "NO MEMORY — the exact same request, unguarded",
            f"python -m agent.cli --no-memory pay --intent inv-77 --to {_BANNED} --amount 2",
            ["--no-memory", "pay", "--intent", "inv-77", "--to", _BANNED, "--amount", "2"],
        ),
    ]
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(str(db) + suffix)
        except FileNotFoundError:
            pass
    return {"steps": steps, "sim": True,
            "note": "executed against a throwaway memory db with settlement forced to "
                    "simulation - nothing shown touches live memory or broadcasts funds"}


def api_demo() -> tuple[int, bytes]:
    try:
        return 200, _json(_guided_demo())
    except Exception as exc:
        return 500, _err("DEMO_ERROR", f"guided demo failed: {exc}")


class Handler(BaseHTTPRequestHandler):
    server_version = "nunes-web"

    def log_message(self, *args):
        pass

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, body: bytes) -> None:
        self._send(status, "application/json; charset=utf-8", body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if parsed.path == "/api/journal":
                status, body = api_journal(parse_qs(parsed.query))
                self._send_json(status, body)
            elif parsed.path == "/api/status":
                status, body = api_status()
                self._send_json(status, body)
            elif parsed.path == "/api/stats":
                status, body = api_stats()
                self._send_json(status, body)
            else:
                self._send_json(404, _err("NOT_FOUND", f"no such endpoint: {parsed.path}"))
            return
        rel = parsed.path.lstrip("/") or "index.html"
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        self._send(200, CONTENT_TYPES.get(target.suffix, "application/octet-stream"),
                   target.read_bytes())

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(422, _err("VALIDATION_ERROR", "request body must be JSON"))
            return
        if not isinstance(body, dict):
            self._send_json(422, _err("VALIDATION_ERROR", "request body must be a JSON object"))
            return
        if parsed.path == "/api/chat":
            status, out = api_chat(body)
        elif parsed.path == "/api/ablation":
            status, out = api_ablation(body)
        elif parsed.path == "/api/demo":
            status, out = api_demo()
        else:
            status, out = 404, _err("NOT_FOUND", f"no such endpoint: {parsed.path}")
        self._send_json(status, out)


def run_server(port: int) -> ThreadingHTTPServer:
    if not WEB_DIR.is_dir():
        raise RuntimeError(f"web directory missing: {WEB_DIR}")
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nunes AI web UI (local demo).")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    server = run_server(args.port)
    print(f"nunes web UI on http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
