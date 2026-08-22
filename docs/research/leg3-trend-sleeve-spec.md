# Leg 3 Spec — Mechanical Trend Sleeve ("trend")

Status: DRAFT for owner review — not yet wired into the harness.
Origin: 2026-08-22 strategy validation (see 2026-08-22-strategy-validation.md). Purpose is **drawdown control and diversification**, not alpha: blend math showed adding this sleeve to the two existing legs lifted OOS Sharpe 1.37→1.65 and cut maxDD −21.8%→−7.6% (2022-09..2026-08). Expect it to LAG in bull tapes; its value shows in bears. Judge it on blended portfolio Sharpe/maxDD, never on standalone return.

## Rule (Faber 2007, unmodified)

- Universe: SPY, QQQ, IWM, EFA, TLT, GLD, XLE, XLV (8 sleeves, equal capital each).
- On the LAST TRADING DAY of each month, at/after 15:45 ET: for each asset, if last price > 10-month SMA of month-end closes → hold; else → cash (BIL or true cash).
- That is the entire rule. No LLM discretion, no overrides, no intramonth trades. Rebalance only on month-end signal changes (~3 trades/month average).

## Execution

- One scheduled run on the last trading day of each month (the existing 4x/hour cadence covers this; the run nearest 15:45 ET executes).
- Plain market orders are fine — the strategy is insensitive to minutes of slip (verified in robustness testing).
- Capital: 20% of study capital, taken pro-rata from the long leg's fraction (long 0.75 → 0.55, trend 0.20, aggressive 0.25 unchanged). Owner to confirm.
- Exits are mechanical by definition; no harness trailing needed. daily_loss_halt does not apply (positions are index/sector ETFs held on a monthly clock).

## Data & signal integrity

- 10-month SMA computed from month-end closes of SPLIT/DIVIDEND-ADJUSTED bars (Alpaca `adjustment=all`). Using raw closes will fire false signals around ex-div dates on TLT/XLE/XLV.
- Signal uses only completed month-end closes plus the live price on signal day; no intramonth peeking.

## Success criteria (evaluate after 3 months, decide at 6)

- Blended portfolio (all 3 legs) maxDD and Sharpe vs the 2-leg counterfactual (compute both from equity.jsonl; log trend sleeve fills tagged leg="trend").
- Kill criteria: implementation errors (any non-month-end trade, any discretionary override) → fix or kill immediately. Performance alone is NOT a kill criterion inside 6 months — a trend sleeve lagging in a bull market is behaving as designed.

## Phase 2 (separate decision): mechanical twins

To answer the study's core question — does the LLM add value over its own skeleton? — run each LLM leg against a mechanical twin with identical universe/caps and zero discretion:
- Long-leg twin: equal-weight of the 15-name universe, monthly rebalance (the benchmark that beat the 20d rule 1.85 vs 1.27 Sharpe OOS).
- Aggressive-leg twin: 100% cash + BTC-only 4-week momentum timing (the closest mechanical analog to its current behavior).
Twins can be tracked virtually (computed in the daily report from prices, no orders) to avoid splitting capital further. 8–12 weeks of live divergence gives the paper its headline result either way.
