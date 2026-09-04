# Nunes AI

**Three agents. One shared memory. No contradictions.**

Nunes AI is a team of three autonomous agents - **planner** (vendors, bans,
directives), **policy** (spending rules), **payments** (guarded settlement on
Base) - that share one persistent Sibyl memory. Every decision, ban, payment,
and rule is written to that memory, and a guard refuses any action that
contradicts what a teammate recorded - across sessions. Delete the memory and
the team becomes strangers: it re-pays, re-approves bans, and enforces nothing.

## Talk to the team

```bash
pip install -r requirements.txt
cp .env.example .env        # INCEPTION_API_KEY for the agents' brains;
                            # BASE_RPC_URL + BASE_PRIVATE_KEY + NUNES_AI_SIMULATE=0 for real settlement
python -m agent.chat        # interactive session; memory persists at ~/.sibyl-memory/nunes-ai.db
```

Say things like "ban vendor 0x... (alias evil-corp), they drained a partner",
"set rule v2: cap 10 USDC from September", or "pay 5 USDC to 0x... for
invoice-404". A dispatcher routes each request to the right agent; the agent
recalls shared memory, decides, and acts. In a new session tomorrow, payments
will still refuse the vendor planner banned today - and cite the ban.

Without keys the agents run in simulation mode (decisions + memory are real,
settlement is simulated). With live credentials the payments agent broadcasts
real Base Sepolia USDC transfers once the memory guard allows.

## The problem

The agent economy gave AI agents wallets but not operational memory. The results are
documented repeatedly in the wild:

- an agent **retries a timed-out payment and pays twice** (CrewAI issue #5802: "no
  idempotency guard - duplicate payments, emails, trades possible");
- an agent **approves an address or contract that was previously rejected**;
- an agent **falls for a prompt-injected transfer** - the Grok/Bankr drain took $150k+ on
  Base via an encoded message; Coinbase AgentKit shipped wallet-drain + infinite-approval
  findings through HackerOne;
- after the fact, there is **no reconstructable record of why an action was taken**.

Identity (KYA) and payment transport (x402) exist. **Decision memory is the missing layer.**

## The solution

Before any onchain action, Nunes AI consults an exact, temporal, append-only Sibyl memory:

- *"Have we already paid this intent on this chain?"* -> refuse the double-spend
- *"Was this address / vendor previously banned?"* -> refuse (exact, and via FTS5 alias recall)
- *"Which spending rule was in force when the obligation was incurred?"* -> enforce that version

After the action, it writes an immutable decision record -
`intent -> recalled context -> policy applied -> tx hash -> outcome` - that anchors to the
Base settlement. **Memory is the control.** Delete it and the core function of keeping the
agent safe breaks.

## Architecture

```
you --> [ dispatcher ] --> planner  --> approve/ban vendors, directives ─┐
                          policy   --> spending rules, caps ──────────────┤
                          payments --> pay on Base (USDC) ────────────────┤
                                                                         v
                                                     [ shared Sibyl memory + guard ]
                                                     every action recalled first,
                                                     every decision journaled after
```

Each agent is an LLM tool-calling loop (`agent/runtime.py`) with its own role
prompt and tool belt (`agent/roles.py`, `agent/toolkit.py`); all three read
and write the same `MemoryStore`, and the guard (`agent/guard.py`) refuses
cross-agent contradictions: payments cannot pay a planner-banned vendor,
policy cannot set a rule above the planner's directive cap, and no one can
re-approve a ban without an explicit recorded override.

Tiers used:
  WARM  entities        paid intents, approved/banned counterparties, spending rules, directives
  COLD  journal         every decision: who, what was recalled, policy applied, tx, outcome
  HOT   state           session policy snapshot
  FTS5  search          recall "was this vendor flagged / this intent already paid?"
```

The `--no-memory` flag ablates the memory layer: the same request that was refused sails
through and pays again. That ablation *is* the demo.

## Getting started

```bash
pip install -r requirements.txt
cp .env.example .env        # optional: Base Sepolia RPC + private key for real settlement
python -m agent.cli demo    # four-beat safety demo (simulated settlement by default)
python -m agent.chat        # the real product: talk to the three-agent team
```

For real onchain settlement set `BASE_RPC_URL`, `BASE_PRIVATE_KEY` and
`NUNES_AI_SIMULATE=0` in `.env`. Without keys the agent settles in simulation mode.

See [docs/demo.md](docs/demo.md) for the four-beat script, the three-process
fresh-session proof, and the ablation.

## Safety model

`intent_id` is the obligation key and **must be minted by the caller before the model runs** -
never by the LLM, or a re-prompt hands back a fresh key and the guard is bypassed
(the same lesson as durable-execution idempotency keys).

Safety properties enforced by the payment path (`agent/cli.py`):

- **`--no-memory` never broadcasts real funds.** The ablation forces simulation even
  when live credentials are configured - the demo can't spend unguarded money.
- **Claim before broadcast.** A live payment first writes a `pending` claim to memory
  (compare-and-set); concurrent or retried runs are refused while the claim is held.
- **Paid only on receipt.** The tx hash is verified against the locally signed hash, the
  chain id is checked against Base Sepolia, and the onchain receipt is confirmed before
  the intent is marked `paid`. A reverted tx marks the attempt `failed` (retry allowed);
  an unconfirmed tx stays `pending` (fails safe - no double-pay).

## Where memory is load-bearing (for judges)

| What | Where |
| --- | --- |
| **Memory reads** (the guard's recalls: paid-intent, counterparty ban/alias, temporal rule) | `agent/guard.py` - `Guard.check()` |
| **Memory writes** (paid marker + ALLOW/BLOCK decision records to the COLD journal) | `agent/guard.py` - `record_allowed_and_paid()` / `record_blocked()`; `agent/memory.py` - `record_paid()`, `claim_intent()` |
| Sibyl MemoryClient tier wrapper (WARM entities, COLD journal, HOT state, FTS5 search) | `agent/memory.py` - `MemoryStore` |
| The ablation (`--no-memory`) that proves load-bearing | `agent/cli.py` - `cmd_pay()` |

Delete those calls and every safety check disappears: the agent double-pays, re-approves
banned counterparties, and enforces no policy. That is the gate.

## Live settlement evidence

A real guarded payment on Base Sepolia (executed Sep 3, 2026):

- tx: `0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e`
  ([BaseScan](https://sepolia.basescan.org/tx/0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e))
- replaying the same intent in a fresh process is refused with the journaled tx hash
  (see [docs/demo.md](docs/demo.md)).

## Prior work declaration

All work in this repository - the `agent/` package, tests, and docs - was written
during the Sep 1-10, 2026 build window of the [Sibyl Labs Hackathon](https://hack.sibyllabs.org/).
No pre-existing codebase was reused; the only dependencies are the public packages in
`requirements.txt` (notably `sibyl-memory-client`, the required stack).

## License

Apache-2.0
