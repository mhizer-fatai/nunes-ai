from __future__ import annotations

"""In-process activity bus: a tiny, thread-safe ring of what the team is
doing as it does it. The web UI tails this to show, live, the process of a
request - dispatcher routing, which agent is working, tool calls, and the
writes landing in Sybil memory. Never persisted; lost on restart.
"""

import threading
from collections import deque
from datetime import datetime, timezone

_MAX = 600

_BUF: deque = deque(maxlen=_MAX)
_LOCK = threading.Lock()
_N = 0


def emit(kind: str, text: str, actor: str | None = None) -> None:
    """Append one activity line. Never raises - observability must not be
    able to break the agent."""
    global _N
    try:
        with _LOCK:
            _N += 1
            _BUF.append({
                "n": _N,
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "kind": kind,
                "text": str(text)[:500],
                "actor": actor,
            })
    except Exception:
        pass


def read_since(cursor: int, limit: int = 400) -> tuple[list, int]:
    """Return events newer than `cursor` (oldest first) and the next cursor."""
    with _LOCK:
        items = [e for e in _BUF if e["n"] > cursor]
        items = items[:limit]
        next_cursor = items[-1]["n"] if items else (
            max((e["n"] for e in _BUF), default=cursor)
        )
        return items, next_cursor
