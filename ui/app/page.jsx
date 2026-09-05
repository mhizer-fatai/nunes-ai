import Link from "next/link";
import Nav from "./components/Nav";
import { Reveal, ScrollProgress } from "./components/Motion";

const NAV_LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#solution", label: "Solution" },
  { href: "#team", label: "Agents" },
  { href: "#proof", label: "Proof" },
  { href: "#live", label: "Live" },
];

const CAUSES = [
  {
    n: "ROOT CAUSE 01",
    title: "The model's reasoning was the authorization",
    mech:
      "Nothing sat between “the agent decided” and “the money moved.” No gate, no second check — so whoever could talk to the agent could spend its wallet.",
    incidents: [
      {
        amt: "$150K+",
        what:
          "An attacker gifted the wallet an NFT that silently unlocked its transfer tools, then posted an instruction hidden in Morse code. Grok decoded it, reposted it, and Bankr's feed parser signed the agent's own output as a transfer command. No key stolen, no contract exploited, the chain worked fine.",
        src: "https://ambcrypto.com/ai-linked-wallet-drained-via-prompt-injection-in-bankr-exploit/",
        label: "Grok / Bankr, May 2026",
      },
      {
        amt: "$47K",
        what:
          "Pure semantics: the attacker convinced the agent that “approveTransfer” meant approving an incoming contribution rather than sending funds out. Its own reasoning was turned against it.",
        src: "https://www.akinciborg.com/blog/posts/crypto-ai-agent-hacking.html",
        label: "Freysa",
      },
      {
        amt: "∞ approvals",
        what:
          "Coinbase's own agent toolkit let injected input steer the model straight into transfer calls with no human confirmation gate — plus unlimited ERC-20 approvals. Validated on Base Sepolia via HackerOne.",
        src: "https://www.chaincatcher.com/en/article/2258728",
        label: "AgentKit, Feb 2026",
      },
    ],
    verdict: {
      kind: "blocked",
      tag: "Nunes blocks this",
      text:
        "The model only proposes. A deterministic guard disposes — and the recipient is read from the vendor directory in memory, never from model text.",
    },
  },
  {
    n: "ROOT CAUSE 02",
    title: "No memory that the action already happened",
    mech:
      "The work succeeded, the response was lost, the agent retried — and nothing durable recorded “already done.” So it did it again.",
    incidents: [
      {
        amt: "×2 payments",
        what:
          "CrewAI issue #5802: when a task fails after its tool already ran, the retry re-invokes the payment function. Their words: “duplicate payments, emails, trades possible.” No idempotency guard exists.",
        src: "https://github.com/crewAIInc/crewAI/issues/5802",
        label: "CrewAI #5802",
      },
      {
        amt: "43× / 200×3",
        what:
          "One lost response spawned 43 duplicate support tickets and 43 duplicate emails. A restarted agent resent a whole batch — 200 leads got the same email three times in 24 hours.",
        src: "https://www.redhat.com/en/blog/why-good-ai-agents-fail-production-missing-infrastructure-layer",
        label: "Red Hat",
      },
    ],
    verdict: {
      kind: "blocked",
      tag: "Nunes blocks this",
      text:
        "Every obligation is claimed in memory before broadcast and marked paid with its tx hash after. A replay is refused, citing the original transaction.",
    },
  },
  {
    n: "ROOT CAUSE 03",
    title: "The infrastructure itself was compromised",
    mech:
      "Not a trick and not a memory failure — a break-in. Attackers reached the agent's own control surface and queued actions directly.",
    incidents: [
      {
        amt: "$106K",
        what:
          "Attackers accessed the agent's dashboard and queued malicious replies, causing its wallet to send 55.5 ETH.",
        src: "https://blockonomi.com/ai-crypto-bot-aixbt-loses-106200-in-eth-through-dashboard-breach/",
        label: "AIXBT, Mar 2025",
      },
    ],
    verdict: {
      kind: "honest",
      tag: "Nunes does not fix this",
      text:
        "If someone owns your server, memory will not save you. It does limit the blast radius: live payments only reach addresses a planner already registered, so funds cannot be redirected to a fresh address.",
    },
  },
];

const AGENTS = [
  {
    key: "planner",
    role: "Planner",
    title: "Decides who to trust",
    body: "Bans scammers, approves vendors, and writes standing directives the whole team must obey — every verdict signed with its name.",
    bullets: ["Ban with alias trail", "Register vendor addresses", "Directives that cap the team"],
  },
  {
    key: "policy",
    role: "Policy",
    title: "Sets the spending rules",
    body: "Caps and effective dates. Every payment is judged under the rule that was in force when the obligation was incurred — not today's rule.",
    bullets: ["Dated, versioned rules", "Cannot exceed a directive", "Temporal recall"],
  },
  {
    key: "payments",
    role: "Payments",
    title: "Moves the money",
    body: "Settles USDC on Base and buys x402 paywalls — and refuses whatever memory forbids, quoting the record back at you.",
    bullets: ["Real USDC on Base", "Memory-gated x402", "Refuses before signing"],
  },
];

const TXS = [
  { hash: "0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e", label: "USDC transfer" },
  { hash: "0x15274fda7af3cf75bd3b98ed073208a8564fe78ee0ea4611439efcbda58ba15c", label: "agent payment" },
  { hash: "0x7cf2cb70f40b251281ce2626c1f104ebeb095045b113552a71ede2f514c8a537", label: "x402 purchase" },
];

