# Semrush Traffic Signal Study — Results & Recommendation

**Date:** 2026-08-23 · **Verdict: the mechanism is real; the tradable edge, as tested, is not there. Don't launch a traffic book yet — use the data as a screen and start archiving vintages so a real test becomes possible.**

## What we built

A 71-ticker universe of traffic-dependent US-listed companies (5 research agents across sectors, judge-ranked into tiers, plus additions from a completeness critic: GoodRx, LegalZoom, Chegg, Groupon, eHealth, and others). For each: full monthly organic-search-traffic history 2012→July 2026 from Semrush (139 domains, summed per company — e.g. Expedia = expedia.com + hotels.com + vrbo.com + travelocity + orbitz), quarterly revenue with filing dates from SEC EDGAR (64 companies), and daily prices from Alpaca (2015→now).

Note on data scope: your Semrush plan includes the SEO-side monthly *organic search* traffic, not the Trends total-visits product (that's a separate tier). Organic-only is a partial view — it misses direct, app, and paid demand.

## Results

**The mechanism works — for the right companies.** Same-quarter traffic growth vs revenue growth, 1,579 company-quarters: pooled correlation +0.15, but for pure-play web businesses it is strong — Wayfair 0.76, Chewy 0.72, DoorDash 0.70, Angi 0.68, Coursera 0.66, Carvana 0.63. For app-heavy or B2B-mixed names it's zero to negative (Uber −0.53). Traffic genuinely nowcasts revenue where the funnel runs through the website. The universe design was right.

**The market already knows.** Every attempt to turn the nowcast into returns came back empty:

| Test | Result |
|---|---|
| Monthly long/short on traffic YoY (2016–2026, 126 months, ~51 names/mo) | IC −0.007 (t = −0.45) — no ranking power |
| Same, tier-A only / pure-play only | IC ≈ 0 both |
| Pre-announcement window (signal known weeks before earnings) | corr 0.003–0.05; quintile spread ≤0.8%, not significant |
| Post-earnings 21-day drift | corr 0.016 — nothing |

The raw quintile spread (1.55%/mo) looks tempting but has no statistical support (t = 1.36) and no IC behind it — it's volatile-small-cap noise, exactly the pattern the 2026-08-22 strategy validation taught us to distrust.

**One usable remnant: the collapse screen.** Companies whose organic traffic is down ≥30% YoY underperform over the next 3 months: median abnormal return −6.3% vs −4.1% baseline, mean gap ~4.5pp, 61% negative. Skewed distribution — outright shorting them invites squeezes — but as an *avoid* filter for the long book it has modest, real value. Chegg's slow bleed is the canonical case, and the screen still flags it (traffic −14% to −22% YoY through 2026).

## Why the honest caveats matter

Semrush history is restated by today's estimation model — not what an investor saw at the time — so even these null results are optimistic-case; a real-time signal would likely test worse. The universe is today's survivors (no Farfetch, Wish, Groupon-at-peak short-side wins). And announcement timing was proxied by 10-Q filing dates. None of these caveats rescue the strategy; all of them cut against it.

## Recommendation

1. **No traffic book.** The core long/short idea doesn't clear the bar even on flattering data.
2. **Archive vintages now.** Pull the trailing-month snapshot for all 139 domains monthly and commit it. In 6–12 months you'd own the point-in-time dataset that makes a genuine test possible — the thing no restated backtest can fake. Cost: ~zero.
3. **Wire the collapse screen into the long leg.** A one-line rule — no new longs in names with organic traffic down ≥30% YoY — costs nothing and uses the subscription for the one thing it demonstrably flags.
4. **Skip the Trends upgrade** unless a vintage-based test someday shows real-time edge worth paying for.

*Scope: ~30 research agents (~1.3M tokens, covered by plan), 139 Semrush pulls, 1,600+ earnings events, 126 monthly cross-sections. Paper study — no orders placed, no study files modified.*
