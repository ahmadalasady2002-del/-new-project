"""Replay the strategy on real past prices to see how it would have done.

  python -m bot.backtest              # last 30 days
  python -m bot.backtest --days 60
  python -m bot.backtest --sweep      # compare strategy variants on the same data

Rules match the live bot: same signals, sizes, stops, take-profit and loss limits.
Stops fill at the stop price (or the open, if price gapped through it), and every
fill pays the fee plus slippage. The coins are today's popular ones, which flatters
the result a bit: coins that died during the period aren't in the test.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config, data, notify, strategy

SLIPPAGE = 0.002  # meme order books are thin


class Sim:
    def __init__(self, cash):
        self.cash = cash
        self.positions = {}
        self.trades = []
        self.cooldown = {}
        self.peak = cash
        self.max_dd = 0.0
        self.day = None
        self.day_start = cash
        self.halted = False

    def buy(self, sym, usdt, price, sig, ts, stop_dist):
        fill = price * (1 + SLIPPAGE)
        qty = usdt * (1 - config.FEE_RATE) / fill
        self.cash -= usdt
        entry = usdt / qty
        self.positions[sym] = {"qty": qty, "cost": usdt, "entry": entry, "atr": sig.atr,
                               "highest": entry, "stop": entry * (1 - stop_dist),
                               "opened": ts, "reason": sig.reason, "tp_done": False}

    def sell(self, sym, share, price, ts, why):
        pos = self.positions[sym]
        qty, cost = pos["qty"] * share, pos["cost"] * share
        proceeds = qty * price * (1 - SLIPPAGE) * (1 - config.FEE_RATE)
        self.cash += proceeds
        self.trades.append({"symbol": sym, "opened": pos["opened"], "closed": ts, "pnl": proceeds - cost,
                            "pct": proceeds / cost - 1, "why": why, "setup": pos["reason"]})
        if share >= 1:
            del self.positions[sym]
            self.cooldown[sym] = ts
        else:
            pos["qty"] -= qty
            pos["cost"] -= cost

    def manage(self, sym, c):
        pos = self.positions[sym]
        if c["low"] <= pos["stop"]:
            self.sell(sym, 1, min(pos["stop"], c["open"]), c["time"], "stop")
            return
        target = pos["entry"] * (1 + config.TAKE_PROFIT_PCT)
        if config.TAKE_PROFIT_PCT and not pos["tp_done"] and c["high"] >= target:
            pos["tp_done"] = True
            self.sell(sym, config.TAKE_PROFIT_SHARE, max(target, c["open"]), c["time"], "tp")
            pos["stop"] = max(pos["stop"], pos["entry"] * (1 + 2 * config.FEE_RATE))
        pos["highest"] = max(pos["highest"], c["high"])
        if pos["highest"] - pos["entry"] >= config.TRAIL_START_ATR * pos["atr"]:
            pos["stop"] = max(pos["stop"], pos["highest"] - config.STOP_ATR * pos["atr"])
        hours = (c["time"] - pos["opened"]) / 3600
        if hours >= config.MAX_HOLD_HOURS and c["close"] < pos["entry"] + pos["atr"]:
            self.sell(sym, 1, c["close"], c["time"], "time")

    def equity(self, last):
        return self.cash + sum(p["qty"] * last[s] for s, p in self.positions.items())

    def can_buy(self, eq, ts):
        day = datetime.fromtimestamp(ts, timezone.utc).date()
        if day != self.day:
            self.day, self.day_start = day, eq
        self.peak = max(self.peak, eq)
        self.max_dd = max(self.max_dd, 1 - eq / self.peak)
        if eq <= self.peak * (1 - config.MAX_DRAWDOWN):
            self.halted = True
        return not self.halted and eq > self.day_start * (1 - config.DAILY_LOSS_LIMIT)


def pick_symbols(limit):
    tickers = data.tickers_24h()
    if config.STRATEGY != "meme":
        return {s: [] for s in data.build_universe(tickers, set())[:limit]}
    memes = data.meme_symbols()
    majors = {"BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "TRX", "TON", "LTC", "BCH", "DOT", "LINK", "AVAX"}
    rows = []
    for t in tickers:
        sym, vol = t["symbol"], float(t["quoteVolume"])
        base = sym[:-4]
        if (not sym.endswith("USDT") or vol < config.MIN_QUOTE_VOLUME or base in config.STABLECOINS
                or base in majors or base.endswith(("2L", "3L", "2S", "3S"))):
            continue
        rows.append((base not in memes, -vol, sym, base))  # memes first, then by volume
    rows.sort()
    return {sym: ["meme"] if base in memes else [] for _, _, sym, base in rows[:limit]}


def quick_reject(candles, i):
    """Cheap pre-check so we only run the full indicators on candidate candles."""
    lookback = config.MOMENTUM_LOOKBACK
    if i < max(21, lookback):
        return True
    c = candles[i]
    avg_vol = sum(x["volume"] for x in candles[i - 20:i]) / 20
    prior_high = max(x["high"] for x in candles[i - lookback:i])
    return c["volume"] < min(2, config.MOMENTUM_VOL_MULT) * avg_vol or c["close"] <= prior_high


def run(history, tags, start_cash=100.0, bars_per_hour=4):
    sim = Sim(start_cash)
    index = {s: {c["time"]: i for i, c in enumerate(cs)} for s, cs in history.items()}
    last = {}
    for ts in sorted({c["time"] for cs in history.values() for c in cs}):
        for sym in list(sim.positions):
            i = index[sym].get(ts)
            if i is not None:
                sim.manage(sym, history[sym][i])
        for sym, cs in history.items():
            i = index[sym].get(ts)
            if i is not None:
                last[sym] = cs[i]["close"]
        eq = sim.equity(last)
        slots = config.MAX_POSITIONS - len(sim.positions)
        if slots <= 0 or not sim.can_buy(eq, ts):
            continue
        signals = []
        for sym, cs in history.items():
            i = index[sym].get(ts)
            if i is None or sym in sim.positions or quick_reject(cs, i):
                continue
            if ts - sim.cooldown.get(sym, 0) < config.COOLDOWN_HOURS * 3600:
                continue
            window = cs[max(0, i - 249): i + 1]
            if config.STRATEGY == "meme":
                sig = strategy.evaluate_momentum(sym, window, tags[sym], config.MAX_ATR_PCT,
                                                 config.MOMENTUM_VOL_MULT, config.MOMENTUM_LOOKBACK, bars_per_hour)
            else:
                sig = strategy.evaluate(sym, window, False, config.MAX_ATR_PCT)
            if sig:
                signals.append(sig)
        signals.sort(key=lambda s: s.score, reverse=True)
        for sig in signals[:slots]:
            stop_dist = min(max(config.STOP_ATR * sig.atr / sig.price, config.MIN_STOP_PCT), config.MAX_STOP_PCT)
            usdt = min(eq * config.RISK_PER_TRADE / stop_dist, eq * config.MAX_POSITION_PCT, sim.cash * 0.99)
            if usdt < config.MIN_ORDER_USDT:
                break
            sim.buy(sig.symbol, usdt, sig.price, sig, ts, stop_dist)
    for sym in list(sim.positions):
        sim.sell(sym, 1, last[sym], ts, "end")
    return sim


def summary(sim, start_cash, days, n_coins):
    trades = sim.trades
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    final = sim.cash
    lines = [
        f"strategy {config.STRATEGY} | {days} days | {n_coins} coins | start {start_cash:.2f} USDT",
        f"end balance: {final:.2f} USDT ({final / start_cash - 1:+.1%})",
        f"trades: {len(trades)} | wins {len(wins)} ({len(wins) / max(len(trades), 1):.0%})"
        f" | avg win {sum(t['pct'] for t in wins) / max(len(wins), 1):+.1%}"
        f" | avg loss {sum(t['pct'] for t in losses) / max(len(losses), 1):+.1%}",
        f"worst drop from peak: -{sim.max_dd:.1%}" + ("  (bot would have STOPPED)" if sim.halted else ""),
    ]
    by_pnl = sorted(trades, key=lambda t: t["pnl"])
    for label, ts in (("best", by_pnl[-3:][::-1]), ("worst", by_pnl[:3])):
        for t in ts:
            when = datetime.fromtimestamp(t["opened"], timezone.utc).strftime("%m-%d %H:%M")
            lines.append(f"  {label:<5} {when} {t['symbol']:<14} {t['pnl']:+7.2f} ({t['pct']:+.0%}) {t['why']}")
    return "\n".join(lines)


def to_hourly(candles):
    """Merge 15m candles into 1h candles."""
    hours = {}
    for c in candles:
        h = c["time"] - c["time"] % 3600
        if h not in hours:
            hours[h] = dict(c, time=h)
        else:
            m = hours[h]
            m["high"], m["low"] = max(m["high"], c["high"]), min(m["low"], c["low"])
            m["close"], m["volume"] = c["close"], m["volume"] + c["volume"]
    return [hours[h] for h in sorted(hours)]


# name -> (config overrides, use 1h candles)
VARIANTS = {
    "current": ({}, False),
    "vol x5": ({"MOMENTUM_VOL_MULT": 5}, False),
    "6h high": ({"MOMENTUM_LOOKBACK": 24}, False),
    "vol x5 + 6h high": ({"MOMENTUM_VOL_MULT": 5, "MOMENTUM_LOOKBACK": 24}, False),
    "wide stop": ({"MIN_STOP_PCT": 0.07, "MAX_STOP_PCT": 0.15, "STOP_ATR": 3.5}, False),
    "no take-profit": ({"TAKE_PROFIT_PCT": 0}, False),
    "take-profit 20%": ({"TAKE_PROFIT_PCT": 0.20}, False),
    "hold 24h": ({"MAX_HOLD_HOURS": 24}, False),
    "1h candles": ({"MOMENTUM_LOOKBACK": 12}, True),
    "1h candles + vol x5": ({"MOMENTUM_LOOKBACK": 12, "MOMENTUM_VOL_MULT": 5}, True),
    "1h + vol x5 + wide stop": ({"MOMENTUM_VOL_MULT": 5, "MIN_STOP_PCT": 0.07, "MAX_STOP_PCT": 0.15,
                                 "STOP_ATR": 3.5}, True),
}


@contextmanager
def overrides(values):
    saved = {k: getattr(config, k) for k in values}
    for k, v in values.items():
        setattr(config, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


VARIANT_AR = {
    "current": "الحالية",
    "vol x5": "انفجار أقوى (تداول ×5)",
    "6h high": "يكسر قمة 6 ساعات",
    "vol x5 + 6h high": "انفجار أقوى + قمة 6 ساعات",
    "wide stop": "وقف خسارة أعرض",
    "no take-profit": "بدون قبض ربح",
    "take-profit 20%": "قبض الربح عند 20%",
    "hold 24h": "يمسك العملة 24 ساعة",
    "1h candles": "شموع ساعة",
    "1h candles + vol x5": "شموع ساعة + انفجار أقوى",
    "1h + vol x5 + wide stop": "شموع ساعة + انفجار أقوى + وقف أعرض",
}


def sweep(history, tags):
    """Run every variant on the same history; best ending balance first."""
    hourly = {s: to_hourly(cs) for s, cs in history.items()}
    results = []
    for name, (values, use_hourly) in VARIANTS.items():
        with overrides(values):
            sim = run(hourly if use_hourly else history, tags, bars_per_hour=1 if use_hourly else 4)
        wins = sum(t["pnl"] > 0 for t in sim.trades)
        results.append((sim.cash, name, len(sim.trades), wins, sim.max_dd))
    return sorted(results, reverse=True)


def sweep_text(results, days, n_coins):
    lines = [f"{days} days | {n_coins} coins | start 100 USDT", "end    trades win%  maxDD  variant"]
    for cash, name, n, wins, dd in results:
        lines.append(f"{cash:6.1f} {n:6d} {wins / max(n, 1):4.0%} {-dd:6.1%}  {name}")
    return "\n".join(lines)


def money(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def sweep_message(results, days, n_coins):
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"🧪 جربت {len(results)} نسخ من البوت على أسعار آخر {days} يوم، على {n_coins} عملات",
             "كل نسخة بدت بـ 100$، وهاي النتيجة من الأحسن للأسوأ:", ""]
    for k, (cash, name, n, wins, dd) in enumerate(results):
        mark = medals[k] if k < 3 else f"{k + 1}."
        icon = "📈" if cash > 100 else "📉"
        lines.append(f"{mark} {VARIANT_AR.get(name, name)}")
        lines.append(f"    {icon} صارت {money(cash)}$ ({cash - 100:+.1f}%)")
        lines.append(f"    🔁 {n} صفقة، ربحت منها {wins / max(n, 1):.0%}")
        if n < 20:
            lines.append("    ⚠️ صفقاتها قليلة، فنتيجتها ممكن تكون حظ")
        lines.append("")
    best = results[0]
    if best[0] > 100:
        lines.append(f"✅ الأحسن: {VARIANT_AR.get(best[1], best[1])}")
    else:
        lines.append("❌ ولا نسخة ربحت بهالفترة")
    return "\n".join(lines)


def summary_message(sim, start_cash, days, n_coins):
    trades = sim.trades
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    final = sim.cash
    change = final / start_cash - 1
    lines = [
        f"🧪 جربت البوت على أسعار آخر {days} يوم، على {n_coins} عملات",
        "",
        f"💵 الـ {money(start_cash)}$ صارت {money(final)}$",
        f"{'📈 ربح' if change > 0 else '📉 خسارة'} {abs(change):.1%}",
        "",
        f"🔁 سوى {len(trades)} صفقة:",
        f"    ✅ {len(wins)} ربحت، بمعدل {sum(t['pct'] for t in wins) / max(len(wins), 1):+.1%} للصفقة",
        f"    ❌ {len(losses)} خسرت، بمعدل {sum(t['pct'] for t in losses) / max(len(losses), 1):+.1%} للصفقة",
        f"⚠️ أكبر نزلة بالرصيد: {sim.max_dd:.1%}" + (" (والبوت چان راح يوگف)" if sim.halted else ""),
    ]
    if trades:
        by_pnl = sorted(trades, key=lambda t: t["pnl"])
        lines += ["",
                  f"🏆 أحسن صفقة: {by_pnl[-1]['symbol'][:-4]} {by_pnl[-1]['pct']:+.0%}",
                  f"💔 أسوأ صفقة: {by_pnl[0]['symbol'][:-4]} {by_pnl[0]['pct']:+.0%}"]
    lines += ["", "✅ الخلاصة: الاستراتيجية ربحت" if change > 0 else "❌ الخلاصة: الاستراتيجية خسرت"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--coins", type=int, default=40)
    ap.add_argument("--sweep", action="store_true", help="compare strategy variants")
    args = ap.parse_args()
    tags = pick_symbols(args.coins)
    print(f"downloading {len(tags)} coins x {args.days} days of {config.INTERVAL} candles...")
    history = {}
    for sym in tags:
        try:
            history[sym] = data.history(sym, config.INTERVAL, args.days)
        except Exception as e:
            print(f"  skip {sym}: {e}")
    print("replaying...")
    if args.sweep:
        results = sweep(history, tags)
        print(sweep_text(results, args.days, len(history)))
        notify.send(sweep_message(results, args.days, len(history)))
    else:
        sim = run(history, tags)
        print(summary(sim, 100.0, args.days, len(history)))
        notify.send(summary_message(sim, 100.0, args.days, len(history)))


if __name__ == "__main__":
    main()
