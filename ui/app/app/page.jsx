"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Nav from "../components/Nav";
import { ScrollProgress } from "../components/Motion";
import ChatPanel from "../components/ChatPanel";
import JournalPanel from "../components/JournalPanel";
import AblationPanel from "../components/AblationPanel";

export default function AppScreen() {
  const [status, setStatus] = useState(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const res = await fetch("/api/status");
        if (!res.ok) throw new Error("status " + res.status);
        const data = await res.json();
        if (alive) setStatus(data);
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

  const memOk = status && !status.offline;
  const live = memOk && String(status.chain || "").startsWith("live");

  return (
    <>
      <ScrollProgress />
      <Nav
        cta={
          <Link className="btn btn-ghost btn-sm" href="/">
            Overview
          </Link>
        }
      />
      <div className="wrap">
        <div className="app-bar">
          <h1>Team workspace</h1>
          <div className="spacer" />
          <span
            className={"pill " + (memOk ? "ok" : "warn")}
            title={memOk ? status.memory : "backend unreachable"}
          >
            <span className="dot" />
            {memOk ? "shared memory connected" : "memory unreachable"}
          </span>
          <span className={"pill " + (live ? "ok" : "")}>
            <span className="dot" />
            {status ? (status.offline ? "chain unknown" : status.chain) : "…"}
          </span>
        </div>
        <div className="app-main">
          <ChatPanel onAnswered={refresh} />
          <div className="side-col">
            <JournalPanel tick={tick} />
            <AblationPanel />
          </div>
        </div>
      </div>
    </>
  );
}
