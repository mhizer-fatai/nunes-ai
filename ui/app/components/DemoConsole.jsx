"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function clsFor(raw) {
  const t = String(raw || "").trim();
  if (t.startsWith("[BLOCK]")) return "refuse";
  if (t.startsWith("[ALLOW]")) return "allow";
  if (/\bPAID\b/.test(t)) return "allow";
  if (/^wiped memory db/.test(t)) return "warn";
  if (/^banned /.test(t)) return "warn";
  if (/^rule .* set:/i.test(t)) return "warn";
  if (/memory layer deleted|forcing simulation|no idempotency/.test(t)) return "warn";
  if (/^reason:|^journal:|^recall|^tx:|^settle:|^intent:|^counterparty|^memory :/.test(t) ||
      /waiting on Sibyl|marked paid/.test(t)) return "dim";
  return "out";
}

export default function DemoConsole() {
  const [lines, setLines] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const runId = useRef(0);
  const bodyRef = useRef(null);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const play = useCallback(async () => {
    const id = ++runId.current;
    setBusy(true);
    setError(null);
    setLines([]);
    let data;
    try {
      const res = await fetch("/api/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error((data.error && data.error.message) || "demo failed: " + res.status);
      }
    } catch (e) {
      setError(e.message);
      setBusy(false);
      return;
    }
    const add = (cls, text) => {
      if (runId.current !== id) return;
      setLines((prev) => [...prev, { cls, text }]);
    };
    for (const step of data.steps || []) {
      if (runId.current !== id) return;
      add("sep", step.banner);
      await sleep(430);
      add("cmd", step.cmd);
      await sleep(140);
      const outs = String(step.out || "").split("\n").filter((l) => l.trim());
      for (const raw of outs) {
        if (runId.current !== id) return;
        const cls = clsFor(raw);
        add(cls, raw);
        await sleep(cls === "refuse" || cls === "allow" ? 500 : 48);
      }
      await sleep(160);
    }
    if (runId.current === id) setBusy(false);
  }, []);

  useEffect(() => {
    play();
    return () => {
      runId.current++;
    };
  }, [play]);

  return (
    <>
      <div className="console">
        <div className="console-bar">
          <div className="dots" aria-hidden="true">
            <i /><i /><i />
          </div>
          <span className="title">nunes console — shared memory · the guard</span>
          <span className="spacer" />
          <span className="chip">sim · throwaway db</span>
        </div>
        <div className="console-body" ref={bodyRef} aria-live="polite">
          {error && <div className="ln refuse">error: {error}</div>}
          {lines.length === 0 && !error && (
            <div className="ln dim">spinning up a fresh team session…</div>
          )}
          {lines.map((l, i) => (
            <div className={"ln " + l.cls} key={i}>
              {l.text}
            </div>
          ))}
          {busy && <span className="cursor" aria-hidden="true" />}
        </div>
      </div>
      <div className="console-foot">
        <button className="btn btn-ghost btn-sm" type="button" onClick={play} disabled={busy}>
          {busy ? "Running…" : "Replay the demo"}
        </button>
        <span className="hint">
          Runs `python -m agent.cli` under the hood — the refusals you see are real guard
          decisions from shared memory, on a throwaway db. Settlement is forced to simulation.
        </span>
      </div>
    </>
  );
}
