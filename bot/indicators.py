"""Technical indicators on plain lists."""


def ema(values, n):
    if len(values) < n:
        return []
    k = 2 / (n + 1)
    out = [sum(values[:n]) / n]
    for v in values[n:]:
        out.append(v * k + out[-1] * (1 - k))
    return [None] * (n - 1) + out


def rsi(closes, n=14):
    if len(closes) <= n:
        return []
    gains, losses = [], []
    for a, b in zip(closes, closes[1:]):
        d = b - a
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:n]) / n
    avg_l = sum(losses[:n]) / n
    out = [None] * n

    def value(g, l):
        return 100.0 if l == 0 else 100 - 100 / (1 + g / l)

    out.append(value(avg_g, avg_l))
    for g, l in zip(gains[n:], losses[n:]):
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
        out.append(value(avg_g, avg_l))
    return out


def atr(candles, n=14):
    if len(candles) <= n:
        return None
    trs = []
    for prev, c in zip(candles, candles[1:]):
        trs.append(max(c["high"] - c["low"], abs(c["high"] - prev["close"]), abs(c["low"] - prev["close"])))
    value = sum(trs[:n]) / n
    for tr in trs[n:]:
        value = (value * (n - 1) + tr) / n
    return value
