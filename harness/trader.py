#!/usr/bin/env python3
"""LLM Trading Study harness v2 — one decision cycle per invocation.

v2 changes (from cross-model audit 2026-08-09, GPT-4o + Gemini + Claude):
- Aggressive-leg buys place REAL standing exit orders (GTC take-profit limit
  sell + stop-limit sell) so exits execute between hourly cycles.
- Crypto entries use IOC limit orders at the ask (caps spread/slippage) instead
  of market orders.
- Orphaned exit orders (no matching position) are cancelled at cycle start.
- State now includes open orders and live bid/ask quotes.
- Bars are compressed to closing-price strings (cuts token cost ~70%).

v4 changes (2026-08-15, owner-authorized):
- Trailing stops now apply to BOTH legs, with per-leg activate/gap params read
  from config (legs.<leg>.trailing); v3 constants remain the fallback.
- State includes week_to_date_pnl and weekly_target_usd for pace discipline.

Usage:
    python harness/trader.py            # real cycle (needs .env keys)
    python harness/trader.py --mock     # plumbing test, no keys, no orders
"""
import argparse, json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def load_config():
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)

def load_prompt(cfg):
    version = cfg["llm"]["prompt_version"]
    return (ROOT / "prompts" / f"decision_prompt_{version}.md").read_text()

def append_jsonl(name, record):
    LOGS.mkdir(exist_ok=True)
    with open(LOGS / name, "a") as f:
        f.write(json.dumps(record) + "\n")

def recent_decisions(n):
    path = LOGS / "decisions.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()[-n:]
    return [json.loads(l) for l in lines]

def norm(sym):
    return sym.replace("/", "")

# Stop registry: Alpaca crypto allows only ONE standing sell per position (no
# OCO), so the take-profit lives on the exchange and stops live here, enforced
# mechanically at every cycle start.
EXITS = LOGS / "exits.json"

def load_exits():
    return json.loads(EXITS.read_text()) if EXITS.exists() else {}

def save_exits(d):
    LOGS.mkdir(exist_ok=True)
    EXITS.write_text(json.dumps(d, indent=2))

# ---------------------------------------------------------------- alpaca setup

def trading_client(cfg):
    from alpaca.trading.client import TradingClient
    return TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"],
                         paper=cfg["account"]["mode"] == "paper")

# ---------------------------------------------------------------- market state

