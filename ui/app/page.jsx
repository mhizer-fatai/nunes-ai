import Link from "next/link";

const TXS = [
  { hash: "0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e", label: "USDC transfer" },
  { hash: "0x15274fda7af3cf75bd3b98ed073208a8564fe78ee0ea4611439efcbda58ba15c", label: "agent payment" },
  { hash: "0x7cf2cb70f40b251281ce2626c1f104ebeb095045b113552a71ede2f514c8a537", label: "x402 purchase" },
];

const FAILURES = [
  {
    amount: "$150K+",
    text: "drained from an AI agent's wallet on Base by a prompt-injected message hidden in Morse code (Grok / Bankr, May 2026).",
    source: "https://ambcrypto.com/ai-linked-wallet-drained-via-prompt-injection-in-bankr-exploit/",
    sourceLabel: "Ambcrypto",
  },
  {
    amount: "$106K",
    text: "taken from an AI trading agent's wallet after attackers queued malicious replies through its own dashboard (AIXBT, Mar 2025).",
    source: "https://blockonomi.com/ai-crypto-bot-aixbt-loses-106200-in-eth-through-dashboard-breach/",
    sourceLabel: "Blockonomi",
  },
  {
    amount: "$47K",
    text: "extracted from an AI prize vault by reframing 'approveTransfer' as an incoming contribution (Freysa).",
    source: "https://www.akinciborg.com/blog/posts/crypto-ai-agent-hacking.html",
    sourceLabel: "Akıncıborg",
  },
  {
    amount: "∞ approvals",
    text: "Coinbase's own agent toolkit shipped prompt-injection plus unlimited ERC-20 approvals — validated on Base Sepolia via HackerOne, Feb 2026.",
    source: "https://www.chaincatcher.com/en/article/2258728",
    sourceLabel: "ChainCatcher",
  },
  {
    amount: "×2 everything",
    text: "CrewAI issue #5802: retrying a task re-fires its payment tools — 'duplicate payments, emails, trades possible.' No idempotency guard.",
    source: "https://github.com/crewAIInc/crewAI/issues/5802",
    sourceLabel: "GitHub",
  },
  {
    amount: "43× / 200×3",
    text: "One failed retry created 43 duplicate tickets; one restarted agent emailed 200 leads three times in 24 hours.",
    source: "https://www.redhat.com/en/blog/why-good-ai-agents-fail-production-missing-infrastructure-layer",
    sourceLabel: "Red Hat",
  },
];

function short(h) {
  return h.slice(0, 10) + "…" + h.slice(-8);
}

export default function Landing() {
  return (
    <>
      <header>
        <div className="brand">
          Nunes <span>AI</span>
        </div>
        <nav className="links">
          <a href="#problem">Problem</a>
          <a href="#solution">Solution</a>
          <a href="#proof">Proof</a>
          <a href="#live">Live</a>
          <Link href="/app">Agents</Link>
        </nav>
        <div className="pills">
          <Link className="pill" href="/app" style={{ textDecoration: "none" }}>
            Launch app
          </Link>
        </div>
      </header>

      <section className="hero">
        <h1>
          Three agents. One shared memory. <span className="grad">No contradictions.</span>
        </h1>
        <p>
          Nunes AI is a finance team of AI agents — Planner, Policy, Payments — that moves real
          USDC on Base under rules it cannot forget. Every ban, cap and payment is written to one
          shared memory, and memory refuses whatever contradicts it.
        </p>
        <div className="cta-row">
          <Link className="btn-primary" href="/app">
            Talk to the team
          </Link>
          <a className="btn-ghost" href="#proof">
            See the deletion test
          </a>
        </div>
      </section>

      <section className="band" id="problem">
        <h2 style={{ fontSize: 18 }}>The problem: agents got wallets, but no memory</h2>
        <p style={{ color: "var(--ink-dim)", fontSize: 15, maxWidth: 720 }}>
          The agent economy gave AI agents the power to move money — without any memory of their
          own financial decisions. Every session starts as a stranger holding your wallet. These
          are not hypotheticals; they are documented failures:
        </p>
        <div className="steps">
          {FAILURES.map((f) => (
            <div className="step" key={f.amount}>
              <div className="n">{f.amount}</div>
              <p>
                {f.text}{" "}
                <a
                  href={f.source}
                  target="_blank"
                  rel="noopener"
                  style={{ color: "var(--primary)", fontSize: 13 }}
                >
                  {f.sourceLabel} ↗
                </a>
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="band" id="solution">
        <h2 style={{ fontSize: 18 }}>The solution: memory is the control</h2>
        <div className="steps">
          <div className="step">
            <div className="n">DECIDE ONCE</div>
            <p>
              Planner bans a scammer, Policy caps spending, Payments settles — and every decision
              is written to shared memory with the agent&apos;s name on it.
            </p>
          </div>
          <div className="step">
            <div className="n">RECALL ALWAYS</div>
            <p>
              Before a dollar moves, the agent recalls: already paid? banned — exactly, by alias,
              or fuzzy over the journal? which rule was in force? No recall, no payment.
            </p>
          </div>
          <div className="step">
            <div className="n">REFUSE OR PAY</div>
            <p>
              A deterministic guard disposes what the model proposes. Replays, banned vendors and
              over-cap demands are refused with the evidence cited — the signature is never even
              created.
            </p>
          </div>
        </div>
      </section>

      <section className="agent-cards">
        <div className="card">
          <h3>Planner</h3>
          <p>Decides who to trust. Bans scammers, approves vendors, writes standing directives the whole team must obey.</p>
        </div>
        <div className="card">
          <h3>Policy</h3>
          <p>Sets the spending rules. Caps, effective dates — every payment is judged under the rule in force when it was incurred.</p>
        </div>
        <div className="card">
          <h3>Payments</h3>
          <p>Moves USDC on Base and buys x402 paywalls — and refuses whatever memory forbids, citing the record.</p>
        </div>
      </section>

      <section className="band" id="proof">
        <div className="stat good">
          With memory: 160/160 harmful payments blocked
          <div className="proof-bar">
            <div className="proof-fill good" style={{ width: "100%" }} />
          </div>
        </div>
        <div className="stat bad" style={{ marginTop: 12 }}>
          Without: 160/160 sail through
          <div className="proof-bar">
            <div className="proof-fill bad" style={{ width: "100%" }} />
          </div>
        </div>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          Same obligations. The only difference is memory. Re-run it live in the app — plus 60/60
          x402 purchases completed with memory vs 0/60 possible without it.
        </p>
      </section>

      <section className="band" id="live">
        <h2 style={{ fontSize: 18 }}>Live on Base</h2>
        <div className="tx-strip">
          {TXS.map((t) => (
            <a
              key={t.hash}
              href={"https://sepolia.basescan.org/tx/" + t.hash}
              target="_blank"
              rel="noopener"
            >
              {short(t.hash)} · {t.label} ↗
            </a>
          ))}
        </div>
      </section>

      <footer>
        <a href="https://github.com/mhizer-fatai/nunes-ai">Repo</a>
        <span>Sibyl Labs Hackathon 2026</span>
        <span>Apache-2.0</span>
      </footer>
    </>
  );
}
