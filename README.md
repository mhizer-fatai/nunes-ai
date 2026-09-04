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

Everything below is on the critical path of every agent action. Delete these
calls and the core function breaks - that is the gate.

| What | Where |
| --- | --- |
| **Memory reads** - every payment recalls paid-intents, counterparty bans/alias trail, and the temporal rule: `Guard.check()` in `agent/guard.py:37` | `agent/guard.py` |
| **Memory reads** - governance recalls (ban before approve, directive cap before rule): `decide_vendor_change()` / `decide_rule()` in `agent/guard.py:186` | `agent/guard.py` |
| **Memory reads** - every agent's pre-action recall (FTS5 + entities + journal): `t_recall` in `agent/toolkit.py:57`, `MemoryStore.recall()` in `agent/memory.py:441` | `agent/toolkit.py`, `agent/memory.py` |
| **Memory reads** - the vendor directory the broadcast address is resolved from: `resolve_counterparty()` in `agent/memory.py:319` | `agent/memory.py` |
| **Memory writes** - paid marker, pending work-claim, ALLOW/BLOCK records: `claim_intent()` / `record_paid()` / `record_blocked()` | `agent/memory.py:164`, `agent/guard.py:143` |
| **Memory writes** - bans, approvals, rules, directives, agent notes: `ban/approve_counterparty`, `set_rule`, `set_directive`, `journal_note` | `agent/memory.py:230-477` |
| The ablation that proves it (`--no-memory` / `AgentCtx(memory=None)`) | `agent/toolkit.py:248`, `agent/cli.py`, `agent/chat.py` |

## The deletion test (run it yourself)

```bash
# 1. ban a vendor, then watch a FRESH session refuse to pay it
python -m agent.chat                 # "ban 0x... alias evil-corp, they scammed us"  -> quit
python -m agent.chat                 # "pay 2 USDC to 0x... alias evil-corp for invoice-7"  -> BLOCKED, cites the ban

# 2. delete the memory and ask the exact same thing
python -m agent.cli wipe
python -m agent.chat --no-memory     # same payment request  -> PAYS (simulated; unguarded funds are never broadcast)
```

With memory the team refuses; without memory the same request sails through.
`tests/test_team.py::test_no_memory_pays_what_memory_blocked` asserts the
contrast, and `tests/test_guard.py::test_ablation_allows_double_pay` asserts
the double-pay variant.

## How memory made this possible

A shared SQL table could store the same rows. What it could not do is what
the build leans on: **temporal rule recall** (which cap was in force when the
obligation was incurred - two overlapping rules, judged correctly), **fuzzy
alias recall** (a banned vendor re-emerging under a new address is caught by
FTS5 over the counterparty trail, not by an exact key), and a **load-bearing
journal** that any teammate reads back before acting - the pending payment
claim is a work-claim primitive that closes the check->broadcast->record race
across processes. Those three are why the guard's refusals cite evidence a
judge can trace to a stored entity.

## Partner stack: Base (verified, load-bearing)

Every ALLOW ends in a real ERC-20 USDC transfer on Base Sepolia, signed and
broadcast by `agent/chain.py`, receipt-confirmed, and the tx hash is written
back into memory where the next session reads it to refuse replays. Three live
executed transactions:

- `0xa782a891...47441e` (Sep 3) - [BaseScan](https://sepolia.basescan.org/tx/0xa782a891ef381e6fe7a946adffca27294dd5300072d27309104fd877da47441e)
- `0x15274fda...8ba15c` (Sep 4, routed through the agent team's payments
  agent) - [BaseScan](https://sepolia.basescan.org/tx/0x15274fda7af3cf75bd3b98ed073208a8564fe78ee0ea4611439efcbda58ba15c)
- `0x7cf2cb70...f514c8a537` (Sep 4, an **x402** purchase: the payments agent
  bought a paywalled feed through the memory guard - the guard ran on the
  server's own 402 terms before anything was signed, and the replay was
  refused citing this tx) - [BaseScan](https://sepolia.basescan.org/tx/0x7cf2cb70f40b251281ce2626c1f104ebeb095045b113552a71ede2f514c8a537)

### Memory-gated x402 (the protocol-native double-pay)

x402 paywalls are the retry double-pay pattern in the wild: the server names
the price and the recipient, the agent signs, the facilitator settles. The
payments agent's `buy` tool (`agent/toolkit.py`) runs that flow through the
official `x402` SDK - but the memory guard sits *inside* the protocol, as a
before-payment hook (`agent/x402store.py`): the 402's own payTo + amount are
checked for replays, bans, and the rule cap before any signature exists. A
refusal aborts the signature, so nothing signable ever leaves the agent.
Without memory the agent signs whatever any paywall demands - the exact drain
shape of the Grok/Bankr incident, now structurally impossible.

Run the demo vendor locally (settles for real on Base Sepolia via the public
testnet facilitator):

```bash
python -m agent.x402server --port 8077 --pay-to 0x... --amount-usdc 0.01
python -m agent.chat   # "buy http://127.0.0.1:8077/feed with a 0.05 USDC budget"
```

Virtuals is deliberately not claimed: one fully verified stack beats a
decorative second one.

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