const STEPS = [
  { n: "01", t: "Decide once", d: "Planner bans a scammer, Policy caps spending, Payments settles — and every decision is written to shared memory with the agent's name on it." },
  { n: "02", t: "Recall always", d: "Before a dollar moves: already paid? banned — exactly, by alias, or fuzzy over the journal? which rule was in force? No recall, no payment." },
  { n: "03", t: "Refuse or pay", d: "A deterministic guard disposes what the model proposes. Replays, bans and over-cap demands are refused with evidence — the signature is never created." },
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
            Launch app
          </Link>
        }
      />

      <section className="hero">
        <div className="hero-grid" aria-hidden="true" />
        <div className="wrap">
          <Reveal>
            <span className="pill" style={{ marginBottom: 22 }}>
              <span className="dot" /> Sibyl Labs Hackathon 2026 · live on Base
            </span>
          </Reveal>
          <Reveal delay={60}>
            <h1>
              Three agents. One shared memory.{" "}
              <span className="grad">No contradictions.</span>
            </h1>
          </Reveal>
          <Reveal delay={120}>
            <p className="hero-lede">
              Nunes AI is a finance team of AI agents that moves real USDC on Base under rules it
              cannot forget. Every ban, cap and payment is written to one shared memory — and
              memory refuses whatever contradicts it, in any future session.
            </p>
          </Reveal>
          <Reveal delay={180}>
            <div className="cta-row">
              <Link className="btn btn-primary" href="/app">
                Talk to the team →
              </Link>
              <a className="btn btn-ghost" href="#proof">
                See the deletion test
              </a>
            </div>
          </Reveal>
          <Reveal delay={240}>
            <div className="hero-meta">
              <div>
                <b>160/160</b> harmful payments blocked
              </div>
              <div>
                <b>0/160</b> blocked without memory
              </div>
              <div>
                <b>3</b> live transactions on Base
              </div>
              <div>
                <b>38</b> automated tests passing
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="section" id="problem">
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The problem</div>
            <h2 className="section-title">Agents got wallets, but no memory.</h2>
            <p className="section-lede" style={{ marginBottom: 34 }}>
              The agent economy gave AI agents the power to move money — without any memory of
              their own financial decisions. Every session starts as a stranger holding your
              wallet. Real money has already been lost, and it traces back to three root causes.
            </p>
          </Reveal>
          {CAUSES.map((c, i) => (
            <Reveal key={c.n} delay={i * 90} variant="reveal-left">
              <div className={"cause" + (c.verdict.kind === "honest" ? " scope" : "")}>
                <div className="cause-n">{c.n}</div>
                <h3>{c.title}</h3>
                <p className="mech">{c.mech}</p>
                {c.incidents.map((inc) => (
                  <div className="incident" key={inc.label}>
                    <span className="amt">{inc.amt}</span>
                    <span className="what">
                      {inc.what}{" "}
                      <a href={inc.src} target="_blank" rel="noopener">
                        {inc.label} ↗
                      </a>
                    </span>
                  </div>
                ))}
                <div className={"verdict " + c.verdict.kind}>
                  <span className="tag">{c.verdict.tag}</span>
                  <span className="txt">{c.verdict.text}</span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="section" id="solution">
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The solution</div>
            <h2 className="section-title">Memory is the control, not a feature.</h2>
            <p className="section-lede" style={{ marginBottom: 34 }}>
              The model proposes; deterministic code disposes. Every action passes through a guard
              that reads shared memory first and records the outcome after.
            </p>
          </Reveal>
          <div className="grid-3">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 100} variant="reveal-scale">
                <div className="card card-lift step">
                  <div className="n">{s.n} — {s.t.toUpperCase()}</div>
                  <h3>{s.t}</h3>
                  <p>{s.d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="team">
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The team</div>
            <h2 className="section-title">Three agents, three jobs, one notebook.</h2>
            <p className="section-lede" style={{ marginBottom: 34 }}>
              Each agent is a real tool-calling loop with its own role and tool belt. They never
              meet — they coordinate entirely through what they write down.
            </p>
          </Reveal>
          <div className="grid-3">
            {AGENTS.map((a, i) => (
              <Reveal key={a.key} delay={i * 100}>
                <div className={"card card-lift agent-card " + a.key}>
                  <span className="role">{a.role}</span>
                  <h3>{a.title}</h3>
                  <p>{a.body}</p>
                  <ul>
                    {a.bullets.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="proof">
        <div className="wrap">
          <Reveal>
            <div className="eyebrow">The proof</div>
            <h2 className="section-title">Delete the memory and it pays the scammer.</h2>
            <p className="section-lede" style={{ marginBottom: 34 }}>
              240 payment decisions — legit payments, replays, banned vendors and over-cap demands
              — each checked in a fresh session, with memory and without. Same obligations. The
              only variable is memory.
            </p>
          </Reveal>
          <div className="proof-wrap">
            <Reveal variant="reveal-scale">
              <div className="stat good">
                <div className="k">With memory</div>
                <div className="v">160 / 160</div>
                <div className="d">harmful payments blocked — and all 80 legitimate payments still went through.</div>
                <div className="bar good">
                  <i style={{ width: "100%" }} />
                </div>
              </div>
            </Reveal>
            <Reveal delay={120} variant="reveal-scale">
              <div className="stat bad">
                <div className="k">Memory deleted</div>
                <div className="v">160 / 160</div>
                <div className="d">sail straight through. Zero blocked. The team becomes strangers with a wallet.</div>
                <div className="bar bad">
                  <i style={{ width: "100%" }} />
                </div>
              </div>
            </Reveal>
          </div>
          <Reveal delay={180}>
            <p style={{ color: "var(--ink-3)", fontSize: 14, marginTop: 18 }}>
              x402 purchases tell the same story in reverse: 60/60 completed with memory, 0/60 even
              possible without it — the agent refuses to sign an unguarded authorization.{" "}
              <Link href="/app" style={{ color: "var(--primary)", fontWeight: 600, textDecoration: "none" }}>
                Re-run it live in the app →
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
