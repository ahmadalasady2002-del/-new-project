"""Trading loop: manage open positions, then look for new buys.

Run:
  python -m bot.main            # run forever (paper money unless LIVE_TRADING=yes)
  python -m bot.main --once     # one cycle and exit
  python -m bot.main --report   # print balance and trade history
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

from . import config, data, strategy
from .broker import BybitBroker, PaperBroker

log = logging.getLogger("bot")


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(config.LOG_FILE, encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)


def load_state():
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"positions": {}, "trades": [], "cooldown": {}}


def save_state(state):
    tmp = config.STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(config.STATE_FILE)


def make_broker(state):
    mode = "live" if config.LIVE_TRADING else "paper"
    if state.setdefault("mode", mode) != mode:
        raise SystemExit(
            f"{config.STATE_FILE.name} belongs to {state['mode']} mode. "
            f"Rename or delete it before switching to {mode}."
        )
    if config.LIVE_TRADING:
        broker = BybitBroker(config.API_KEY, config.API_SECRET)
        broker.check_permissions()
        return broker
    return PaperBroker(state)


def equity(state, broker, px):
    held = sum(p["qty"] * px.get(s, p["entry"]) for s, p in state["positions"].items())
    return broker.cash() + held


def close_position(state, broker, symbol, price, why):
    pos = state["positions"][symbol]
    proceeds = broker.sell(symbol, pos["qty"], price)
    if broker.live and proceeds == 0:
        log.warning("%s too small to sell (dust), dropping it", symbol)
    pnl = proceeds - pos["cost"]
    state["trades"].append({
        "symbol": symbol, "opened": pos["opened"], "closed": int(time.time()),
        "entry": pos["entry"], "exit": price, "cost": round(pos["cost"], 4),
        "proceeds": round(proceeds, 4), "pnl": round(pnl, 4), "why": why, "setup": pos["reason"],
    })
    state["cooldown"][symbol] = int(time.time())
    del state["positions"][symbol]
    log.info("SELL %s @ %.6g  %s  pnl %+.2f USDT (%+.1f%%)", symbol, price, why, pnl, 100 * pnl / pos["cost"])


def manage_positions(state, broker, px):
    now = time.time()
    for symbol in list(state["positions"]):
        pos = state["positions"][symbol]
        price = px.get(symbol)
        if price is None:
            continue
        pos["highest"] = max(pos["highest"], price)
        # Once in profit by TRAIL_START_ATR, the stop follows the price up.
        if pos["highest"] - pos["entry"] >= config.TRAIL_START_ATR * pos["atr"]:
            pos["stop"] = max(pos["stop"], pos["entry"] * (1 + 2 * config.FEE_RATE),
                              pos["highest"] - config.STOP_ATR * pos["atr"])
        hours = (now - pos["opened"]) / 3600
        if price <= pos["stop"]:
            close_position(state, broker, symbol, price, "stop")
        elif hours >= config.MAX_HOLD_HOURS and price < pos["entry"] + pos["atr"]:
            close_position(state, broker, symbol, price, "time")


def risk_gate(state, eq):
    """Returns None if buying is allowed, otherwise the reason it isn't."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.setdefault("start_equity", eq)
    state["peak_equity"] = max(state.get("peak_equity", eq), eq)
    if state.get("day") != today:
        state["day"], state["day_start_equity"] = today, eq
    if state.get("halted"):
        return "halted"
    if eq <= state["peak_equity"] * (1 - config.MAX_DRAWDOWN):
        state["halted"] = True
        log.error("Equity fell %.0f%% from its peak. Bot stopped buying for good. "
                  "Delete \"halted\" from %s to resume.", 100 * config.MAX_DRAWDOWN, config.STATE_FILE.name)
        return "halted"
    if eq <= state["day_start_equity"] * (1 - config.DAILY_LOSS_LIMIT):
        return "daily loss limit"
    return None


