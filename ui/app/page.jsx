import Link from "next/link";
import Nav from "./components/Nav";
import { Reveal, ScrollProgress } from "./components/Motion";

const NAV_LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#how", label: "How it works" },
  { href: "#proof", label: "Proof" },
  { href: "#live", label: "Live" },
];

/* Confirmed, sourced losses — conservative figures. */
const INCIDENTS = [
  {
    amt: "~$174,000",
    what: "drained from an AI wallet on Base — a prompt-injected message made Grok sign away 93% of its own holdings (Grok / Bankr, May 2026).",
    src: "https://ambcrypto.com/ai-linked-wallet-drained-via-prompt-injection-in-bankr-exploit/",
    label: "Ambcrypto",
  },
  {
    amt: "~$330,000",
    what: "taken from the same AI wallet a year earlier via social engineering (BNKR, DRB, WETH, Mar 2025).",
    src: "https://ourcryptotalk.com/news/grok-wallet-drained-3b-drb-prompt-injection-attack",
    label: "OurCryptoTalk",
  },
  {
    amt: "~$500,000",
    what: "drained from a live wallet by a malicious LLM router — 428 routers tested, one stole funds (Apr 2026, arXiv study).",
    src: "https://www.coindesk.com/tech/2026/04/13/ai-agents-are-set-to-power-crypto-payments-but-a-hidden-flaw-could-expose-wallets",
    label: "CoinDesk",
  },
  {
    amt: "duplicate",
    what: "CrewAI #5802 and LangGraph #7417: when an agent retries after a lost response, its payment tools fire again — no idempotency guard exists.",
    src: "https://github.com/crewAIInc/crewAI/issues/5802",
    label: "GitHub",
  },
  {
    amt: "43× / 200×3",
    what: "one lost response spawned 43 duplicate tickets; a restarted agent resent a batch — 200 recipients emailed three times in a day (Red Hat).",
    src: "https://www.redhat.com/en/blog/why-good-ai-agents-fail-production-missing-infrastructure-layer",
    label: "Red Hat",
  },
];

const PILLARS = [
  {
    n: "ROBBED",
    amt: "~$174K on Base",
    title: "Prompt injection drains wallets",
    body: "No key stolen, no contract broken — an attacker just talked the agent into sending its own funds. The wallet did exactly what it was told.",
  },
  {
    n: "CHARGED TWICE",
    amt: "retries re-fire",
    title: "No memory that it already paid",
    body: "Response lost, agent retries, payment tool fires again. CrewAI and LangGraph both document this — no idempotency guard ships by default.",
  },
  {
    n: "UNGUARDED",
    amt: "no gate",
    title: "Nothing between deciding and sending",
    body: "The model's reasoning becomes the authorization. Whoever can talk to the agent can spend its wallet.",
  },
];

const AGENTS = [
  {
    key: "planner",
    role: "Planner",
    icon: "◈",
    what: "decides who gets paid",
    how: "bans scammers and registers vendors so money can only reach addresses the team trusts.",
  },
  {
    key: "policy",
    role: "Policy",
    icon: "❒",
    what: "decides how much",
    how: "sets the spending rules — every payment is judged under the cap that was in force when it was incurred.",
  },
  {
    key: "payments",
    role: "Payments",
    icon: "●",
    what: "does the paying",
    how: "settles USDC on Base and buys x402 paywalls — refusing anything memory forbids, citing the record.",
  },
];

const STEPS = [
  {
    n: "01",
    t: "Decide once",
    d: "Planner bans a scammer, Policy caps spending, Payments settles — and every decision is written to one shared memory with the agent's name on it.",
  },
  {
    n: "02",
    t: "Recall before every payment",
    d: "Before a dollar moves the payee is checked against memory: already paid? banned — exactly, by alias, or fuzzy over the journal? over the cap? No recall, no payment, no signature.",
  },
  {
    n: "03",
    t: "Refuse or pay — never both, never twice",
    d: "A deterministic guard disposes what the model proposes. Replays, banned payees and over-cap demands are refused with evidence. And when it pays, it's real USDC on Base with a receipt kept forever.",
  },
];

