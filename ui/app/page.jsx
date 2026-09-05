import Link from "next/link";

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
          <Link href="/app">Agents</Link>
          <a href="#proof">Proof</a>
          <a href="#live">Live</a>
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
          A finance team of AI agents that cannot contradict each other — every ban, rule and
          payment is written to shared memory, and memory refuses what contradicts it.
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
          Same obligations. The only difference is memory. Re-run it live in the app.
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

      <section className="band">
        <h2 style={{ fontSize: 18 }}>How it works</h2>
        <div className="steps">
          <div className="step">
            <div className="n">01 — TALK</div>
            <p>Chat with the team in plain English. A dispatcher routes you to the right agent.</p>
          </div>
          <div className="step">
            <div className="n">02 — RECALL</div>
            <p>Every action checks shared memory first: paid intents, bans, rules in force.</p>
          </div>
          <div className="step">
            <div className="n">03 — REFUSE OR PAY</div>
            <p>The guard decides, the journal records. Delete memory and the same request pays.</p>
          </div>
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
