"""Lottery mode: small tickets in brand-new listings, held for big multiples.

Most tickets lose. The bet is that one coin going 10x+ pays for all of them,
so winners are never sold early: a third goes at 3x, half the rest at 10x,
and what's left rides until it falls 50% from its top.
"""
from . import config, indicators as ind
from .strategy import Signal


def evaluate(symbol, candles, listed, now):
    """1h candles since listing. Buy when a coin that survived its first day
    breaks above everything it did after the opening hours, on rising volume."""
    if not candles:
        return None
    # `listed` comes from the daily candle (midnight); the first hourly candle is the real listing hour.
    # For coins older than the candle window this only moves `listed` later, and they are too old anyway.
    listed = max(listed, candles[0]["time"])
    age_h = (now - listed) / 3600
    if not config.LOTTO_WAIT_HOURS <= age_h <= config.LOTTO_MAX_AGE_DAYS * 24:
        return None
    # The first 6 hours after a listing are pure chaos; measure the range after that.
    settled = [c for c in candles[:-1] if c["time"] >= listed + 6 * 3600]
    if len(settled) < 12:
        return None
    last = candles[-1]
    range_high = max(c["high"] for c in settled)
    avg_vol = sum(c["volume"] for c in settled[-24:]) / len(settled[-24:])
    vol_ratio = last["volume"] / avg_vol if avg_vol else 0
    if last["close"] <= range_high or vol_ratio < config.MOMENTUM_VOL_MULT:
        return None
    a = ind.atr(candles, 14) or (last["high"] - last["low"])
    return Signal(symbol, vol_ratio, last["close"], a,
                  f"lotto listed {age_h:.0f}h ago, new high, vol x{vol_ratio:.1f}", ("new", "lotto"), vol_ratio, age_h)


def exits(pos, candle, now):
    """What to sell this candle, as (share of current qty, fill price, why).
    `candle` is a dict with open/high/low/close; live trading passes one price for all four."""
    out = []
    entry, step = pos["entry"], pos.get("ladder", 0)
    if step == 0 and candle["low"] <= entry * (1 - config.LOTTO_STOP):
        return [(1, min(entry * (1 - config.LOTTO_STOP), candle["open"]), "stop")]
    while step < len(config.LOTTO_LADDER) and candle["high"] >= entry * config.LOTTO_LADDER[step][0]:
        mult, share = config.LOTTO_LADDER[step]
        out.append((share, max(entry * mult, candle["open"]), f"x{mult:g}"))
        step += 1
    pos["ladder"] = step
    pos["highest"] = max(pos["highest"], candle["high"])
    if step:
        trail = pos["highest"] * (1 - config.LOTTO_TRAIL)
        if candle["low"] <= trail:
            out.append((1, min(trail, candle["open"]), "trail"))
            return out
    if now - pos["opened"] >= config.MAX_HOLD_HOURS * 3600:
        out.append((1, candle["close"], "time"))
    return out
