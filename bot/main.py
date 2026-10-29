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
import threading
import time
from datetime import datetime, timezone

from . import config, data, lotto, notify, strategy
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
    hours = (time.time() - pos["opened"]) / 3600
    if why == "manual":
        reason = "بعتها بطلبك من تلگرام"
    elif pos.get("ann") and why in ANN_REASONS:
        reason = ANN_REASONS[why]
    elif pos.get("lotto") and why in LOTTO_REASONS:
        reason = LOTTO_REASONS[why]
    elif why == "time":
        reason = f"ما تحركت خلال {hours:.0f} ساعة"
    elif pnl > 0:
        reason = "السعر بدا ينزل من القمة، فبعت وحفظت الربح"
    else:
        reason = "السعر نزل، فبعت حتى ما تكبر الخسارة"
    if abs(pnl) < pos["cost"] * 0.005:
        head = f"⚪ بعت {symbol[:-4]} بدون ربح ولا خسارة"
        if why != "time":
            reason = "السعر رجع لنفس سعر الشراء، فبعت"
    else:
        head = (f"{'🟢 ربح' if pnl > 0 else '🔴 خسارة'}: بعت {symbol[:-4]}\n"
                f"{'ربحت' if pnl > 0 else 'خسرت'} {abs(pnl):.2f}$ ({100 * pnl / pos['cost']:+.1f}%)")
    extra = "\nوالربح اللي قبضته قبل من هاي العملة محفوظ 💰" if pos.get("tp_done") or pos.get("ladder") else ""
    notify.send(f"{head}\nالسبب: {reason}{extra}")


LOTTO_REASONS = {
    "stop": f"نزلت {100 * config.LOTTO_STOP:.0f}%، فهاي التذكرة خسرت 🎟",
    "trail": f"نزلت {100 * config.LOTTO_TRAIL:.0f}% من أعلى سعر وصلته، فبعت الباقي",
    "time": f"مرت {config.MAX_HOLD_HOURS / 24:.0f} يوم وما انفجرت",
}


ANN_REASONS = {
    "trail": f"قفزت وبعدين رجعت {100 * config.ANN_TRAIL:.0f}% من أعلى سعر، فبعت",
    "stop": f"نزلت {100 * config.ANN_STOP:.0f}% بدل ما تصعد، فبعت",
    "time": f"مرت {config.ANN_MAX_HOURS:.0f} ساعات على الخبر، فبعت",
}


def partial_sell(state, broker, symbol, price, share, why):
    """Sell `share` of a position and keep the rest open. Returns the profit, or None if too small."""
    pos = state["positions"][symbol]
    proceeds = broker.sell(symbol, pos["qty"] * share, price)
    if proceeds == 0:
        return None
    cost = pos["cost"] * share
    state["trades"].append({
        "symbol": symbol, "opened": pos["opened"], "closed": int(time.time()),
        "entry": pos["entry"], "exit": price, "cost": round(cost, 4),
        "proceeds": round(proceeds, 4), "pnl": round(proceeds - cost, 4), "why": why, "setup": pos["reason"],
    })
    pos["qty"] *= 1 - share
    pos["cost"] -= cost
    log.info("PART %s @ %.6g  sold %.0f%%  %s  pnl %+.2f USDT", symbol, price, 100 * share, why, proceeds - cost)
    return proceeds - cost


def take_profit(state, broker, symbol, price):
    """Sell part of a winner to lock the gain, and make the rest risk-free."""
    pos = state["positions"][symbol]
    pos["tp_done"] = True
    profit = partial_sell(state, broker, symbol, price, config.TAKE_PROFIT_SHARE, "tp")
    if profit is None:
        return  # too small to split; the trailing stop handles the whole position
    pos["stop"] = max(pos["stop"], pos["entry"] * (1 + 2 * config.FEE_RATE))
    notify.send(f"💰 قبضت ربح من {symbol[:-4]}\n"
                f"بعت نصها وربحت {profit:.2f}$\n"
                f"النص الباقي هسه ما يخسر، وإذا كملت تصعد نربح وياها")


def manage_lotto(state, broker, symbol, price, now):
    pos = state["positions"][symbol]
    candle = {"open": price, "high": price, "low": price, "close": price}
    for share, fill, why in lotto.exits(pos, candle, now):
        if share >= 1:
            close_position(state, broker, symbol, fill, why)
            return
        profit = partial_sell(state, broker, symbol, fill, share, why)
        if profit is not None:
            notify.send(f"🎉 {symbol[:-4]} صارت {why[1:]} أضعاف!\n"
                        f"بعت {100 * share:.0f}% منها وربحت {profit:.2f}$\n"
                        f"والباقي خليته يركض")


