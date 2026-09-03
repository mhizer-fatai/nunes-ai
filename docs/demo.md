# Nunes AI demo

The four-beat safety primitive and the three proofs that matter for the judges.

## Four beats

Every payment runs: **recall -> decide -> execute -> journal**.

`python -m agent.cli demo` runs all four beats on a throwaway db with simulated settlement:

| Beat | What | Expect |
| --- | --- | --- |
| 1a | Session 1 pays inv-900 (5 USDC, incurred 3 days ago) | `[ALLOW]`, tx journaled |
| 1b | A genuinely fresh session replays inv-900 | `[BLOCK]` double-spend refused (cites tx) |
| 2 | Banned vendor re-emerges under a NEW address + same alias | `[BLOCK]` via FTS5 alias recall |
| 3 | 50 USDC incurred Aug 25 | `[ALLOW]` under rule v1 (cap 100 USDC) |
| 4 | 50 USDC incurred Sep 1 | `[BLOCK]` under rule v2 (cap 10 USDC) |

Beat 1b is the **fresh-session recall** moment; beats 3/4 answer "isn't this just a
UNIQUE index?" (temporal recall). Beat 2 answers the same question with fuzzy recall.

## Three-process fresh-session + ablation proof

Run these three commands in three separate terminal processes (they share one db):

```powershell
$db = Join-Path $env:TEMP "nunes-ai-proof.db"

# P1 - seed rule, then pay (expect ALLOW)
python -m agent.cli --db $db set-rule --version v1 --effective-from 2026-08-01T00:00:00.000Z --max-amount 100
python -m agent.cli --db $db pay --intent inv-900 --to 0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3B --amount 5

# P2 - fresh process, same db, replays inv-900 (expect BLOCK double-spend)
python -m agent.cli --db $db pay --intent inv-900 --to 0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3B --amount 5

# P3 - --no-memory ablation (expect ALLOW again = the double-pay)
python -m agent.cli --no-memory pay --intent inv-900 --to 0x8f42b6a2C9d5F2A1b7C3e5D9F0a2b6C4D8e1F2a3B --amount 5
```

## Real onchain settlement

Fill `.env` and send a real Base Sepolia USDC transfer:

```powershell
$env:BASE_RPC_URL  = "https://sepolia.base.org"
$env:BASE_PRIVATE_KEY = "<funded key>"
$env:NUNES_AI_SIMULATE = "0"
python -m agent.cli pay --intent inv-live-001 --to <payee> --amount 5
```

Every `[ALLOW]` now returns a real tx hash, written into the COLD journal and read back
by later sessions to refuse replays.

## Utilities

```powershell
python -m agent.cli ban      --address 0x7b8B... --aliases data-feed.io --reason "drain attempt"
python -m agent.cli approve  --address 0x8f42... --note "trusted vendor"
python -m agent.cli set-rule --version v2 --effective-from 2026-09-01T00:00:00.000Z --max-amount 10
python -m agent.cli rules
python -m agent.cli search data-feed
python -m agent.cli events
```

## Tests

```powershell
python -m pytest tests -q   # 4 passed: idempotency, alias ban, temporal, ablation
```
