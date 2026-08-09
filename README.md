# LLM Trading Study — Harness

Research harness testing whether an LLM can manage a real brokerage account.
Two legs, one Alpaca account: **aggressive** (crypto, 24/7, targeting 1–3% net
per trade) and **long** (equities/ETFs, targeting ~10% annualized). Paper mode
first; promote to live by funding the same Alpaca account and flipping
`account.mode` in `config.yaml`.

## Architecture

Every hour a scheduled Cowork task clones this repo and runs `./run.sh`:

1. `trader.py` pulls account, positions, bars (daily + hourly), and news from
   Alpaca's free data API — $0 fixed data cost, deliberately.
2. It assembles the **frozen decision prompt** (`prompts/decision_prompt_v1.md`)
   plus a JSON state block and calls the Claude API. The prompt is a versioned
   research artifact: never edited, only superseded (v2, v3…) with the version
   stamped on every decision log line.
3. The model returns structured JSON decisions. The harness — not the model —
   enforces risk limits (whitelist, per-trade and per-position caps, order
   count). Violations are logged and skipped, not negotiated.
4. Orders go to Alpaca; the decision, risk verdict, and execution result are
   appended to `logs/decisions.jsonl`; equity snapshots to `logs/equity.jsonl`.
5. The run commits the logs back to the repo — the full audit trail for the
   paper is the git history itself.

## Setup (one time)

1. Open an Alpaca account (alpaca.markets) — this gives paper trading
   immediately and is the same account you later fund by ACH for live.
2. Generate **paper** API keys; copy `.env.example` to `.env` and fill in.
3. Add an Anthropic API key to `.env`.
4. `pip install -r requirements.txt`
5. Test: `python3 harness/trader.py --mock` (no keys needed), then a real
   paper cycle: `./run.sh`

## Cost discipline

Fixed costs are drag: $100/mo of data subscriptions is ~12%/yr on a $10k
account — an impossible handicap. Stack is therefore free Alpaca data + free
Alpaca/Benzinga news + Claude Sonnet at hourly cadence (~$10–30/mo tokens).
Upgrade data only if the paper needs it.

## Study notes

- Benchmark the long leg against SPY buy-and-hold over the same window.
- Paper phase doubles as plumbing validation AND a baseline chapter.
- `logs/*.jsonl` is append-only; never rewrite history.
