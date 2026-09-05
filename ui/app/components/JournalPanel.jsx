"use client";

import { useEffect, useState } from "react";

function shortAddr(text) {
  return String(text || "").replace(/0x[0-9a-fA-F]{40}/g, (m) => m.slice(0, 6) + "…" + m.slice(-4));
}

function fmtTs(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d) ? ts : d.toLocaleString();
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
    <section className="card" aria-label="Shared memory">
      <h2>Shared memory — the notebook</h2>
      <div id="journal-log">
        {error && <div className="toast">Journal unreachable: {error}</div>}
        {!error && events === null && (
          <div className="empty">Loading the notebook…</div>
        )}
        {!error && events && events.length === 0 && (
          <div className="empty">
            No decisions recorded yet — talk to the team and watch this notebook fill.
          </div>
        )}
        {(events || []).map((ev, i) => (
          <div className={"entry " + (ev.kind || "")} key={i}>
            <div className="meta">
              {ev.kind && <span className={"chip " + ev.kind}>{ev.kind}</span>}
              {ev.actor && <span>{ev.actor}</span>}
              {ev.ts && <span>{fmtTs(ev.ts)}</span>}
            </div>
            <div>
              {shortAddr(ev.text)}
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
