"""Bot settings. Every value can be overridden from the .env file."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(ROOT / ".env")


def _f(name, default):
    return float(os.getenv(name, default))


def _i(name, default):
    return int(os.getenv(name, default))


# --- connection ---
BYBIT_BASE = os.getenv("BYBIT_BASE", "https://api.bybit.com")
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# Real money only when this is exactly "yes" and keys exist.
LIVE_TRADING = os.getenv("LIVE_TRADING", "no").lower() == "yes"

# --- paper trading ---
PAPER_START_USDT = _f("PAPER_START_USDT", 100)
FEE_RATE = _f("FEE_RATE", 0.001)  # 0.1% per side

# "meme"  = aggressive: volume breakouts in meme coins, new listings and top gainers
# "lotto" = lottery tickets: small buys in brand-new listings, held for big multiples
# "safe"  = calmer: big liquid coins
_DEFAULTS = {
    "safe": {
        "MIN_QUOTE_VOLUME": 20_000_000, "MIN_TRENDING_VOLUME": 5_000_000, "UNIVERSE_SIZE": 40,
        "INTERVAL": "1h", "RISK_PER_TRADE": 0.01, "MAX_POSITION_PCT": 0.20, "MAX_POSITIONS": 4,
        "DAILY_LOSS_LIMIT": 0.05, "MAX_DRAWDOWN": 0.30, "STOP_ATR": 2.0, "TRAIL_START_ATR": 1.5,
        "MIN_STOP_PCT": 0.02, "MAX_STOP_PCT": 0.08, "MAX_HOLD_HOURS": 72, "COOLDOWN_HOURS": 12,
        "MAX_ATR_PCT": 0.06, "CYCLE_SECONDS": 300, "TAKE_PROFIT_PCT": 0, "MOMENTUM_VOL_MULT": 3,
    },
    "meme": {
        # Picked by `bot-test --sweep` over 60 days: 1h candles, 5x volume, wide stop.
        "MIN_QUOTE_VOLUME": 1_000_000, "MIN_TRENDING_VOLUME": 1_000_000, "UNIVERSE_SIZE": 60,
        "INTERVAL": "1h", "RISK_PER_TRADE": 0.03, "MAX_POSITION_PCT": 0.30, "MAX_POSITIONS": 5,
        "DAILY_LOSS_LIMIT": 0.15, "MAX_DRAWDOWN": 0.50, "STOP_ATR": 3.5, "TRAIL_START_ATR": 2.0,
        "MIN_STOP_PCT": 0.07, "MAX_STOP_PCT": 0.15, "MAX_HOLD_HOURS": 12, "COOLDOWN_HOURS": 4,
        "MAX_ATR_PCT": 0.15, "CYCLE_SECONDS": 120, "TAKE_PROFIT_PCT": 0.10, "MOMENTUM_VOL_MULT": 5,
    },
    "lotto": {
        # Each ticket is MAX_POSITION_PCT of equity; exits are the lotto ladder below, not ATR stops.
        "MIN_QUOTE_VOLUME": 500_000, "MIN_TRENDING_VOLUME": 500_000, "UNIVERSE_SIZE": 0,
        "INTERVAL": "1h", "RISK_PER_TRADE": 0, "MAX_POSITION_PCT": 0.07, "MAX_POSITIONS": 14,
        # STOP_ATR/TRAIL_START_ATR only matter for non-lotto positions left over from another mode.
        "DAILY_LOSS_LIMIT": 1.0, "MAX_DRAWDOWN": 0.90, "STOP_ATR": 3.5, "TRAIL_START_ATR": 2.0,
        "MIN_STOP_PCT": 0.60, "MAX_STOP_PCT": 0.60, "MAX_HOLD_HOURS": 30 * 24, "COOLDOWN_HOURS": 1e6,
        "MAX_ATR_PCT": 1.0, "CYCLE_SECONDS": 300, "TAKE_PROFIT_PCT": 0, "MOMENTUM_VOL_MULT": 2,
    },
}


def load(strategy):
    """Set every strategy-dependent setting; values in .env still win."""
    d = _DEFAULTS[strategy]
    globals().update(
        STRATEGY=strategy,
        # coin selection
        MIN_QUOTE_VOLUME=_f("MIN_QUOTE_VOLUME", d["MIN_QUOTE_VOLUME"]),  # 24h volume in USDT
        MIN_TRENDING_VOLUME=_f("MIN_TRENDING_VOLUME", d["MIN_TRENDING_VOLUME"]),
        UNIVERSE_SIZE=_i("UNIVERSE_SIZE", d["UNIVERSE_SIZE"]),
        INTERVAL=os.getenv("INTERVAL", d["INTERVAL"]),
        MAX_ATR_PCT=_f("MAX_ATR_PCT", d["MAX_ATR_PCT"]),  # skip coins wilder than this per candle
        # entry: break the high of the last N candles on at least X times normal volume
        MOMENTUM_LOOKBACK=_i("MOMENTUM_LOOKBACK", 12),
        MOMENTUM_VOL_MULT=_f("MOMENTUM_VOL_MULT", d["MOMENTUM_VOL_MULT"]),
        # risk
        RISK_PER_TRADE=_f("RISK_PER_TRADE", d["RISK_PER_TRADE"]),  # max equity lost per trade
        MAX_POSITION_PCT=_f("MAX_POSITION_PCT", d["MAX_POSITION_PCT"]),  # max equity in one coin
        MAX_POSITIONS=_i("MAX_POSITIONS", d["MAX_POSITIONS"]),
        DAILY_LOSS_LIMIT=_f("DAILY_LOSS_LIMIT", d["DAILY_LOSS_LIMIT"]),  # stop buying for the day
        MAX_DRAWDOWN=_f("MAX_DRAWDOWN", d["MAX_DRAWDOWN"]),  # stop buying for good
        STOP_ATR=_f("STOP_ATR", d["STOP_ATR"]),
        TRAIL_START_ATR=_f("TRAIL_START_ATR", d["TRAIL_START_ATR"]),
        MIN_STOP_PCT=_f("MIN_STOP_PCT", d["MIN_STOP_PCT"]),
        MAX_STOP_PCT=_f("MAX_STOP_PCT", d["MAX_STOP_PCT"]),
        MAX_HOLD_HOURS=_f("MAX_HOLD_HOURS", d["MAX_HOLD_HOURS"]),
        COOLDOWN_HOURS=_f("COOLDOWN_HOURS", d["COOLDOWN_HOURS"]),  # don't rebuy right after selling
        # at +TAKE_PROFIT_PCT sell TAKE_PROFIT_SHARE and move the stop to break-even (0 = off)
        TAKE_PROFIT_PCT=_f("TAKE_PROFIT_PCT", d["TAKE_PROFIT_PCT"]),
        TAKE_PROFIT_SHARE=_f("TAKE_PROFIT_SHARE", 0.5),
        CYCLE_SECONDS=_i("CYCLE_SECONDS", d["CYCLE_SECONDS"]),
    )


load(os.getenv("STRATEGY", "meme").lower())

MIN_ORDER_USDT = _f("MIN_ORDER_USDT", 6)

# --- listing news (Binance / Upbit announcements) ---
ANNOUNCE = os.getenv("ANNOUNCE", "yes").lower() == "yes"
ANN_POLL_SECONDS = _f("ANN_POLL_SECONDS", 15)
ANN_POSITION_PCT = _f("ANN_POSITION_PCT", 0.20)  # share of equity per news trade
ANN_MAX_POSITIONS = _i("ANN_MAX_POSITIONS", 3)
ANN_MAX_JUMP = _f("ANN_MAX_JUMP", 0.30)  # skip if it already rose this much in the last hour
ANN_STOP = _f("ANN_STOP", 0.08)
ANN_TRAIL_START = _f("ANN_TRAIL_START", 0.05)  # once up 5%, sell on an 8% drop from the top
ANN_TRAIL = _f("ANN_TRAIL", 0.08)
ANN_MAX_HOURS = _f("ANN_MAX_HOURS", 6)

# --- lotto ---
LOTTO_WAIT_HOURS = _f("LOTTO_WAIT_HOURS", 24)  # let the listing-day dump play out first
LOTTO_MAX_AGE_DAYS = _f("LOTTO_MAX_AGE_DAYS", 7)  # only coins listed within this many days
LOTTO_STOP = _f("LOTTO_STOP", 0.60)  # ticket is lost after -60% (before the first ladder step)
LOTTO_TRAIL = _f("LOTTO_TRAIL", 0.50)  # after the first step, sell the rest on a 50% drop from the top
LOTTO_LADDER = ((3.0, 1 / 3), (10.0, 1 / 2))  # at 3x sell a third; at 10x half of what's left

STATE_FILE = ROOT / os.getenv("STATE_FILE", "state.json")
LOG_FILE = ROOT / os.getenv("LOG_FILE", "bot.log")

STABLECOINS = {
    "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "EUR", "AEUR", "USDE",
    "PYUSD", "USD1", "XUSD", "BFUSD", "RLUSD", "EURI", "PAXG", "WBTC", "WBETH",
    "USDQ", "USDR", "XAUT", "STETH", "METH", "CMETH",
}

# Fallback when CoinGecko's meme list is unavailable.
MEME_COINS = {
    "DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "BOME", "MEW", "POPCAT", "BRETT", "MOG",
    "NEIRO", "TURBO", "PNUT", "GOAT", "MOODENG", "TRUMP", "FARTCOIN", "SPX", "PENGU", "PEOPLE",
    "MEME", "BABYDOGE", "CAT", "MYRO", "SLERF", "ACT", "CHILLGUY", "DOGS", "HMSTR", "NOT", "BOBO",
    "LADYS", "WEN", "PONKE", "SUNDOG", "GIGA", "MICHI", "BAN", "DEGEN", "TOSHI", "SIREN", "PUMP",
}