def manage_positions(state, broker, px):
    now = time.time()
    for symbol in list(state["positions"]):
        pos = state["positions"][symbol]
        price = px.get(symbol)
        if price is None:
            continue
        if pos.get("ann"):
            continue  # the announcement watcher manages these every few seconds
        if pos.get("lotto"):
            manage_lotto(state, broker, symbol, price, now)
            continue
        pos["highest"] = max(pos["highest"], price)
        if (config.TAKE_PROFIT_PCT and not pos.get("tp_done")
                and price >= pos["entry"] * (1 + config.TAKE_PROFIT_PCT)):
            take_profit(state, broker, symbol, price)
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
    if state.get("paused"):
        return "paused from Telegram"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.setdefault("start_equity", eq)
    state["peak_equity"] = max(state.get("peak_equity", eq), eq)
    if state.get("day") != today:
        if state.get("day"):
            change = eq - state["day_start_equity"]
            today_trades = [t for t in state["trades"]
                            if datetime.fromtimestamp(t["closed"], timezone.utc).strftime("%Y-%m-%d") == state["day"]]
            if abs(change) < 0.01:
                result = "⚪ ما تغير شي"
            else:
                result = (f"{'📈 ربحنا' if change > 0 else '📉 خسرنا'} {abs(change):.2f}$ "
                          f"({change / state['day_start_equity']:+.1%})")
            notify.send(f"📊 ملخص يوم أمس\n{result}\n"
                        f"💵 الرصيد هسه: {eq:.2f}$\n"
                        f"🔁 صفقات انسدت: {len(today_trades)}\n"
                        f"⏳ عملات ماسكها هسه: {len(state['positions'])}")
        state["day"], state["day_start_equity"] = today, eq
    if state.get("halted"):
        return "halted"
    if eq <= state["peak_equity"] * (1 - config.MAX_DRAWDOWN):
        state["halted"] = True
        notify.send(f"⛔ البوت وگف شراء: الرصيد نزل {100 * config.MAX_DRAWDOWN:.0f}% عن أعلى رقم وصله")
        log.error("Equity fell %.0f%% from its peak. Bot stopped buying for good. "
                  "Delete \"halted\" from %s to resume.", 100 * config.MAX_DRAWDOWN, config.STATE_FILE.name)
        return "halted"
    if eq <= state["day_start_equity"] * (1 - config.DAILY_LOSS_LIMIT):
        return "daily loss limit"
    return None


def new_listings(state, tickers, days=3):
    """USDT pairs that appeared on the exchange in the last few days."""
    now = int(time.time())
    seen = state.setdefault("first_seen", {})
    first_run = not seen
    for t in tickers:
        if t["symbol"].endswith("USDT") and t["symbol"] not in seen:
            seen[t["symbol"]] = 0 if first_run else now
    return [s for s, ts in seen.items() if ts and now - ts < days * 86400]


TAG_AR = {"new": "عملة جديدة", "meme": "عملة ميم", "trending": "ترند", "gainer": "صاعدة هواية اليوم"}


def age_text(hours):
    return f"{hours:.0f} ساعة" if hours < 48 else f"{hours / 24:.0f} أيام"


def buy_message(sig, cost, stop_dist):
    if "ann" in sig.tags:
        from .announce import SOURCE_AR
        return (f"📢 {SOURCE_AR[sig.tags[1]]} أعلنت إنها راح تدرج {sig.symbol[:-4]}!\n"
                f"🚀 اشتريتها فوراً على Bybit بـ {cost:.2f}$\n"
                f"🛡 إذا نزلت {100 * stop_dist:.0f}% أبيعها، وإذا قفزت أحمي الربح وأبيع لمن ترجع")
    if "lotto" in sig.tags:
        return (f"🎟 اشتريت تذكرة يانصيب: {sig.symbol[:-4]} بـ {cost:.2f}$\n"
                f"🆕 عملة جديدة نزلت قبل {age_text(sig.age_h)}، وهسه كسرت أعلى سعر إلها بتداول قوي\n"
                f"🎯 إذا صارت 3 أضعاف أبيع ثلثها، وإذا صارت 10 أضعاف أبيع نص الباقي\n"
                f"🛡 إذا نزلت {100 * stop_dist:.0f}% أعتبرها خسرانة وأبيعها")
    what = " + ".join(TAG_AR[t] for t in sig.tags if t in TAG_AR)
    lines = [f"🚀 اشتريت {sig.symbol[:-4]} بـ {cost:.2f}$"]
    if what:
        lines.append(f"🏷 {what}")
    if sig.vol_ratio:
        lines.append(f"📊 كسرت أعلى سعر إلها، والتداول عليها صار {sig.vol_ratio:.0f} أضعاف")
    lines.append(f"🛡 إذا نزلت {100 * stop_dist:.0f}% أبيعها")
    if config.TAKE_PROFIT_PCT:
        lines.append(f"💰 إذا صعدت {100 * config.TAKE_PROFIT_PCT:.0f}% أبيع نصها وأقبض الربح")
    return "\n".join(lines)


def open_position(state, broker, sig, usdt, price, stop_dist, **extra):
    qty, cost = broker.buy(sig.symbol, usdt, price)
    if qty <= 0:
        return
    entry = cost / qty
    state["positions"][sig.symbol] = {
        "qty": qty, "cost": cost, "entry": entry, "atr": sig.atr, "highest": entry,
        "stop": entry * (1 - stop_dist), "opened": int(time.time()), "reason": sig.reason, **extra,
    }
    log.info("BUY  %s @ %.6g  %.2f USDT  stop %.6g  [%s]",
             sig.symbol, entry, cost, entry * (1 - stop_dist), sig.reason)
    notify.send(buy_message(sig, cost, stop_dist))


