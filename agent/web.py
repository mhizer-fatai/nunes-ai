from __future__ import annotations

"""Nunes AI web UI backend (stdlib only, no new dependencies).

Serves the single-page frontend in web/ plus a small JSON API over the
existing agent code:

  POST /api/chat      {message}            -> {agent, reply}
  GET  /api/journal?limit=N               -> {events: [{ts, actor, kind, text, tx}]}
  GET  /api/status                         -> {memory, chain, llm, rules, directives, counts}
  POST /api/ablation   {trials=1}          -> quantified deletion-test report (temp db)

Errors always look like {"error": {"code": ..., "message": ...}}.
Inputs are validated at the boundary; the agent core is never trusted with
raw shapes. Binds 127.0.0.1 by default (local demo surface).
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import config

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
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
        "counts": counters,
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
