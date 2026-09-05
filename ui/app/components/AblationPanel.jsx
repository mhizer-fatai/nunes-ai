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
      if (!res.ok) {
        throw new Error((data.error && data.error.message) || "request failed: " + res.status);
      }
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="panel" aria-label="Deletion test">
      <div className="panel-head">
        <h2>Deletion test</h2>
      </div>
      <div className="ablation-body">
        <p>
          Runs the same obligations twice — once with shared memory, once with it deleted — on a
          throwaway database. Your live memory is never touched.
        </p>

        {error && <div className="toast">Deletion test failed: {error}</div>}

        {!result && !running && !error && (
          <div className="empty" style={{ padding: "10px 0" }}>
            Not run yet in this session.
          </div>
        )}

        {running && (
          <div className="mini-stat">
            <span className="shimmer">Running with-memory vs without-memory arms…</span>
          </div>
        )}

        {result && !running && (
          <>
            <div className="mini-stat good">
              <div className="num">
                {result.withBlocked} / {result.withTotal}
              </div>
              harmful payments blocked with memory
            </div>
            <div className="mini-stat bad">
              <div className="num">
                {result.withoutAllowed} / {result.withoutTotal}
              </div>
              sail through with memory deleted
            </div>
            <div className="cats">
              Blocked by category:{" "}
              {Object.entries(result.byCategory || {})
                .map(([k, v]) => `${k} ${v}`)
                .join(" · ")}
            </div>
          </>
        )}

        <button className="btn btn-ghost" type="button" onClick={run} disabled={running}>
          {running ? "Running…" : result ? "Run it again" : "Run the deletion test"}
        </button>
      </div>
    </section>
  );
}