def gather_state_alpaca(cfg):
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import (StockBarsRequest, CryptoBarsRequest, NewsRequest,
                                      StockLatestQuoteRequest, CryptoLatestQuoteRequest)
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.historical.news import NewsClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    key, secret = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    trading = trading_client(cfg)

    acct = trading.get_account()
    positions = [{
        "symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value),
        "avg_entry": float(p.avg_entry_price), "unrealized_pl": float(p.unrealized_pl),
        "unrealized_plpc": float(p.unrealized_plpc),
    } for p in trading.get_all_positions()]

    # cancel orphaned exit orders (sell orders with no matching position)
    held = {norm(p["symbol"]) for p in positions}
    open_orders, cancelled = [], []
    for o in trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)):
        rec = {"id": str(o.id), "symbol": o.symbol, "side": o.side.value,
               "type": o.order_type.value if o.order_type else None,
               "qty": float(o.qty) if o.qty else None,
               "notional": float(o.notional) if o.notional else None,
               "limit_price": float(o.limit_price) if o.limit_price else None,
               "stop_price": float(o.stop_price) if o.stop_price else None}
        if o.side.value == "sell" and norm(o.symbol) not in held:
            try:
                trading.cancel_order_by_id(o.id); cancelled.append(rec)
            except Exception:
                open_orders.append(rec)
        else:
            open_orders.append(rec)

    start_daily = datetime.now(timezone.utc) - timedelta(days=cfg["history"]["bars_lookback_days"])
    start_hourly = datetime.now(timezone.utc) - timedelta(hours=cfg["history"]["intraday_bars_hours"])

    def compress_daily(bars_by_symbol):
        return {s: " ".join(f"{b.timestamp.strftime('%m/%d')}:{round(b.close, 4)}" for b in bs)
                for s, bs in bars_by_symbol.items()}

    def compress_hourly(bars_by_symbol, keep=12):
        return {s: " ".join(f"{b.timestamp.strftime('%Hh')}:{round(b.close, 4)}" for b in bs[-keep:])
                for s, bs in bars_by_symbol.items()}

    stock_syms = cfg["legs"]["long"]["symbols"]
    crypto_syms = cfg["legs"]["aggressive"]["symbols"]

    sc = StockHistoricalDataClient(key, secret)
    cc = CryptoHistoricalDataClient(key, secret)
    stock_daily = sc.get_stock_bars(StockBarsRequest(symbol_or_symbols=stock_syms, timeframe=TimeFrame.Day, start=start_daily)).data
    stock_hourly = sc.get_stock_bars(StockBarsRequest(symbol_or_symbols=stock_syms, timeframe=TimeFrame.Hour, start=start_hourly)).data
    crypto_daily = cc.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=crypto_syms, timeframe=TimeFrame.Day, start=start_daily)).data
    crypto_hourly = cc.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=crypto_syms, timeframe=TimeFrame.Hour, start=start_hourly)).data

    quotes = {}
    try:
        for s, q in sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=stock_syms)).items():
            quotes[s] = {"bid": float(q.bid_price), "ask": float(q.ask_price)}
    except Exception:
        pass
    try:
        for s, q in cc.get_crypto_latest_quote(CryptoLatestQuoteRequest(symbol_or_symbols=crypto_syms)).items():
            quotes[s] = {"bid": float(q.bid_price), "ask": float(q.ask_price)}
    except Exception:
        pass

    try:
        news = NewsClient(key, secret).get_news(NewsRequest(limit=25)).data.get("news", [])
        headlines = [{"t": n.created_at.isoformat(timespec="minutes"), "headline": n.headline,
                      "symbols": n.symbols} for n in news]
    except Exception as e:
        headlines = [{"error": f"news unavailable: {e}"}]

    return {
        "timestamp": now_iso(),
        "account": {"equity": float(acct.equity), "cash": float(acct.cash),
                    "buying_power": float(acct.buying_power)},
        "positions": positions,
        "open_orders": open_orders,
        "cancelled_orphan_orders": cancelled,
        "quotes": quotes,
        "daily_closes": {**compress_daily(stock_daily), **compress_daily(crypto_daily)},
        "hourly_closes": {**compress_hourly(stock_hourly), **compress_hourly(crypto_hourly)},
        "news": headlines,
    }

def gather_state_mock(cfg):
    return {
        "timestamp": now_iso(),
        "account": {"equity": 10000.0, "cash": 10000.0, "buying_power": 10000.0},
        "positions": [], "open_orders": [], "cancelled_orphan_orders": [],
        "quotes": {"BTC/USD": {"bid": 65100.0, "ask": 65200.0}, "SPY": {"bid": 772.9, "ask": 773.1}},
        "daily_closes": {"SPY": "08/07:770.1 08/08:773.0", "BTC/USD": "08/07:64800 08/08:65150"},
        "hourly_closes": {"BTC/USD": "18h:65100 19h:65150"},
        "news": [{"t": "2026-08-09T12:00", "headline": "Mock headline", "symbols": ["SPY"]}],
    }

# ------------------------------------------------------------------- decisions

def leg_equity(cfg, state, leg):
    base = min(state["account"]["equity"], cfg["account"].get("study_capital", state["account"]["equity"]))
    return base * cfg["legs"][leg]["capital_fraction"]