const TXS = [
  { hash: "0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e", label: "USDC transfer" },
  { hash: "0x15274fda7af3cf75bd3b98ed073208a8564fe78ee0ea4611439efcbda58ba15c", label: "agent payment" },
  { hash: "0x7cf2cb70f40b251281ce2626c1f104ebeb095045b113552a71ede2f514c8a537", label: "x402 purchase" },
];

function short(h) {
  return h.slice(0, 10) + "…" + h.slice(-8);
}

export default function Landing() {
  return (
    <>
      <ScrollProgress />
      <Nav
        links={NAV_LINKS}
        cta={
          <Link className="btn btn-primary btn-sm" href="/app">
            Start free
          </Link>
        }
      />

      <section className="hero">
        <div className="hero-grid" aria-hidden="true" />
        <div className="wrap">
          <Reveal>
            <span
              className="hero-badge"
              style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
            >
              <span
                style={{ width: 7, height: 7, borderRadius: 999, background: "var(--green)", display: "inline-block" }}
              />
              The money layer AI agents can't outsmart
            </span>
          </Reveal>
          <Reveal delay={70}>
            <h1>
              Let your AI agents send money — <br />
              without getting robbed, double-charged, or tricked.
            </h1>
          </Reveal>
          <Reveal delay={140}>
            <p className="hero-lede">
              AI agents are holding wallets now — paying invoices, buying services on x402. But
              they don't remember their own decisions, so they get drained, pay twice, and re-approve
              what they already rejected. Nunes AI gives them the memory that stops all three.
            </p>
          </Reveal>
          <Reveal delay={200}>
            <div className="cta-row">
              <Link className="btn btn-primary" href="/app">
                Start free
              </Link>
              <Link className="btn btn-ghost" href="#how">
                How it works
              </Link>
            </div>
            <div className="hero-caption">Real USDC on Base · memory-gated x402 · Apache-2.0</div>
          </Reveal>

          <Reveal delay={260}>
            <div className="preview">
              <div className="preview-top">
                Your agents, guarded
                <span className="pill ok live">
                  <span className="dot" /> 1 shared memory
                </span>
              </div>
              <div className="preview-grid">
                <div className="preview-side">
                  <div>Payments</div>
                  <div>Policy</div>
                  <div>Planner</div>
                  <div>Shared memory</div>
                  <div className="on">Money guard</div>
                </div>
                <div className="preview-main">
                  <div className="preview-stats">
                    <div className="pstat">
                      <div className="n">3</div>
                      <div className="l">Agents sharing one memory</div>
                    </div>
                    <div className="pstat">
                      <div className="n">0</div>
                      <div className="l">Pays a banned payee · ever</div>
                      <div className="d up">guard refuses, evidence cited</div>
                    </div>
                    <div className="pstat">
                      <div className="n">0</div>
                      <div className="l">Pays an invoice twice</div>
                      <div className="d up">replays blocked by memory</div>
                    </div>
                  </div>
                  <div className="preview-rows">
                    <div className="prow">
                      <span className="chip block">refused</span> evil-corp payment blocked — banned in memory
                      <span className="st no">BLOCKED</span>
                    </div>
                    <div className="prow">
                      <span className="chip rule">rule</span> Policy cap 5 USDC · 0.05 USDC payment allowed
                      <span className="st ok">ALLOWED</span>
                    </div>
                    <div className="prow">
                      <span className="chip x402">x402</span> feed purchase · 0.01 USDC on Base
                      <span className="st ok">SETTLED</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="section" id="problem">
        <div className="wrap">
          <Reveal>
            <div className="split">
              <div>
                <div className="split-num">01</div>
                <div className="split-kicker">The problem</div>
                <h2>AI agents got wallets. They have no memory.</h2>
              </div>
              <p className="lede">
                Real money has already left agent wallets — not because keys were stolen or chains
                broke, but because nothing stopped a talk-to-the-agent attack, a retry, or an
                unauthorized approval. Every session starts as a stranger holding your funds.
              </p>
            </div>
          </Reveal>
          <div className="grid-3" style={{ marginTop: 28 }}>
            {PILLARS.map((p, i) => (
              <Reveal key={p.n} delay={i * 90}>
                <div className="card card-lift agent-card">
                  <span className="role">{p.n}</span>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--red)", marginBottom: 10 }}>
                    {p.amt}
                  </div>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <div style={{ marginTop: 20 }}>
            {INCIDENTS.map((inc, i) => (
              <Reveal key={inc.label} delay={i * 60}>
                <div className="incident">
                  <span className="amt">{inc.amt}</span>
                  <span className="what">
                    {inc.what}{" "}
                    <a href={inc.src} target="_blank" rel="noopener">
                      {inc.label} ↗
                    </a>
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="how" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The solution</div>
            <h2 className="section-title">Memory is the control, not a feature.</h2>
            <p className="section-lede" style={{ marginBottom: 28 }}>
              A deterministic memory guard sits between “the agent decided” and “the money moved” —
              and every decision lives in one shared memory the whole team must obey.
            </p>
          </Reveal>
          <div className="grid-3">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 100}>
                <div className="card card-lift step" style={{ height: "100%" }}>
                  <div className="n">{s.n} — {s.t.toUpperCase()}</div>
                  <h3>{s.t}</h3>
                  <p>{s.d}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={80}>
            <div className="eyebrow" style={{ marginTop: 56 }}>Powered by three teammates</div>
            <h3 style={{ fontSize: 22, marginBottom: 4 }}>How it works — the sub-agents</h3>
            <p className="section-lede" style={{ marginBottom: 26 }}>
              Three specialised agents do the work. They never meet — they coordinate entirely
              through the shared memory, so no agent can undo what another decided.
            </p>
          </Reveal>
          <div className="grid-3">
            {AGENTS.map((a, i) => (
              <Reveal key={a.key} delay={i * 100}>
                <div className={"card card-lift agent-card " + a.key} style={{ height: "100%" }}>
                  <span className="role">
                    <span style={{ marginRight: 4 }}>{a.icon}</span> {a.role}
                  </span>
                  <h3>{a.what}</h3>
                  <p>{a.how}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="proof" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The proof</div>
            <h2 className="section-title">Delete the memory and it pays the scammer.</h2>
            <p className="section-lede" style={{ marginBottom: 28 }}>
              240 payment decisions — legit payments, replays, banned payees, over-cap demands —
              each checked in a fresh session, with memory and without.
            </p>
          </Reveal>
          <div className="proof-wrap">
            <Reveal variant="reveal-scale">
              <div className="stat good">
                <div className="k">With memory</div>
                <div className="v">160 / 160</div>
                <div className="d">harmful payments blocked — all 80 legitimate ones still went through.</div>
                <div className="bar good">
                  <i style={{ width: "100%" }} />
                </div>
              </div>
            </Reveal>
            <Reveal delay={120} variant="reveal-scale">
              <div className="stat bad">
                <div className="k">Memory deleted</div>
                <div className="v">160 / 160</div>
                <div className="d">sail straight through. Zero blocked — the team becomes strangers with a wallet.</div>
                <div className="bar bad">
                  <i style={{ width: "100%" }} />
                </div>
              </div>
            </Reveal>
          </div>
          <Reveal delay={180}>
            <p style={{ color: "var(--ink-3)", fontSize: 14, marginTop: 18 }}>
              x402 purchases: 60/60 completed with memory, 0/60 even possible without — the agent
              refuses to sign an unguarded authorization.{" "}
              <Link href="/app" style={{ color: "var(--primary)", fontWeight: 600, textDecoration: "none" }}>
                Run it live in the app →
              </Link>
            </p>
          </Reveal>
        </div>
      </section>

      <section className="section-sm" id="live">
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">Live on Base</div>
            <h2 className="section-title" style={{ fontSize: 26, marginBottom: 20 }}>
              Real transactions, not screenshots.
            </h2>
          </Reveal>
          <Reveal delay={80}>
            <div className="tx-strip">
              {TXS.map((t) => (
                <a
                  className="tx-card"
                  key={t.hash}
                  href={"https://sepolia.basescan.org/tx/" + t.hash}
                  target="_blank"
                  rel="noopener"
                >
                  <span className="h">{short(t.hash)} ↗</span>
                  <span className="l">{t.label}</span>
                </a>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap footer-inner">
          <a href="https://github.com/mhizer-fatai/nunes-ai" target="_blank" rel="noopener">
            GitHub
          </a>
          <Link href="/app">Launch app</Link>
          <span className="spacer">Sibyl Labs Hackathon 2026 · Apache-2.0</span>
        </div>
      </footer>
    </>
  );
}