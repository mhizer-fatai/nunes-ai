"use client";

import { useState } from "react";

export default function AblationPanel() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/ablation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trials: 1 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data.error && data.error.message) || `request failed: ${res.status}`);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="card" id="ablation-card" aria-label="Deletion test">
      <h2>Deletion test</h2>
      <div className="body">
        <p>Same obligations, memory on vs memory deleted. Re-runs the experiment live:</p>
        <div id="ablation-result">
          {!result && !running && !error && (
            <span className="empty">Not run yet in this session.</span>
          )}
          {running && <span className="shimmer">Running with-memory vs without-memory arms…</span>}
          {error && <div className="toast">Deletion test failed: {error}</div>}
          {result && (
            <>
              <div className="stat good">
                With memory: {result.withBlocked}/{result.withTotal} harmful payments blocked
                <div className="proof-bar">
                  <div
                    className="proof-fill good"
                    style={{ width: (100 * result.withBlocked) / Math.max(1, result.withTotal) + "%" }}
                  />
                </div>
              </div>
              <div className="stat bad">
                Without: {result.withoutAllowed}/{result.withoutTotal} sail through
                <div className="proof-bar">
                  <div
                    className="proof-fill bad"
                    style={{ width: (100 * result.withoutAllowed) / Math.max(1, result.withoutTotal) + "%" }}
                  />
                </div>
              </div>
              <div>
                Blocked by category:{" "}
                {Object.entries(result.byCategory || {})
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </div>
            </>
          )}
        </div>
        <button type="button" onClick={run} disabled={running}>
          {running ? "Running…" : "Run the deletion test"}
        </button>
      </div>
    </section>
  );
}