def ask_llm(cfg, prompt, state, mock=False):
    if mock:
        return {"market_view": "Mock cycle.",
                "decisions": [
                    {"leg": "aggressive", "action": "buy", "symbol": "BTC/USD", "notional_usd": 600,
                     "take_profit_price": 66500, "stop_price": 64200,
                     "rationale": "Mock buy to exercise order path.", "confidence": 0.6},
                    {"leg": "long", "action": "hold", "symbol": None, "notional_usd": None,
                     "take_profit_price": None, "stop_price": None,
                     "rationale": "Mock hold.", "confidence": 0.9}]}
    import anthropic
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    limits = {}
    for leg, legcfg in cfg["legs"].items():
        eq = leg_equity(cfg, state, leg)
        exposure = sum(p["market_value"] for p in state["positions"]
                       if norm(p["symbol"]) in [norm(s) for s in legcfg["symbols"]])
        limits[leg] = {
            "objective": legcfg["objective"], "whitelist": legcfg["symbols"],
            "leg_budget_usd": round(eq, 2), "current_exposure_usd": round(exposure, 2),
            "max_single_order_usd": round(eq * legcfg["max_trade_pct"], 2),
            "max_per_position_usd": round(eq * legcfg["max_position_pct"], 2),
            "note": "Size ALL orders off these dollar caps, not raw account equity."}
    msg = client.messages.create(
        model=cfg["llm"]["model"], max_tokens=cfg["llm"]["max_tokens"],
        system=prompt,
        messages=[{"role": "user", "content":
                   f"STATE:\n{json.dumps(state, default=str)}\n\nRISK_LIMITS:\n{json.dumps(limits)}\n\n"
                   f"RECENT_DECISIONS:\n{json.dumps(recent_decisions(cfg['history']['recent_decisions_shown']))}\n\n"
                   "Respond with the decision JSON only."}])
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    return json.loads(text)

# ---------------------------------------------------------------- risk + orders

def validate(cfg, state, d):
    """Return (ok, reason). Harness-enforced; the model cannot override these."""
    if d["action"] == "hold":
        return True, "hold"
    legcfg = cfg["legs"].get(d["leg"])
    if not legcfg:
        return False, f"unknown leg {d['leg']}"
    if d["symbol"] not in legcfg["symbols"]:
        return False, f"{d['symbol']} not on {d['leg']} whitelist"
    if d["action"] == "buy":
        # Traffic-collapse screen (docs/research/2026-08-23-traffic-signal-study.md):
        # no NEW long entries in names whose organic search traffic is down >=30% YoY.
        # Fail-open: a missing or unreadable screen file never blocks trading.
        if d["leg"] == "long":
            try:
                scr = json.loads((ROOT / "data" / "traffic_screen.json").read_text())
                if d["symbol"] in scr.get("blocked", []):
                    return False, (f"traffic-collapse screen blocks {d['symbol']} "
                                   f"(organic traffic <=-30% YoY, asof {scr.get('asof')})")
            except Exception:
                pass
        eq = leg_equity(cfg, state, d["leg"])
        if not d.get("notional_usd") or d["notional_usd"] <= 0:
            return False, "buy without positive notional"
        if d["notional_usd"] > eq * legcfg["max_trade_pct"]:
            return False, f"notional {d['notional_usd']} > max_trade_pct cap {eq * legcfg['max_trade_pct']:.2f}"
        held = sum(p["market_value"] for p in state["positions"] if norm(p["symbol"]) == norm(d["symbol"]))
        if held + d["notional_usd"] > eq * legcfg["max_position_pct"]:
            return False, "would exceed max_position_pct cap"
        if not d.get("stop_price"):
            return False, "buy missing stop_price"
        if d["leg"] == "aggressive" and not d.get("take_profit_price"):
            return False, "aggressive buy missing take_profit_price"
    return True, "ok"

def rnd_price(p):
    return round(p, 4 if p < 10 else 2)

