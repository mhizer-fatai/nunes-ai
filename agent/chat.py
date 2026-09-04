from __future__ import annotations

import argparse
import sys

from . import roles
from .config import config
from .memory import MemoryStore
from .runtime import route, run_agent
from .toolkit import ActorCtx

BANNER = """Nunes AI - one shared memory, three agents.
  planner  : vendors, bans, approvals, standing directives
  policy   : spending rules and caps
  payments : guarded settlement on Base (USDC)
Type 'quit' to leave. Every decision is written to shared memory.
"""


def open_memory(db: str | None, no_memory: bool) -> MemoryStore | None:
    if no_memory:
        return None
    return MemoryStore(db) if db else MemoryStore()


def handle_turn(memory: MemoryStore | None, text: str) -> str:
    assignment = route(text)
    if assignment["role"] is None:
        return assignment["ask"]
    role = assignment["role"]
    ctx = ActorCtx(actor=role, memory=memory)
    result = run_agent(role, ctx, text)
    return result["final"]


def chat_loop(memory: MemoryStore | None) -> int:
    print(BANNER)
    print(f"  memory : {memory.db_path if memory else 'DELETED (--no-memory)'}")
    print(f"  chain  : {'live Base Sepolia' if config.can_execute and not config.simulate else 'simulation'}")
    if not config.llm_enabled:
        print("  brain  : DISABLED - set INCEPTION_API_KEY in .env to wake the team")
        return 1
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nsession closed. Memory persists - the team remembers.")
            return 0
        if not text:
            continue
        if text.lower() in ("quit", "exit"):
            print("session closed. Memory persists - the team remembers.")
            return 0
        assignment = route(text)
        if assignment["role"] is None:
            print(f"\nteam> {assignment['ask']}")
            continue
        role = assignment["role"]
        print(f"\n[dispatcher -> {role}]")
        ctx = ActorCtx(actor=role, memory=memory)
        result = run_agent(role, ctx, text)
        print(f"\n{role}> {result['final']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nunes-ai-chat",
        description="Nunes AI - talk to the three-agent team sharing one Sibyl memory.",
    )
    parser.add_argument("--db", metavar="PATH", default=None,
                        help="override the Sibyl memory database path")
    parser.add_argument("--no-memory", action="store_true",
                        help="ablate the memory layer (agents lose recall; settlement is simulated only)")
    args = parser.parse_args(argv)
    # Model output is UTF-8; Windows consoles default to cp1252 and would
    # crash printing it.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return chat_loop(open_memory(args.db, args.no_memory))


if __name__ == "__main__":
    raise SystemExit(main())
