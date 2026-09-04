from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import config


class LLMError(Exception):
    """Raised when the model layer cannot produce a usable reply."""


class LLMUnavailable(LLMError):
    """No API key configured - agent loops are disabled."""


def complete(messages: list[dict[str, str]], *, temperature: float = 0.5,
             max_tokens: int = 2048) -> str:
    """One OpenAI-compatible chat completion over a message list.

    Thin transport over the same key/endpoint the brain layer uses
    (INCEPTION_API_KEY / LLM_BASE_URL / LLM_MODEL). All agent reasoning is
    disposable: it proposes, the memory guard disposes.

    Provider notes (Inception Mercury): temperature must sit in [0.5, 1], and
    reasoning tokens bill against max_tokens - so this layer clamps the
    temperature and budgets generously.
    """
    if not config.llm_api_key:
        raise LLMUnavailable("no LLM API key configured (INCEPTION_API_KEY)")
    body = json.dumps({
        "model": config.llm_model,
        "messages": messages,
        "temperature": min(1.0, max(0.5, temperature)),
        "max_tokens": max_tokens,
    }).encode()
    url = config.llm_base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.llm_api_key}",
            "User-Agent": "nunes-ai/0.1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        raise LLMError(f"LLM HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"LLM request failed: {exc.reason}") from exc
    try:
        content = result["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError("LLM response missing choices[0].message.content") from exc
    # Reasoning models occasionally return an empty content with a stop
    # reason on the first attempt - retry once before giving up.
    if not isinstance(content, str) or not content.strip():
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode())
            content = result["choices"][0]["message"].get("content")
        except Exception:
            content = None
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM returned an empty reply")
    return content


def complete_with_tools(messages: list[dict], tools: list[dict], *,
                        temperature: float = 0.5, max_tokens: int = 2048) -> dict:
    """Chat completion with native function calling.

    Returns {"content": str|None, "calls": [{"id": str, "name": str,
    "args": dict}]}. Mercury-class models prefer this path: with tools
    offered they emit structured calls instead of text JSON. Empty text
    content alongside calls is normal, not an error.
    """
    if not config.llm_api_key:
        raise LLMUnavailable("no LLM API key configured (INCEPTION_API_KEY)")
    body = json.dumps({
        "model": config.llm_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": min(1.0, max(0.5, temperature)),
        "max_tokens": max_tokens,
    }).encode()
    url = config.llm_base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.llm_api_key}",
            "User-Agent": "nunes-ai/0.1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        raise LLMError(f"LLM HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"LLM request failed: {exc.reason}") from exc
    try:
        message = result["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response missing choices[0].message") from exc
    calls: list[dict] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else {}
        except json.JSONDecodeError:
            args = {}
        if name:
            calls.append({"id": tc.get("id") or name, "name": name,
                          "args": args if isinstance(args, dict) else {}})
    content = message.get("content")
    if not calls and (not isinstance(content, str) or not content.strip()):
        raise LLMError("LLM returned neither a tool call nor text")
    return {"content": content if isinstance(content, str) else None, "calls": calls}
