"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import JournalPanel from "../components/JournalPanel";
import AblationPanel from "../components/AblationPanel";

export default function Home() {
  const [status, setStatus] = useState(null);
  const [journalTick, setJournalTick] = useState(0);
  const refreshJournal = useCallback(() => setJournalTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const res = await fetch("/api/status");
        if (res.ok) {
          const data = await res.json();
          if (alive) setStatus(data);
        }
      } catch {
        if (alive) setStatus({ offline: true });
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const chainLabel = !status
    ? "…"
    : status.offline
      ? "unreachable"
      : status.chain;

  return (
    <>
      <header>
        <div className="brand">
          Nunes <span>AI</span>
        </div>
        <div className="tagline">Three agents. One shared memory. No contradictions.</div>
        <div className="pills">
          <span className="pill" title={status && status.memory ? status.memory : ""}>
            memory: {status ? (status.offline ? "unreachable" : "connected") : "…"}
          </span>
          <span className="pill">chain: {chainLabel}</span>
        </div>
      </header>
      <main>
        <ChatPanel onAnswered={refreshJournal} />
        <div className="side">
          <JournalPanel tick={journalTick} />
          <AblationPanel />
        </div>
      </main>
    </>
  );
}
