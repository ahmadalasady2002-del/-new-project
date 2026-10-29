"""Market data from public sources: Bybit, CoinGecko, and the Fear & Greed index."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

UA = {"User-Agent": "trading-bot/1.0"}

# Bybit names intervals in minutes.
BYBIT_INTERVALS = {"5m": "5", "15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240", "1d": "D"}
INTERVAL_SECONDS = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}


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
            # 4xx won't fix themselves on retry, except rate limits (Bybit's CDN answers 403 for those)
            if e.code < 500 and e.code not in (403, 429):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 ** attempt)
    raise last


RATE_LIMITED = {10006, 10018}  # Bybit: too many requests


def bybit_public(path, params, tries=4):
    for attempt in range(tries):
        data = get_json(f"{config.BYBIT_BASE}{path}", params)
        if data.get("retCode") == 0:
            return data["result"]
        if data.get("retCode") not in RATE_LIMITED:
            break
        time.sleep(1 + 2 * attempt)
    raise RuntimeError(f"Bybit {path}: {data.get('retMsg')}")


def tickers_24h():
    rows = bybit_public("/v5/market/tickers", {"category": "spot"})["list"]
    return [
        {"symbol": r["symbol"], "lastPrice": r["lastPrice"], "quoteVolume": r["turnover24h"],
         "change": r.get("price24hPcnt") or "0"}
        for r in rows
    ]


def price(symbol):
    rows = bybit_public("/v5/market/tickers", {"category": "spot", "symbol": symbol})["list"]
    if not rows:
        raise RuntimeError(f"{symbol} not on Bybit")
    return float(rows[0]["lastPrice"])


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


def history(symbol, interval, days, skip_days=0):
    """Closed candles for `days` days ending `skip_days` ago, oldest first (Bybit pages 1000 at a time)."""
    step = INTERVAL_SECONDS[interval]
    end = int(time.time()) - skip_days * 86400
    start = end - days * 86400
    end_ms = end * 1000
    out = {}
    while True:
        rows = bybit_public("/v5/market/kline", {
            "category": "spot", "symbol": symbol, "interval": BYBIT_INTERVALS[interval],
            "limit": 1000, "end": end_ms,
        })["list"]
        for r in rows:
            t = int(r[0]) // 1000
            if start <= t and t + step <= min(end, time.time()):
                out[t] = {"time": t, "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
                          "close": float(r[4]), "volume": float(r[5])}
        if len(rows) < 1000 or int(rows[-1][0]) // 1000 <= start:
            break
        end_ms = int(rows[-1][0]) - 1
    return [out[t] for t in sorted(out)]


def listing_time(symbol):
    """When the pair started trading (unix seconds), or 0 if it is over 1000 days old."""
    rows = bybit_public("/v5/market/kline", {"category": "spot", "symbol": symbol, "interval": "D",
                                             "limit": 1000})["list"]
    if not rows or len(rows) >= 1000:
        return 0
    return int(rows[-1][0]) // 1000  # newest first, so the last row is the first day


def trending_symbols():
    """Coins people are searching for most on CoinGecko right now."""
    try:
        data = get_json("https://api.coingecko.com/api/v3/search/trending")
        return {c["item"]["symbol"].upper() for c in data.get("coins", [])}
    except Exception:
        return set()


def meme_symbols():
    """Meme coins by volume from CoinGecko, falling back to a built-in list."""
    try:
        rows = get_json("https://api.coingecko.com/api/v3/coins/markets", {
            "vs_currency": "usd", "category": "meme-token", "order": "volume_desc", "per_page": 250,
        })
        return {r["symbol"].upper() for r in rows} | config.MEME_COINS
    except Exception:
        return set(config.MEME_COINS)


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


def build_meme_universe(tickers, trending, memes):
    """Meme coins, trending coins, and today's biggest gainers, ranked by heat."""
    picked = {}
    for t in tickers:
        sym = t["symbol"]
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if base in config.STABLECOINS or base.endswith(("UP", "DOWN", "BULL", "BEAR", "2L", "3L", "2S", "3S")):
            continue
        vol, change = float(t["quoteVolume"]), float(t.get("change") or 0)
        if vol < config.MIN_QUOTE_VOLUME or float(t["lastPrice"]) <= 0:
            continue
        tags = []
        if base in memes:
            tags.append("meme")
        if base in trending:
            tags.append("trending")
        if change >= 0.15:
            tags.append("gainer")
        if tags:
            # Hot coins first: big movers, then volume.
            picked[sym] = (change * 100 + len(tags) * 10 + min(vol / 1e7, 20), tags)
    ranked = sorted(picked, key=lambda s: picked[s][0], reverse=True)[: config.UNIVERSE_SIZE]
    return {s: picked[s][1] for s in ranked}
