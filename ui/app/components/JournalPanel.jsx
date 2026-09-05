"use client";

import { useEffect, useState } from "react";

function fmtTs(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function rich(text) {
  const parts = String(text || "").split(/(0x[0-9a-fA-F]{6,})/g);
  return parts.map((p, i) =>
    /^0x[0-9a-fA-F]{6,}$/.test(p) ? (
      <span className="mono" key={i} title={p}>
        {p.length > 14 ? p.slice(0, 6) + "…" + p.slice(-4) : p}
      </span>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

export default function JournalPanel({ tick }) {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const res = await fetch("/api/journal?limit=40");
        if (!res.ok) throw new Error("status " + res.status);
        const data = await res.json();
        if (alive) {
          setEvents(data.events || []);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    }
    load();
    const id = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [tick]);

  return (
    <section className="panel" aria-label="Shared memory journal">
      <div className="panel-head">
        <h2>Shared memory</h2>
        <span className="spacer" />
        <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
          {events ? events.length + " records" : "…"}
        </span>
      </div>
      <div className="journal-log">
        {error && <div className="toast">Journal unreachable: {error}</div>}
        {!error && events === null && <div className="empty">Reading the notebook…</div>}
        {!error && events && events.length === 0 && (
          <div className="empty">
            Nothing recorded yet. Talk to the team and every decision appears here — permanently.
          </div>
        )}
        {(events || []).map((ev, i) => (
          <div className="entry" key={i} style={{ animationDelay: Math.min(i, 8) * 30 + "ms" }}>
            <div className="entry-meta">
              {ev.kind && <span className={"chip " + ev.kind}>{ev.kind}</span>}
              {ev.actor && <span className="who">{ev.actor}</span>}
              <span className="when">{fmtTs(ev.ts)}</span>
            </div>
            <div className="entry-body">
              {rich(ev.text)}
              {ev.txUrl && (
                <>
                  {" "}
                  <a href={ev.txUrl} target="_blank" rel="noopener">
                    view tx ↗
                  </a>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
