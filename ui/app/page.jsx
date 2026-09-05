import Link from "next/link";

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
        <p style={{ color: "var(--ink-dim)", fontSize: 15, maxWidth: 760 }}>
          The agent economy gave AI agents the power to move money — without any memory of their
          own financial decisions. Every session starts as a stranger holding your wallet. Real
          money has already been lost, and the losses trace back to three root causes:
        </p>
        <div className="causes">
          {CAUSES.map((c) => (
            <div className={"cause" + (c.verdict.kind === "honest" ? " scope" : "")} key={c.n}>
              <div className="n">{c.n}</div>
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
                <span>{c.verdict.text}</span>
              </div>
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
