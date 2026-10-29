"""Replay the strategy on real past prices to see how it would have done.

  python -m bot.backtest              # last 30 days
  python -m bot.backtest --days 60

Rules match the live bot: same signals, sizes, stops, take-profit and loss limits.
Stops fill at the stop price (or the open, if price gapped through it), and every
fill pays the fee plus slippage. The coins are today's popular ones, which flatters
the result a bit: coins that died during the period aren't in the test.
"""
import argparse
from datetime import datetime, timezone

from . import config, data, strategy

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
    if config.STRATEGY == "meme":
        memes = data.meme_symbols()
        rows = [t for t in tickers if t["symbol"].endswith("USDT") and t["symbol"][:-4] in memes
                and float(t["quoteVolume"]) >= config.MIN_QUOTE_VOLUME]
        rows.sort(key=lambda t: float(t["quoteVolume"]), reverse=True)
        return {t["symbol"]: ["meme"] for t in rows[:limit]}
    return {s: [] for s in data.build_universe(tickers, set())[:limit]}


def quick_reject(candles, i):
    """Cheap pre-check so we only run the full indicators on candidate candles."""
    if i < 21:
        return True
    c = candles[i]
    avg_vol = sum(x["volume"] for x in candles[i - 20:i]) / 20
    prior_high = max(x["high"] for x in candles[i - 12:i])
    return c["volume"] < 2 * avg_vol or c["close"] <= prior_high


def run(history, tags, start_cash=100.0):
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
                sig = strategy.evaluate_momentum(sym, window, tags[sym], config.MAX_ATR_PCT)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--coins", type=int, default=30)
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
    sim = run(history, tags)
    print(summary(sim, 100.0, args.days, len(history)))


if __name__ == "__main__":
    main()
