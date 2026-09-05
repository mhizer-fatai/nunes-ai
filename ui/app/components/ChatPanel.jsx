"use client";

import { useRef, useState } from "react";

const STARTER =
  "The team is awake. Ask the planner to ban a vendor, the policy agent for a rule, or payments to settle an invoice — everything lands in the shared notebook.";

export default function ChatPanel({ onAnswered }) {
  const [messages, setMessages] = useState([{ agent: "payments", text: STARTER }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  function scrollDown() {
    requestAnimationFrame(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    });
  }

  async function send(ev) {
    ev.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    const thinkingId = Date.now();
    setMessages((m) => [
      ...m,
      { user: true, text },
      { thinking: true, id: thinkingId, text: "Consulting shared memory…" },
    ]);
    scrollDown();
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data.error && data.error.message) || `request failed: ${res.status}`);
      setMessages((m) =>
        m
          .filter((msg) => msg.id !== thinkingId)
          .concat([{ agent: data.agent, text: data.reply }])
      );
    } catch (e) {
      setMessages((m) =>
        m
          .filter((msg) => msg.id !== thinkingId)
          .concat([{ agent: null, text: "The team could not answer: " + e.message }])
      );
    } finally {
      setBusy(false);
      scrollDown();
      if (onAnswered) onAnswered();
    }
  }

  return (
    <section className="card" aria-label="Team chat">
      <h2>Talk to the team</h2>
      <div id="chat-log" ref={logRef} role="log" aria-live="polite">
        {messages.map((m, i) =>
          m.user ? (
            <div className="msg user" key={i}>{m.text}</div>
          ) : (
            <div className="msg team" key={i}>
              {m.agent && <div className={"agent-badge " + m.agent}>{m.agent}</div>}
              <div className="bubble">
                {m.thinking ? <span className="shimmer">{m.text}</span> : m.text}
              </div>
            </div>
          )
        )}
      </div>
      <form id="chat-form" onSubmit={send}>
        <div className="ai-prompt-box">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={2000}
            autoComplete="off"
            placeholder="Ban a vendor, set a rule, pay an invoice…"
          />
          <button type="submit" disabled={busy || !input.trim()}>Send</button>
        </div>
      </form>
    </section>
  );
}
