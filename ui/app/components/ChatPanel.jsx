"use client";

import { useEffect, useRef, useState } from "react";

const STARTER =
  "The team is awake. Ask the planner to ban a vendor, the policy agent for a rule, or payments to settle an invoice — every decision lands in the shared notebook on the right.";

const SUGGESTIONS = [
  "Ban vendor 0x1111111111111111111111111111111111111111 alias evil-corp, they drained a partner",
  "Pay 2 USDC to 0x1111111111111111111111111111111111111111 alias evil-corp for invoice-7",
  "What spending rules are currently in force?",
];

/* Highlight addresses and verdict keywords without dangerouslySetInnerHTML. */
function rich(text) {
  const parts = String(text || "").split(/(0x[0-9a-fA-F]{6,}|BLOCKED|PAID|REFUSED)/g);
  return parts.map((p, i) => {
    if (/^0x[0-9a-fA-F]{6,}$/.test(p)) {
      const label = p.length > 14 ? p.slice(0, 6) + "…" + p.slice(-4) : p;
      return (
        <span className="mono" key={i} title={p}>
          {label}
        </span>
      );
    }
    if (p === "BLOCKED" || p === "REFUSED") return <span className="kw-block" key={i}>{p}</span>;
    if (p === "PAID") return <span className="kw-ok" key={i}>{p}</span>;
    return <span key={i}>{p}</span>;
  });
}

export default function ChatPanel({ onAnswered }) {
  const [messages, setMessages] = useState([{ agent: "team", text: STARTER }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  async function ask(text) {
    const clean = text.trim();
    if (!clean || busy) return;
    setInput("");
    setBusy(true);
    const id = "t" + Date.now();
    setMessages((m) => [
      ...m,
      { user: true, text: clean },
      { thinking: true, id, text: "Consulting shared memory…" },
    ]);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: clean }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error((data.error && data.error.message) || "request failed: " + res.status);
      }
      setMessages((m) =>
        m.filter((x) => x.id !== id).concat([{ agent: data.agent || "team", text: data.reply }])
      );
    } catch (e) {
      setMessages((m) =>
        m.filter((x) => x.id !== id).concat([
          { agent: "team", error: true, text: "The team could not answer: " + e.message },
        ])
      );
    } finally {
      setBusy(false);
      if (onAnswered) onAnswered();
    }
  }

  return (
    <section className="panel" aria-label="Team chat">
      <div className="panel-head">
        <h2>Talk to the team</h2>
        <span className="spacer" />
        <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
          planner · policy · payments
        </span>
      </div>

      <div className="chat-log" ref={logRef} role="log" aria-live="polite">
        {messages.map((m, i) =>
          m.user ? (
            <div className="msg user" key={i}>
              {rich(m.text)}
            </div>
          ) : (
            <div className="msg team" key={i}>
              <span className={"msg-role " + (m.agent || "team")}>{m.agent || "team"}</span>
              <div className="bubble">
                {m.thinking ? <span className="shimmer">{m.text}</span> : rich(m.text)}
              </div>
            </div>
          )
        )}
      </div>

      <div className="composer">
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              type="button"
              className="suggestion"
              key={s}
              onClick={() => ask(s)}
              disabled={busy}
            >
              {s.length > 52 ? s.slice(0, 52) + "…" : s}
            </button>
          ))}
        </div>
        <form
          className="prompt-box"
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={2000}
            autoComplete="off"
            placeholder="Ban a vendor, set a rule, pay an invoice…"
            aria-label="Message the team"
          />
          <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !input.trim()}>
            {busy ? "Working…" : "Send"}
          </button>
        </form>
      </div>
    </section>
  );
}