def place_order(cfg, state, d, mock=False):
    if mock:
        return {"status": "mock", "detail": "order not sent"}
    from alpaca.trading.requests import (MarketOrderRequest, LimitOrderRequest,
                                         StopLimitOrderRequest, GetOrdersRequest)
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    trading = trading_client(cfg)
    is_crypto = "/" in d["symbol"]

    if d["action"] == "sell":
        # cancel standing exit orders for this symbol first, then close/sell
        try:
            for o in trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)):
                if norm(o.symbol) == norm(d["symbol"]):
                    trading.cancel_order_by_id(o.id)
            time.sleep(1)
        except Exception:
            pass
        try:
            if d.get("notional_usd"):
                req = MarketOrderRequest(symbol=d["symbol"], notional=round(d["notional_usd"], 2),
                                         side=OrderSide.SELL,
                                         time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY)
                order = trading.submit_order(req)
                return {"status": "submitted", "order_id": str(order.id)}
            trading.close_position(norm(d["symbol"]))
            return {"status": "submitted", "detail": "position closed"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    # BUY
    try:
        if is_crypto:
            ask = state.get("quotes", {}).get(d["symbol"], {}).get("ask")
            if not ask:
                return {"status": "error", "detail": "no ask quote for limit entry"}
            limit = rnd_price(ask * 1.0015)  # marketable limit: caps slippage at ~15bps past ask
            qty = int(d["notional_usd"] / limit * 1e6) / 1e6
            entry = trading.submit_order(LimitOrderRequest(
                symbol=d["symbol"], qty=qty, side=OrderSide.BUY,
                time_in_force=TimeInForce.IOC, limit_price=limit))
            time.sleep(2)
            entry = trading.get_order_by_id(entry.id)
            filled = float(entry.filled_qty or 0)
            result = {"status": "submitted", "order_id": str(entry.id),
                      "entry_type": f"IOC limit @ {limit}", "filled_qty": filled}
            if filled > 0:
                exits = {}
                try:
                    tp = trading.submit_order(LimitOrderRequest(
                        symbol=d["symbol"], qty=filled, side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC, limit_price=rnd_price(d["take_profit_price"])))
                    exits["take_profit_order"] = str(tp.id)
                except Exception as e:
                    exits["take_profit_error"] = str(e)
                # stop lives in the registry; enforced (with trailing) each cycle
                reg = load_exits()
                reg[norm(d["symbol"])] = {"stop": rnd_price(d["stop_price"]),
                                          "tp": rnd_price(d["take_profit_price"]),
                                          "leg": "aggressive", "peak": None}
                save_exits(reg)
                exits["stop_registered"] = rnd_price(d["stop_price"])
                result["exits"] = exits
            else:
                result["status"] = "unfilled"
            return result
        else:
            req = MarketOrderRequest(symbol=d["symbol"], notional=round(d["notional_usd"], 2),
                                     side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            order = trading.submit_order(req)
            reg = load_exits()
            reg[norm(d["symbol"])] = {"stop": rnd_price(d["stop_price"]),
                                      "tp": rnd_price(d["take_profit_price"]) if d.get("take_profit_price") else None,
                                      "leg": "long", "peak": None}
            save_exits(reg)
            return {"status": "submitted", "order_id": str(order.id),
                    "stop_registered": rnd_price(d["stop_price"])}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

TRAIL_ACTIVATE = 1.04   # default: trailing kicks in at +4% over entry (v3, committee)
TRAIL_GAP = 0.98        # default: stop ratchets to peak - 2%

def trail_params(cfg, leg):
    """Per-leg trailing overrides from config (v4); falls back to v3 defaults."""
    t = cfg["legs"].get(leg, {}).get("trailing") or {}
    return 1 + t.get("activate_pct", TRAIL_ACTIVATE - 1), 1 - t.get("gap_pct", 1 - TRAIL_GAP)

def enforce_stops(cfg, state):
    """Cycle-start exit enforcement: hard stops, trailing stops (per-leg
    params), and registry-based TPs for stocks. Mutates state so the model sees
    the post-exit book. Returns exit records."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    reg = load_exits()
    if not reg:
        return []
    trading = trading_client(cfg)
    crypto_norms = {norm(s) for s in cfg["legs"]["aggressive"]["symbols"]}
    held = {norm(p["symbol"]): p for p in state["positions"]}
    for sym in [s for s in reg if s not in held]:
        del reg[sym]   # position gone (TP filled or sold) -> registry pruned
    fired = []

    def close(sym, quote_sym, plan, bid, reason):
        try:
            for o in trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)):
                if norm(o.symbol) == sym:
                    trading.cancel_order_by_id(o.id)
            time.sleep(1)
            trading.close_position(sym)
            fired.append({"symbol": quote_sym, "reason": reason, "level": plan.get("stop"),
                          "bid": bid, "status": "closed"})
            state["positions"] = [p for p in state["positions"] if norm(p["symbol"]) != sym]
            del reg[sym]
        except Exception as e:
            fired.append({"symbol": quote_sym, "reason": reason, "bid": bid, "status": f"error: {e}"})

    for sym, plan in list(reg.items()):
        is_crypto = sym in crypto_norms
        quote_sym = (sym[:-3] + "/" + sym[-3:]) if is_crypto else sym
        bid = state.get("quotes", {}).get(quote_sym, {}).get("bid")
        if not bid:
            continue   # no live quote (e.g. stock market closed) -> check next cycle
        entry = held[sym]["avg_entry"]
        peak = max(plan.get("peak") or entry, bid)
        plan["peak"] = peak
        leg = plan.get("leg", "aggressive" if is_crypto else "long")
        act, gap = trail_params(cfg, leg)   # v4: trailing on BOTH legs, per-leg params
        if bid >= entry * act:
            new_stop = rnd_price(peak * gap)
            if new_stop > plan["stop"]:
                plan["stop"] = new_stop   # ratchet only, never loosens
        if bid <= plan["stop"]:
            close(sym, quote_sym, plan, bid, "stop")
        elif leg == "long" and plan.get("tp") and bid >= plan["tp"]:
            close(sym, quote_sym, plan, bid, "take_profit")
    save_exits(reg)
    if fired:
        state["harness_stop_exits_this_cycle"] = fired
    return fired

# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="no keys, no orders — plumbing test")
    args = ap.parse_args()

    cfg = load_config()
    prompt = load_prompt(cfg)
    state = gather_state_mock(cfg) if args.mock else gather_state_alpaca(cfg)
    pfx = "mock_" if args.mock else ""   # mock runs never touch the research logs
    stop_exits = [] if args.mock else enforce_stops(cfg, state)

    # v4: weekly pace context — equity at the start of the current ISO week
    try:
        cur_week = datetime.fromisoformat(state["timestamp"]).isocalendar()[:2]
        week_start_eq = None
        with open(ROOT / "logs" / "equity.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if datetime.fromisoformat(rec["t"]).isocalendar()[:2] == cur_week:
                    week_start_eq = rec["equity"]; break
        if week_start_eq is not None:
            state["week_to_date_pnl"] = round(state["account"]["equity"] - week_start_eq, 2)
        state["weekly_target_usd"] = cfg.get("weekly", {}).get("target_usd")
    except Exception:
        pass   # pace context is best-effort; never blocks a cycle

    append_jsonl(pfx + "equity.jsonl", {"t": state["timestamp"], "equity": state["account"]["equity"],
                                  "cash": state["account"]["cash"],
                                  "positions": len(state["positions"])})

    decision = ask_llm(cfg, prompt, state, mock=args.mock)

    results, orders_placed = [], 0
    for d in decision.get("decisions", []):
        ok, reason = validate(cfg, state, d)
        if ok and d["action"] != "hold":
            if orders_placed >= cfg["risk"]["max_orders_per_run"]:
                ok, reason = False, "max_orders_per_run reached"
        result = place_order(cfg, state, d, mock=args.mock) if ok and d["action"] != "hold" else {"status": "skipped", "detail": reason}
        if result.get("status") in ("submitted", "mock"):
            orders_placed += 1
        results.append({"decision": d, "risk_check": reason, "execution": result})

    record = {"t": state["timestamp"], "prompt_version": cfg["llm"]["prompt_version"],
              "model": cfg["llm"]["model"], "mode": "mock" if args.mock else cfg["account"]["mode"],
              "harness_stop_exits": stop_exits,
              "market_view": decision.get("market_view"), "results": results}
    append_jsonl(pfx + "decisions.jsonl", record)
    print(json.dumps(record, indent=2))

if __name__ == "__main__":
    main()
