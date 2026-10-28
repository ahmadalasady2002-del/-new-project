"""Market data from public sources: Binance, CoinGecko, and the Fear & Greed index."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

UA = {"User-Agent": "trading-bot/1.0"}


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


def tickers_24h():
    return get_json(f"{config.BINANCE_BASE}/api/v3/ticker/24hr", {"type": "FULL"})


def prices():
    rows = get_json(f"{config.BINANCE_BASE}/api/v3/ticker/price")
    return {r["symbol"]: float(r["price"]) for r in rows}


def klines(symbol, interval=None, limit=250):
    rows = get_json(
        f"{config.BINANCE_BASE}/api/v3/klines",
        {"symbol": symbol, "interval": interval or config.INTERVAL, "limit": limit},
    )
    candles = [
        {
            "time": r[0] // 1000,
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in rows
    ]
    # Drop the candle that hasn't closed yet so signals don't flicker.
    close_time = rows[-1][6] // 1000 if rows else 0
    if candles and close_time > time.time():
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
        if base in config.STABLECOINS or base.endswith(("UP", "DOWN", "BULL", "BEAR")):
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