def find_entries(state, broker, px, eq, tickers):
    slots = config.MAX_POSITIONS - len(state["positions"])
    if slots <= 0:
        return
    fng = data.fear_greed()
    regime = strategy.market_regime(data.klines("BTCUSDT", "4h", 120), fng)
    log.info("market: %s (fear&greed %s)", regime, fng)
    if regime == "off":
        return

    trending = data.trending_symbols()
    now = time.time()
    signals = []
    universe = data.build_universe(tickers, trending)
    for symbol in universe:
        if symbol in state["positions"]:
            continue
        if now - state["cooldown"].get(symbol, 0) < config.COOLDOWN_HOURS * 3600:
            continue
        try:
            sig = strategy.evaluate(symbol, data.klines(symbol), symbol[:-4] in trending)
        except Exception as e:
            log.warning("skip %s: %s", symbol, e)
            continue
        if sig:
            signals.append(sig)
    signals.sort(key=lambda s: s.score, reverse=True)
    log.info("scanned %d coins, %d signals%s", len(universe), len(signals),
             f" (best {signals[0].symbol}: {signals[0].reason})" if signals else "")

    size_mult = 0.5 if regime == "caution" else 1.0
    for sig in signals[:slots]:
        price = px.get(sig.symbol, sig.price)
        stop_dist = min(max(config.STOP_ATR * sig.atr / price, config.MIN_STOP_PCT), config.MAX_STOP_PCT)
        usdt = min(eq * config.RISK_PER_TRADE / stop_dist, eq * config.MAX_POSITION_PCT) * size_mult
        usdt = min(usdt, broker.cash() * 0.99)
        if usdt < config.MIN_ORDER_USDT:
            log.info("not enough cash for %s (%.2f USDT)", sig.symbol, usdt)
            break
        qty, cost = broker.buy(sig.symbol, usdt, price)
        if qty <= 0:
            continue
        entry = cost / qty
        state["positions"][sig.symbol] = {
            "qty": qty, "cost": cost, "entry": entry, "atr": sig.atr, "highest": entry,
            "stop": entry * (1 - stop_dist), "opened": int(now), "reason": sig.reason,
        }
        log.info("BUY  %s @ %.6g  %.2f USDT  stop %.6g  [%s]",
                 sig.symbol, entry, cost, entry * (1 - stop_dist), sig.reason)


def cycle(state, broker):
    tickers = data.tickers_24h()
    px = {t["symbol"]: float(t["lastPrice"]) for t in tickers}
    manage_positions(state, broker, px)
    eq = equity(state, broker, px)
    blocked = risk_gate(state, eq)
    if blocked:
        log.info("no new buys: %s", blocked)
    else:
        find_entries(state, broker, px, eq, tickers)
    eq = equity(state, broker, px)
    log.info("equity %.2f USDT | cash %.2f | open %s", eq, broker.cash(), ", ".join(state["positions"]) or "-")


def report(state):
    trades = state["trades"]
    wins = [t for t in trades if t["pnl"] > 0]
    total = sum(t["pnl"] for t in trades)
    print(f"mode: {state.get('mode', '?')}   start equity: {state.get('start_equity', 0):.2f} USDT")
    print(f"closed trades: {len(trades)}   wins: {len(wins)}   realized pnl: {total:+.2f} USDT")
    for s, p in state["positions"].items():
        print(f"  open {s}: entry {p['entry']:.6g}  stop {p['stop']:.6g}  cost {p['cost']:.2f}")
    for t in trades[-15:]:
        when = datetime.fromtimestamp(t["closed"], timezone.utc).strftime("%m-%d %H:%M")
        print(f"  {when} {t['symbol']:<12} {t['pnl']:+8.2f}  {t['why']:<5} {t['setup']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    state = load_state()
    if args.report:
        report(state)
        return

    setup_logging()
    broker = make_broker(state)
    log.info("started in %s mode", "LIVE (real money)" if broker.live else "paper")
    while True:
        try:
            cycle(state, broker)
        except Exception:
            log.exception("cycle failed, will retry")
        save_state(state)
        if args.once:
            break
        time.sleep(config.CYCLE_SECONDS)


if __name__ == "__main__":
    main()
