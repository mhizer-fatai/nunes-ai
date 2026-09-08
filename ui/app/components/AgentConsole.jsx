"use client";

import { useEffect, useRef, useState } from "react";

const LIVE = 900;

function fmtHms(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return d.toLocaleTimeString([], { hour12: false });
}

function kindCls(ev) {
  const k = ev.kind;
  if (k === "router") return "router";
  if (k === "agent") return "agent";
  if (k === "tool") return "tool";
  if (k === "memory") {
    const t = String(ev.text);
    if (/\[BLOCK\]|BLOCKED|Refused|FAILED|banned is|double-spend refused/i.test(t)) return "block";
    if (/PAID|\[ALLOW\]|BANNED /i.test(t) || /^PLANNER/i.test(t) && /BANNED/.test(t)) return "pay";
    if (/RULE|cap /i.test(t)) return "rule";
    if (/NOTE/.test(t)) return "note";
    return "dim";
  }
  return "dim";
}

const LABEL = {
  router: "route",
  agent: "agent",
  tool: "tool",
  memory: "write",
};

/* The live process of a request, terminal-style: dispatcher routing -> the
   agent working -> each tool call -> the writes landing in Sybil memory. */
export default function AgentConsole() {
  const [lines, setLines] = useState([]);
  const cursor = useRef(0);
  const bodyRef = useRef(null);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  useEffect(() => {
    let alive = true;
    let lastKey = "";
    async function poll() {
      try {
        const res = await fetch("/api/activity?since=" + cursor.current);
        if (!res.ok) return;
        const data = await res.json();
        if (!alive) return;
        cursor.current = data.next || cursor.current;
        const fresh = [];
        for (const ev of data.events || []) {
          const key = (ev.kind || "?") + "|" + (ev.text || "");
          if (ev.kind === "router" && key === lastKey) continue;
          lastKey = key;
          fresh.push(ev);
        }
        if (fresh.length) {
          setLines((prev) => {
            const merged = prev.concat(fresh);
            return merged.length > 300 ? merged.slice(-300) : merged;
          });
        }
      } catch {
        /* backend briefly busy during a long request - next tick */
      }
    }
    poll();
    const id = setInterval(poll, LIVE);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <section className="panel tail-panel" aria-label="Agent request process">
      <div className="panel-head">
        <h2>Request process</h2>
        <span className="spacer" />
        <span className="tail-live">
          <span className="dot" />
          live
        </span>
      </div>
      <div className="tail-body" ref={bodyRef} role="log" aria-live="polite">
        {lines.length === 0 && (
          <div className="tl dim">awaiting a request — send the team a message and watch every step land here.</div>
        )}
        {lines.map((ev) => (
          <div className="tl" key={ev.n}>
            <span className="tl-t">{fmtHms(ev.ts)}</span>
            <span className={"tl-k " + kindCls(ev)}>{LABEL[ev.kind] || ev.kind}</span>
            <span className="tl-txt">{ev.text}</span>
          </div>
        ))}
      </div>
      <div className="tail-hint">
        dispatcher → agent → tool → memory write, as it happens.
      </div>
    </section>
  );
}