def find_lotto_entries(state, broker, px, eq, tickers):
    slots = config.MAX_POSITIONS - len(state["positions"])
    if slots <= 0:
        return
    listed = state.setdefault("listed", {})  # symbol -> listing time; it never changes, so cache it
    now = time.time()
    signals, fresh = [], 0
    for t in tickers:
        sym = t["symbol"]
        if (not sym.endswith("USDT") or sym[:-4] in config.STABLECOINS or sym in state["positions"]
                or sym in state["cooldown"] or float(t["quoteVolume"]) < config.MIN_QUOTE_VOLUME):
            continue
        try:
            if sym not in listed:
                listed[sym] = data.listing_time(sym)
            if not listed[sym] or now - listed[sym] > config.LOTTO_MAX_AGE_DAYS * 86400:
                continue
            fresh += 1
            sig = lotto.evaluate(sym, data.klines(sym, "1h", 200), listed[sym], now)
        except Exception as e:
            log.warning("skip %s: %s", sym, e)
            continue
        if sig:
            signals.append(sig)
    signals.sort(key=lambda s: s.score, reverse=True)
    log.info("lotto: %d new listings watched, %d tickets to buy", fresh, len(signals))
    for sig in signals[:slots]:
        usdt = min(eq * config.MAX_POSITION_PCT, broker.cash() * 0.99)
        if usdt < config.MIN_ORDER_USDT:
            log.info("not enough cash for %s (%.2f USDT)", sig.symbol, usdt)
            break
        open_position(state, broker, sig, usdt, px.get(sig.symbol, sig.price), config.LOTTO_STOP, lotto=True)


def find_entries(state, broker, px, eq, tickers):
    if config.STRATEGY == "lotto":
        return find_lotto_entries(state, broker, px, eq, tickers)
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
    if config.STRATEGY == "meme":
        universe = data.build_meme_universe(tickers, trending, data.meme_symbols())
        volume = {t["symbol"]: float(t["quoteVolume"]) for t in tickers}
        for sym in new_listings(state, tickers):
            if volume.get(sym, 0) >= config.MIN_QUOTE_VOLUME:
                universe.setdefault(sym, []).insert(0, "new")
    else:
        universe = {s: ["trending"] if s[:-4] in trending else [] for s in data.build_universe(tickers, trending)}

    signals = []
    for symbol, tags in universe.items():
        if symbol in state["positions"]:
            continue
        if now - state["cooldown"].get(symbol, 0) < config.COOLDOWN_HOURS * 3600:
            continue
        try:
            candles = data.klines(symbol)
            if config.STRATEGY == "meme":
                sig = strategy.evaluate_momentum(
                    symbol, candles, tags, config.MAX_ATR_PCT, config.MOMENTUM_VOL_MULT,
                    config.MOMENTUM_LOOKBACK, max(1, 3600 // data.INTERVAL_SECONDS[config.INTERVAL]))
            else:
                sig = strategy.evaluate(symbol, candles, "trending" in tags, config.MAX_ATR_PCT)
        except Exception as e:
            log.warning("skip %s: %s", symbol, e)
            continue
        if sig:
            signals.append(sig)
    signals.sort(key=lambda s: s.score, reverse=True)
    log.info("scanned %d coins, %d signals%s", len(universe), len(signals),
             f" (best {signals[0].symbol}: {signals[0].reason})" if signals else "")

    # The meme strategy is meant to take risk, so it doesn't shrink in a shaky market.
    size_mult = 0.5 if regime == "caution" and config.STRATEGY != "meme" else 1.0
    for sig in signals[:slots]:
        price = px.get(sig.symbol, sig.price)
        stop_dist = min(max(config.STOP_ATR * sig.atr / price, config.MIN_STOP_PCT), config.MAX_STOP_PCT)
        usdt = min(eq * config.RISK_PER_TRADE / stop_dist, eq * config.MAX_POSITION_PCT) * size_mult
        usdt = min(usdt, broker.cash() * 0.99)
        if usdt < config.MIN_ORDER_USDT:
            log.info("not enough cash for %s (%.2f USDT)", sig.symbol, usdt)
            break
        open_position(state, broker, sig, usdt, price, stop_dist)


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
    log.info("started in %s mode, strategy %s", "LIVE (real money)" if broker.live else "paper", config.STRATEGY)
    notify.send(f"✅ البوت اشتغل ({'فلوس حقيقية' if broker.live else 'فلوس وهمية'}، وضع {config.STRATEGY})")
    lock = threading.Lock()  # the Telegram and news threads touch the same state
    watcher = None
    if config.ANNOUNCE and not args.once:
        from .announce import Watcher
        watcher = Watcher(state, broker, lock)
        threading.Thread(target=watcher.run, daemon=True).start()
    if notify.enabled() and not args.once:
        from .telegram_bot import Commands
        threading.Thread(target=Commands(state, broker, lock, watcher).run, daemon=True).start()
    while True:
        with lock:
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
