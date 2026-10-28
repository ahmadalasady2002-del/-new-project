"""Market data from public sources: Bybit, CoinGecko, and the Fear & Greed index."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

UA = {"User-Agent": "trading-bot/1.0"}

# Bybit names intervals in minutes.
BYBIT_INTERVALS = {"15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240", "1d": "D"}
INTERVAL_SECONDS = {"15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}


def get_json(url, params=None, headers=None, tries=3, timeout=15):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            # 4xx (except rate limits) won't fix themselves on retry
            if e.code < 500 and e.code != 429:
                raise
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 ** attempt)
    raise last


def bybit_public(path, params):
    data = get_json(f"{config.BYBIT_BASE}{path}", params)
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit {path}: {data.get('retMsg')}")
    return data["result"]


def tickers_24h():
    rows = bybit_public("/v5/market/tickers", {"category": "spot"})["list"]
    return [
        {"symbol": r["symbol"], "lastPrice": r["lastPrice"], "quoteVolume": r["turnover24h"]}
        for r in rows
    ]


def klines(symbol, interval=None, limit=250):
    interval = interval or config.INTERVAL
    rows = bybit_public("/v5/market/kline", {
        "category": "spot", "symbol": symbol,
        "interval": BYBIT_INTERVALS[interval], "limit": limit,
    })["list"]
    candles = [
        {
            "time": int(r[0]) // 1000,
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in reversed(rows)  # Bybit sends newest first
    ]
    # Drop the candle that hasn't closed yet so signals don't flicker.
    if candles and candles[-1]["time"] + INTERVAL_SECONDS[interval] > time.time():
        candles.pop()
    return candles


def trending_symbols():
    """Coins people are searching for most on CoinGecko right now."""
    try:
        data = get_json("https://api.coingecko.com/api/v3/search/trending")
        return {c["item"]["symbol"].upper() for c in data.get("coins", [])}
    except Exception:
        return set()


def fear_greed():
    """0 = extreme fear, 100 = extreme greed. None if unavailable."""
    try:
        data = get_json("https://api.alternative.me/fng/", {"limit": 1})
        return int(data["data"][0]["value"])
    except Exception:
        return None


def build_universe(tickers, trending):
    """Liquid USDT pairs, plus trending coins with enough volume."""
    rows = []
    for t in tickers:
        sym = t["symbol"]
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if base in config.STABLECOINS or base.endswith(("UP", "DOWN", "BULL", "BEAR", "2L", "3L", "2S", "3S")):
            continue
        vol = float(t["quoteVolume"])
        if float(t["lastPrice"]) <= 0:
            continue
        rows.append((sym, base, vol))
    rows.sort(key=lambda r: r[2], reverse=True)
    universe = [s for s, _, v in rows if v >= config.MIN_QUOTE_VOLUME][: config.UNIVERSE_SIZE]
    for sym, base, vol in rows:
        if base in trending and vol >= config.MIN_TRENDING_VOLUME and sym not in universe:
            universe.append(sym)
    return universe
