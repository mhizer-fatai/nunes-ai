"use client";

import { useEffect, useRef, useState } from "react";

const KIND_COLOR = {
  payment: "pay",
  allow: "pay",
  paid: "pay",
  x402: "pay",
  rule: "rule",
  directive: "rule",
  block: "block",
  failure: "block",
  ban: "block",
  "governance-block": "block",
  "recipient-block": "block",
  vote: "rule",
  note: "note",
};

function fmtHms(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return d.toLocaleTimeString([], { hour12: false });
}

/* Live tail of the COLD journal: every write to Sybil memory appends here,
   newest at the bottom, colored by kind — exactly what a terminal session
   into the shared notebook would show. */
export default function MemoryTail({ tick }) {
  const [lines, setLines] = useState([]);
  const [error, setError] = useState(null);
  const seen = useRef(new Set());
  const bodyRef = useRef(null);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const res = await fetch("/api/journal?limit=30");
        if (!res.ok) throw new Error("journal " + res.status);
        const data = await res.json();
        if (!alive) return;
        setError(null);
        const chrono = (data.events || []).slice().reverse();
        const fresh = [];
        for (const ev of chrono) {
          const key = ev.ts + "|" + ev.text;
          if (!seen.current.has(key)) {
            seen.current.add(key);
            fresh.push(ev);
          }
        }
        if (fresh.length) {
          setLines((prev) => {
            const merged = prev.concat(fresh);
            return merged.length > 500 ? merged.slice(-500) : merged;
          });
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    }
    load();
    const id = setInterval(load, 1500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [tick]);

  return (
    <section className="panel tail-panel" aria-label="Sybil memory write stream">
      <div className="panel-head">
        <h2>Sybil memory</h2>
        <span className="spacer" />
        <span className="tail-live">
          <span className="dot" />
          tail -f
        </span>
      </div>
      <div className="tail-body" ref={bodyRef} role="log" aria-live="polite">
        {error && <div className="tl dim">journal unreachable: {error}</div>}
        {!error && lines.length === 0 && (
          <div className="tl dim">listening for writes…</div>
        )}
        {lines.map((ev, i) => (
          <div className="tl" key={i}>
            <span className="tl-t">{fmtHms(ev.ts)}</span>
            <span className={"tl-k " + (KIND_COLOR[ev.kind] || "dim")}>
              {ev.kind || "?"}
            </span>
            <span className="tl-txt">{ev.text}</span>
            {ev.txUrl && (
              <a className="tl-tx" href={ev.txUrl} target="_blank" rel="noopener">
                tx↗
              </a>
            )}
          </div>
        ))}
      </div>
      <div className="tail-hint">
        every decision the team writes to shared memory streams here — allow, block, rule, note.
      </div>
    </section>
  );
}
