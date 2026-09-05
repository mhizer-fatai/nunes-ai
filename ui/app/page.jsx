import Link from "next/link";
import Nav from "./components/Nav";
import { Reveal, ScrollProgress } from "./components/Motion";

const NAV_LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#solution", label: "Solution" },
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
    body: "Bans scammers, approves vendors, and writes standing directives the whole team must obey.",
  },
  {
    key: "policy",
    role: "Policy",
    title: "Sets the spending rules",
    body: "Caps and effective dates. Every payment is judged under the rule in force when it was incurred.",
  },
  {
    key: "payments",
    role: "Payments",
    title: "Moves the money",
    body: "Settles USDC on Base and buys x402 paywalls — refusing whatever memory forbids, citing the record.",
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
            <span className="hero-badge">
              <span className="dot" style={{ width: 7, height: 7, borderRadius: 999, background: "var(--green)", display: "inline-block" }} />
              New · Memory-gated payments are live
            </span>
          </Reveal>
          <Reveal delay={70}>
            <h1>Meet the AI finance team that never contradicts itself.</h1>
          </Reveal>
          <Reveal delay={140}>
            <p className="hero-lede">
              Nunes AI moves real USDC on Base under rules it cannot forget — every ban, cap and
              payment written to one shared memory. Talk to it, and watch it refuse what its past
              self forbade.
            </p>
          </Reveal>
          <Reveal delay={200}>
            <div className="cta-row">
              <Link className="btn btn-primary" href="/app">
                Start free
              </Link>
              <Link className="btn btn-ghost" href="#proof">
                See the deletion test
              </Link>
            </div>
            <div className="hero-caption">No credit card · runs on Base Sepolia · Apache-2.0</div>
          </Reveal>

          <Reveal delay={260}>
            <div className="preview">
              <div className="preview-top">
                Nunes AI · team workspace
                <span className="pill ok live">
                  <span className="dot" /> Agent active
                </span>
              </div>
              <div className="preview-grid">
                <div className="preview-side">
                  <div className="on">Team chat</div>
                  <div>Memory</div>
                  <div>Deletion test</div>
                </div>
                <div className="preview-main">
                  <div className="preview-stats">
                    <div className="pstat">
                      <div className="n">160</div>
                      <div className="l">Harmful blocked</div>
                      <div className="d up">+100% with memory</div>
                    </div>
                    <div className="pstat">
                      <div className="n">0</div>
                      <div className="l">Blocked without</div>
                      <div className="d down">−100% deleted</div>
                    </div>
                    <div className="pstat">
                      <div className="n">3</div>
                      <div className="l">Live txs on Base</div>
                      <div className="d up">receipts kept</div>
                    </div>
                  </div>
                  <div className="preview-rows">
                    <div className="prow">
                      <span className="chip block">block</span> evil-corp payment refused — banned
                      <span className="st no">REFUSED</span>
                    </div>
                    <div className="prow">
                      <span className="chip payment">paid</span> invoice-900 · 5 USDC settled
                      <span className="st ok">SETTLED</span>
                    </div>
                    <div className="prow">
                      <span className="chip x402">x402</span> feed purchase · 0.01 USDC
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
                <h2>Agents got wallets, but no memory.</h2>
              </div>
              <p className="lede">
                The agent economy gave AI agents the power to move money — without any memory of
                their own financial decisions. Every session starts as a stranger holding your
                wallet. Real money has already been lost, and it traces back to three root causes.
              </p>
            </div>
          </Reveal>
          <div style={{ marginTop: 28 }}>
            {CAUSES.map((c, i) => (
              <Reveal key={c.n} delay={i * 80}>
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
        </div>
      </section>

      <section className="section" id="solution" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <Reveal>
            <div className="split">
              <div>
                <div className="split-num">02</div>
                <div className="split-kicker">The solution</div>
                <h2>Memory is the control, not a feature.</h2>
              </div>
              <p className="lede">
                The model proposes; deterministic code disposes. Decide once, recall always, refuse
                or pay — with the evidence cited every time.
              </p>
            </div>
          </Reveal>
          <div className="grid-3" style={{ marginTop: 28 }}>
            {AGENTS.map((a, i) => (
              <Reveal key={a.key} delay={i * 100}>
                <div className={"card card-lift agent-card " + a.key} style={{ height: "100%" }}>
                  <span className="role">{a.role}</span>
                  <h3>{a.title}</h3>
                  <p>{a.body}</p>
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
              240 payment decisions — legit payments, replays, banned vendors, over-cap demands —
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
                <div className="d">sail straight through. Zero blocked.</div>
                <div className="bar bad">
                  <i style={{ width: "100%" }} />
                </div>
              </div>
            </Reveal>
          </div>
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
