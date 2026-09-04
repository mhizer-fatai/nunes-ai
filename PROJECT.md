# Nunes AI - Project Definition

> The memory that makes an AI agent safe to trust with money.

**Built for:** [Sibyl Labs Hackathon](https://hack.sibyllabs.org/) · build window Sep 1-10 2026 ·
submission deadline **Sep 10, 23:59 UTC** · judging Sep 11-12 · winners Sep 13-15.

---

## 1. What we are building

Nunes AI is a **team of three autonomous agents sharing one memory**.

| Agent | Job | Tools |
| --- | --- | --- |
| **Planner** | Decides who the team does business with: approvals, bans, standing directives | approve/ban vendor, directive, recall |
| **Policy** | Sets the spending rules payments must obey | set-rule, recall (must fit the planner's directive cap) |
| **Payments** | Settles obligations on Base (USDC) - and refuses what memory forbids | pay, recall, payment lookup |

Each agent is a real LLM loop with its own role prompt and tool belt; a
dispatcher routes your instruction to the right teammate. Every decision is
written to shared Sibyl memory with the agent's name on it, and the guard
refuses anything that contradicts a teammate's recorded decision - **across
sessions and restarts**. Delete the memory and the team becomes strangers.

**What Nunes AI is not:** not a chatbot with memory, not a wallet dashboard with an LLM
bolted on, not a "remembers your preferences" assistant. The memory does not decorate the
product - it *is* the product.

## 2. The problem

The agent economy gave AI agents wallets (x402, Coinbase Agentic Wallets, AWS AgentCore
Payments) but **not operational memory of their own financial decisions**. Documented failures:

- **Duplicate payments / retry double-spend.** CrewAI issue #5802: "Tool re-execution on task
  retry has no idempotency guard - duplicate payments, emails, trades possible."
- **Prompt-injected drains.** Grok/Bankr lost $150k+ on **Base** via an encoded message
  (OECD AI incident DB). Coinbase AgentKit shipped wallet-drain + infinite-approval findings
  via HackerOne. Zscaler documented web campaigns injecting payment instructions at agents.
- **Re-approving what was rejected.** "banned" is never durably recorded, so a fresh session
  re-approves it.
- **No audit trail.** After the fact there is no reconstructable record of *why* a decision
  was taken.

## 3. The solution

The memory guard answers three questions before any onchain action:

1. **Idempotency** - has this intent already been paid on this chain? (refuse the double-pay)
2. **Counterparty** - is this address / vendor banned? (exact WARM recall, plus FTS5 recall
   of the alias trail so a banned vendor re-emerging under a new address is still refused)
3. **Temporal policy** - which spending rule was in force when the obligation was incurred?
   (obligations are judged under that version, not the current one)

After the action the guard writes an immutable COLD-journal record:
`intent -> recalled context -> policy applied -> tx hash -> outcome`, anchored to Base.

**Memory is the control.** `--no-memory` ablates the layer and the same request that was
refused sails through and pays again - the falsifiable proof of load-bearing memory.

## 4. Why Sibyl Memory and not a database

The Idempotency check alone *could* be a UNIQUE index. The project wins because of the two
checks a keyed table cannot do:

- **Temporal rule recall.** Two rules, overlapping obligations, "which was in force at ts?"
- **Fuzzy cross-session recall.** A previously-banned vendor under a new address, found by
  FTS5 over the journal rather than by exact key.

These use the memory tiering Sibyl markets (WARM entities, COLD append-only journal, FTS5,
HOT session state) as a decision plane - which is exactly what the #2 LongMemEval temporal
result is for.

## 5. Partner stacks

- **Base (verified, load-bearing):** every ALLOW produces a tx hash written into memory and
  read back by later sessions to refuse replays. Real settlement via `agent/chain.py`.
- **Virtuals:** not used - one verified stack (Base) is a x1.15; a decorative second stack
  is worth less than a solid one.

## 6. Build order & status (as of Sep 4)

| # | Item | Status |
| --- | --- | --- |
| 1 | Sibyl Memory wrapper (5 tiers) + directives + recall + actor tagging | done |
| 2 | Guard: idempotency / counterparty / temporal rule + cross-agent governance (ban-approve override, directive cap) | done |
| 3 | CLI: pay, ban, approve, set-rule, rules, search, events, wipe, demo | done |
| 4 | Base Sepolia executor (`agent/chain.py`) | done |
| 5 | `--no-memory` ablation + fresh-process proof | done (ablation now always simulates) |
| 6 | Tests (23 passing: guard, brain, team coordination) | done |
| 7 | README + docs/demo.md | done |
| 8 | Live Base Sepolia transaction | **done** - tx `0xa782a891...47441e`, receipt verified on BaseScan |
| 9 | Safety hardening: pending claim, receipt confirm, chain-id check | done |
| 10 | Real product: 3 LLM agents (planner/policy/payments) + dispatcher + `python -m agent.chat` | **done** - verified live: planner ban -> fresh-session payments refusal |
| 11 | Memory-gated x402: `buy` tool + guard hook inside the official SDK + demo vendor; live Sepolia purchase + replay refusal | **done** - tx `0x7cf2cb70...f514c8a537`, 6 offline tests, 35 total passing |
| 12 | 2-5 min demo video + 2 build-in-public posts | **next** |

## 7. Repo layout

```
agent/
  memory.py   Sibyl five-tier wrapper (WARM/COLD/HOT/FTS5) + directives + recall
  policy.py   PayRequest + GuardDecision
  guard.py    the memory gate + decision journaling + cross-agent governance
  chain.py    Base settlement (ERC-20 transfer, RPC via urllib)
  brain.py    single-shot LLM intent extraction (legacy `brain` command)
  llm.py      OpenAI-compatible transport incl. native function calling
  roles.py    the three agents: prompts, tool belts, dispatcher contract
  toolkit.py  all agent tools (guarded writes, settlement, recall)
  runtime.py  the agent loop + dispatcher
  chat.py     the product: `python -m agent.chat`
  cli.py      ops surface (pay/ban/rule/search/events/wipe/demo)
tests/test_guard.py  tests/test_brain.py  tests/test_team.py (23 passing)
docs/demo.md
```

## 8. Submission checklist

- [ ] public repo (Apache-2.0)
- [ ] 2-5 min demo video with an explicit fresh-session recall moment
- [ ] README
- [ ] 2 build-in-public posts
