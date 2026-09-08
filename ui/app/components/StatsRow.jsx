"use client";

import { useEffect, useState } from "react";

/* Live counters from shared memory. Real aggregates, zero invented metrics. */
export default function StatsRow() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive && d) setStats(d);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const cards = stats
    ? [
        { n: String(stats.calls), l: "calls on record" },
        { n: String(stats.blocked), l: "refused by memory" },
        { n: String(stats.paid), l: "settlements kept" },
        { n: stats.usdc.toFixed(2), l: "USDC moved" },
      ]
    : [
        { n: "…", l: "calls on record" },
        { n: "…", l: "refused by memory" },
        { n: "…", l: "settlements kept" },
        { n: "…", l: "USDC moved" },
      ];

  return (
    <div className="stat-cards">
      {cards.map((c) => (
        <div className="stat-card" key={c.l}>
          <div className="n">{c.n}</div>
          <div className="l">{c.l}</div>
        </div>
      ))}
    </div>
  );
}
