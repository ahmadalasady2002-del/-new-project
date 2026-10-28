"""Entry signals and market regime.

Two setups are scored:
  breakout - price breaks its 20-candle high on heavy volume inside an uptrend
  dip      - coin in a long uptrend got oversold and is now bouncing
"""
from dataclasses import dataclass

from . import indicators as ind


@dataclass
class Signal:
    symbol: str
    score: float
    price: float
    atr: float
    reason: str


def market_regime(btc_candles, fng):
    """'on' = buy normally, 'caution' = half size, 'off' = no new buys."""
    closes = [c["close"] for c in btc_candles]
    e50 = ind.ema(closes, 50)
    if not e50 or e50[-1] is None:
        return "caution"
    btc_up = closes[-1] > e50[-1]
    if not btc_up and fng is not None and fng >= 75:
        return "off"  # BTC falling while everyone is greedy
    if not btc_up:
        return "caution"
    if fng is not None and fng >= 85:
        return "caution"  # euphoria - tops form here
    return "on"


def evaluate(symbol, candles, trending=False):
    if len(candles) < 210:
        return None
    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]
    e20, e50, e200 = ind.ema(closes, 20), ind.ema(closes, 50), ind.ema(closes, 200)
    r = ind.rsi(closes, 14)
    a = ind.atr(candles, 14)
    price = closes[-1]
    if not a or price <= 0:
        return None

    avg_vol = sum(vols[-21:-1]) / 20
    vol_ratio = vols[-1] / avg_vol if avg_vol else 0
    prior_high = max(c["high"] for c in candles[-21:-1])
    atr_pct = a / price

    # Ignore coins that are dead or insanely volatile.
    if atr_pct < 0.003 or atr_pct > 0.06:
        return None

    best = None

    # Breakout
    if (
        price > prior_high
        and e20[-1] > e50[-1] > e200[-1]
        and vol_ratio >= 2.0
        and 55 <= r[-1] <= 75
        and (price - e20[-1]) / a < 3  # not already miles above the average
    ):
        score = 50 + min(vol_ratio, 6) * 5 + (75 - r[-1])
        best = Signal(symbol, score, price, a, f"breakout vol x{vol_ratio:.1f} rsi {r[-1]:.0f}")

    # Dip in an uptrend
    recent_low_rsi = min(x for x in r[-6:-1] if x is not None)
    if (
        price > e200[-1]
        and e50[-1] > e200[-1]
        and recent_low_rsi < 30
        and r[-1] > r[-2]
        and r[-1] < 45
        and closes[-1] > candles[-1]["open"]  # bouncing candle
    ):
        score = 45 + (30 - recent_low_rsi) * 2 + min(vol_ratio, 4) * 3
        if not best or score > best.score:
            best = Signal(symbol, score, price, a, f"dip rsi {recent_low_rsi:.0f}->{r[-1]:.0f}")

    if best and trending:
        best.score += 10
        best.reason += " trending"
    return best
