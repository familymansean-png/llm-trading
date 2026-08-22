# Strategy Validation Study — 2026-08-22

Two multi-agent validation studies run 2026-08-22 (39 agents total, ~2.5M tokens, independent adversarial verification on all headline claims). Full result files retained in the research session; this file records what the study concluded and what it changes about the live study.

## Study 1: Gap continuation day-trade (owner hypothesis)

Hypothesis: if pre-open futures move ±1%, buy the 3x leveraged ETF in that direction; variants with quick take-profit and hard stop.

Verdict: **no edge — do not build.** An initially positive backtest (+0.2–0.4%/event with TP+stop) was traced by adversarial re-implementation to a session-timezone bug: fixed-UTC session windows entered trades on the 8:30 AM ET *pre-market* bar during winter months (~40% of trading days), capturing prices no live order could get. Corrected DST-aware engine: pooled SPY+QQQ, 255 events, mean −0.08%/event net, t=−0.64, p=0.53. Published literature agrees (large index gaps fade early-session; Grant/Wolf/Yu 2005, Stübinger & Schneider 2019; ORB results die at ~2c/share slippage in replication).

Process consequence: all backtests now run on a shared, self-testing engine with DST-aware sessions (`America/New_York`), split/dividend-adjusted daily data, and verified first-bar volume sanity checks.

## Study 2: Ten published strategies, full battery

Faithful long-only replications, IS through 2022-12-31 / OOS 2023-01-01+, realistic next-open execution, friction stress, parameter perturbation, bootstrap significance with multiple-testing haircuts, correlation/portfolio fit, capital math, and three independent skeptic re-implementations (reproduced to ~4 decimals).

Strategies tested: Faber 10-mo SMA timing (2007), Antonacci dual momentum (2014), Moskowitz time-series momentum (2012), George & Hwang 52-wk high (2004), turn-of-the-month (Lakonishok & Smidt 1988), overnight drift (Lou/Polk/Skouras 2019), intraday momentum (Gao et al. 2018), volatility-managed portfolios (Moreira & Muir 2017), low-vol anomaly (Baker et al. 2011), crypto momentum (Liu & Tsyvinski 2021).

Verdict: **0 of 10 beat their fair benchmark OOS 2023–2026.** All ten OOS excess t-stats negative (−2.59 to −0.21). All replicate gross/in-sample — the anomalies existed; net of friction against fair benchmarks in the recent window, none survives. Overnight drift is real (gross Sharpe 1.3–1.5) but breaks even at 2–4 bps/side × 250 round-trips/yr. Intraday momentum is dead 2022–2026. Crypto momentum's lone "benchmark beat" (BTC 4-wk timing) was refuted by a skeptic: a silently truncated final week (BTC +24.6%) accounted for the entire edge.

### Finding that changes the live study

The long leg's 20d-momentum rule backtests at +40%/yr OOS on its universe — but **84.5% of those gains come from NVDA/TQQQ/MSTR, names in the universe because they had already won** (universe assembled 2026). Without them the rule trails SPY. Even with them, equal-weight of the same 15 names beats the rule risk-adjusted: Sharpe 1.85 vs 1.27, smaller drawdown. The universe is the strategy; the signal currently subtracts risk-adjusted value.

Action taken: `baselines.json` now carries `universe_ew_benchmark` (per-symbol raw 2026-08-07 closes). The daily report compares the long leg against EW of its own universe, not only SPY. Any future universe edit is a strategy decision and should be logged as such.

### What survived

Drawdown control, not alpha. Faber trend timing, dual momentum, and vol-managed scaling all roughly halve max drawdown at some return cost; the 2023–26 OOS window was a bull with nothing to dodge, which is exactly when these look worst. Portfolio fit: a trend-following sleeve is 0.11–0.29 correlated to the existing legs; adding it lifted the blended OOS Sharpe 1.37→1.65 and cut maxDD −21.8%→−7.6%. See `leg3-trend-sleeve-spec.md`.

### Capital math for the $2k/week goal

$104k/yr requires ≈$550–800k at OOS bull-window mean returns; ≈$1M after a standard 50% live-degradation haircut (Bailey/López de Prado); $1.6–2.6M to survive a mean−1σ year without eating principal. Expect ~21 negative weeks/yr; weekly P&L σ ≈ 4× the target at mean-sized capital. Reference: plain SPY needed $468k in this same exceptional window. The binding constraint is capital and drawdown tolerance, not signal quality.

## Standing process rule

No strategy touches the harness without passing: verified-engine backtest → IS/OOS split → friction/execution stress → parameter perturbation → independent skeptic re-implementation. Two ideas entered this gauntlet on 2026-08-22; both initially looked good; zero survived.
