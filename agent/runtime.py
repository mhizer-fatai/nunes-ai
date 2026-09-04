from __future__ import annotations

import json
import re

from . import roles
from .llm import LLMError, complete, complete_with_tools
from .toolkit import ActorCtx, TOOLS, function_defs

MAX_STEPS = 6


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise LLMError("agent returned no usable JSON action")
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"agent returned malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("agent action was not a JSON object")
    return data


def _tool_block(role: str) -> str:
    names = roles.ROLE_TOOLS[role]
    lines = [f"- {n}: {TOOLS[n]['description']}" for n in names]
    return "\n".join(lines)


def system_for(role: str) -> str:
    return (
        roles.ROLE_PROMPTS[role]
        + "\n\n"
        + roles._CONTRACT.format(tools=_tool_block(role), steps=MAX_STEPS)
    )


def run_agent(role: str, ctx: ActorCtx, task: str, *,
              complete_fn=complete_with_tools, max_steps: int = MAX_STEPS) -> dict:
    """Run one role agent on a task. Returns {"final": str, "steps": [...]}.

    The model drives via native function calls (text JSON is accepted as a
    fallback). Tool calls execute against shared memory under the guard; the
    returned observations are the only thing the next step can build on.
    `complete_fn` is injectable so the loop is testable without an LLM.
    """
    allowed = set(roles.ROLE_TOOLS[role])
    specs = function_defs(roles.ROLE_TOOLS[role])
    messages: list[dict] = [
        {"role": "system", "content": system_for(role)},
        {"role": "user", "content": task},
    ]
    steps: list[dict] = []

    def _run_tool(name: str, args: dict) -> str:
        if not isinstance(args, dict):
            args = {}
        if name not in allowed or name not in TOOLS:
            return (f"Unknown or forbidden tool '{name}'. Your tools are: "
                    f"{', '.join(roles.ROLE_TOOLS[role])}.")
        try:
            return str(TOOLS[name]["run"](ctx, args))[:3000]
        except Exception as exc:  # tools must never crash the loop
            return f"Tool '{name}' failed: {exc}"

    for _ in range(max_steps):
        try:
            if complete_fn is complete_with_tools:
                turn = complete_fn(messages, specs)
            else:  # test doubles return raw text in the old JSON-action shape
                turn = {"content": complete_fn(messages), "calls": []}
        except LLMError as exc:
            return {"final": f"[{role} error] {exc}", "steps": steps}

        calls = list(turn.get("calls") or [])
        content = turn.get("content") or ""

        # Text fallback: the model emitted a {"tool":...} / {"final":...} object.
        if not calls and content.strip().startswith("{"):
            try:
                action = _extract_json(content)
            except LLMError:
                action = {}
            if "tool" in action and "final" not in action:
                calls = [{"id": "text", "name": str(action.get("tool")),
                          "args": action.get("args") if isinstance(action.get("args"), dict) else {}}]
            elif "final" in action:
                return {"final": str(action.get("final") or "").strip() or "(empty reply)",
                        "steps": steps}

        if calls:
            assistant_msg: dict = {"role": "assistant", "content": content or None}
            native = [c for c in calls if c.get("id") != "text"]
            if native:
                assistant_msg["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                    for c in native
                ]
            messages.append(assistant_msg)
            for call in calls:
                obs = _run_tool(call["name"], call["args"])
                if call.get("id") != "text":
                    messages.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": obs})
                else:
                    messages.append({"role": "user",
                                     "content": f"Tool {call['name']} returned:\n{obs}"})
                steps.append({"raw": call, "observation": obs})
            continue

        text = content.strip()
        if text:
            return {"final": text, "steps": steps}
        messages.append({"role": "user", "content": "Please continue: call a tool or answer in plain text."})

    return {"final": "[agent stopped] step budget exhausted without a final answer.", "steps": steps}


def route(task: str, *, complete_fn=complete) -> dict:
    """Dispatch one user request to a role. Returns {"role": str|None, "ask": str}.

    An LLM dispatcher decides; a deterministic keyword fallback keeps the team
    usable when the model reply is unusable.
    """
    try:
        raw = complete_fn([
            {"role": "system", "content": roles._DISPATCH_PROMPT},
            {"role": "user", "content": task},
        ])
        data = _extract_json(raw)
        role = data.get("role")
        if role in roles.ROLE_ORDER:
            return {"role": role, "ask": ""}
        if role is None and data.get("ask"):
            return {"role": None, "ask": str(data["ask"])}
    except LLMError:
        pass
    low = task.lower()
    pay_words = ("pay", "settle", "transfer", "send ", "send usdc", "invoice", ".invoice")
    ban_words = ("ban", "approve", "blacklist", "freeze", "vendor", "scam", "directive", "strategy")
    rule_words = ("rule", "cap", "limit", "budget", "spend", "allowance", "policy")
    scores = {
        roles.PAYMENTS: sum(w in low for w in pay_words),
        roles.PLANNER: sum(w in low for w in ban_words),
        roles.POLICY: sum(w in low for w in rule_words),
    }
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return {"role": None, "ask": "Which teammate should take this - planner (vendors), policy (spending rules), or payments?"}
    return {"role": best, "ask": ""}
