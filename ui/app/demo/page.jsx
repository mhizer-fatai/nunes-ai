"use client";

import { useState } from "react";
import Link from "next/link";
import Nav from "../components/Nav";
import { Reveal, ScrollProgress } from "../components/Motion";

const DEMO_VENDOR = "0x1111111111111111111111111111111111111111";
const DEMO_ALIAS = "evil-corp";
const DEMO_INVOICE = "invoice-7";

const BEATS = [
  {
    n: "BEAT 01",
    title: "Day one — the Planner bans a vendor",
    script: (
      <>
        A drainage report comes in. The planner checks shared memory, writes the ban with the
        reason, and every future session will see it. Message sent:{" "}
        <code>Ban vendor {DEMO_VENDOR.slice(0, 6)}…{DEMO_VENDOR.slice(-4)} alias {DEMO_ALIAS}, they drained a partner</code>
      </>
    ),
  },
  {
    n: "BEAT 02",
    title: "Day two — a stranger refuses to pay",
    script: (
      <>
        A brand-new session — a payments agent that never met the planner — is told to pay that
        vendor. It recalls shared memory first. Message sent:{" "}
        <code>Pay 2 USDC to {DEMO_VENDOR.slice(0, 6)}…{DEMO_VENDOR.slice(-4)} alias {DEMO_ALIAS} for {DEMO_INVOICE}</code>
      </>
    ),
  },
  {
    n: "BEAT 03",
    title: "Delete the memory — the same request pays",
    script: (
      <>
        The quantified proof, re-run live on a throwaway database: 24 obligations each, memory on
        versus memory deleted. Nothing here touches live memory.
      </>
    ),
  },
];

export default function Demo() {
  const [runs, setRuns] = useState([null, null, null]);
  const [busy, setBusy] = useState([false, false, false]);

  function setRun(i, value) {
    setRuns((r) => r.map((x, j) => (j === i ? value : x)));
  }
  function setBusyAt(i, value) {
    setBusy((b) => b.map((x, j) => (j === i ? value : x)));
  }

  async function postChat(message) {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data.error && data.error.message) || "request failed: " + res.status);
    return data;
  }

  async function runBeat(i) {
    setBusyAt(i, true);
    try {
      if (i === 0) {
        const d = await postChat(
          `Ban vendor ${DEMO_VENDOR} alias ${DEMO_ALIAS}, they drained a partner`
        );
        setRun(0, { who: d.agent || "planner", text: d.reply });
      } else if (i === 1) {
        const d = await postChat(
          `Pay 2 USDC to ${DEMO_VENDOR} alias ${DEMO_ALIAS} for ${DEMO_INVOICE}`
        );
        setRun(1, { who: d.agent || "payments", text: d.reply });
      } else {
        const res = await fetch("/api/ablation", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trials: 1 }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((data.error && data.error.message) || "request failed");
        setRun(2, {
          who: "system",
          text:
            `With memory: ${data.withBlocked}/${data.withTotal} harmful payments blocked.\n` +
            `Without: ${data.withoutAllowed}/${data.withoutTotal} sail through.`,
        });
      }
    } catch (e) {
      setRun(i, { who: "system", text: "Beat failed: " + e.message });
    } finally {
      setBusyAt(i, false);
    }
  }

  return (
    <>
      <ScrollProgress />
      <Nav
        links={[{ href: "/", label: "Overview" }]}
        cta={
          <Link className="btn btn-primary btn-sm" href="/app">
            Open workspace
          </Link>
        }
      />
      <div className="wrap" style={{ paddingTop: 48, paddingBottom: 64 }}>
        <Reveal>
          <div className="eyebrow">Guided demo · three beats</div>
          <h1 style={{ fontSize: "clamp(30px, 4.5vw, 46px)", marginBottom: 12 }}>
            Watch memory change what the team does.
          </h1>
          <p className="section-lede" style={{ marginBottom: 36 }}>
            Each beat executes live against the real backend — every request opens a fresh
            session on the same shared memory. Run them in order.
          </p>
        </Reveal>
        <div className="demo-beats">
          {BEATS.map((b, i) => (
            <Reveal key={b.n} delay={i * 80}>
              <div
                className={
                  "card beat" + (runs[i] ? " done" : "") + (!runs[i] && (i === 0 || runs[i - 1]) ? " active" : "")
                }
              >
                <div className="beat-top">
                  <span className="beat-num">{b.n}</span>
                  <h3>{b.title}</h3>
                </div>
                <p className="script">{b.script}</p>
                {runs[i] && (
                  <div className={"beat-result " + runs[i].who}>
                    <span className="who">{runs[i].who}</span>
                    <div>{runs[i].text}</div>
                  </div>
                )}
                <div className="beat-actions">
                  <button
                    className="btn btn-primary btn-sm"
                    type="button"
                    disabled={busy[i] || (i > 0 && !runs[i - 1])}
                    onClick={() => runBeat(i)}
                  >
                    {busy[i] ? "Running…" : runs[i] ? "Run again" : "Run this beat"}
                  </button>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </>
  );
}
