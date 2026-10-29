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
# Real money only when this is exactly "yes" and keys exist.
LIVE_TRADING = os.getenv("LIVE_TRADING", "no").lower() == "yes"

# --- paper trading ---
PAPER_START_USDT = _f("PAPER_START_USDT", 100)
FEE_RATE = _f("FEE_RATE", 0.001)  # 0.1% per side

# "meme" = aggressive: meme coins, new listings and top gainers on 15m candles
# "safe" = calmer: big liquid coins on 1h candles
STRATEGY = os.getenv("STRATEGY", "meme").lower()

_DEFAULTS = {
    "safe": {
        "MIN_QUOTE_VOLUME": 20_000_000, "MIN_TRENDING_VOLUME": 5_000_000, "UNIVERSE_SIZE": 40,
        "INTERVAL": "1h", "RISK_PER_TRADE": 0.01, "MAX_POSITION_PCT": 0.20, "MAX_POSITIONS": 4,
        "DAILY_LOSS_LIMIT": 0.05, "MAX_DRAWDOWN": 0.30, "STOP_ATR": 2.0, "TRAIL_START_ATR": 1.5,
        "MIN_STOP_PCT": 0.02, "MAX_STOP_PCT": 0.08, "MAX_HOLD_HOURS": 72, "COOLDOWN_HOURS": 12,
        "MAX_ATR_PCT": 0.06, "CYCLE_SECONDS": 300,
    },
    "meme": {
        "MIN_QUOTE_VOLUME": 1_000_000, "MIN_TRENDING_VOLUME": 1_000_000, "UNIVERSE_SIZE": 60,
        "INTERVAL": "15m", "RISK_PER_TRADE": 0.03, "MAX_POSITION_PCT": 0.30, "MAX_POSITIONS": 5,
        "DAILY_LOSS_LIMIT": 0.15, "MAX_DRAWDOWN": 0.50, "STOP_ATR": 2.5, "TRAIL_START_ATR": 2.0,
        "MIN_STOP_PCT": 0.04, "MAX_STOP_PCT": 0.12, "MAX_HOLD_HOURS": 12, "COOLDOWN_HOURS": 4,
        "MAX_ATR_PCT": 0.15, "CYCLE_SECONDS": 120,
    },
}[STRATEGY]

# --- coin selection ---
MIN_QUOTE_VOLUME = _f("MIN_QUOTE_VOLUME", _DEFAULTS["MIN_QUOTE_VOLUME"])  # 24h volume in USDT
MIN_TRENDING_VOLUME = _f("MIN_TRENDING_VOLUME", _DEFAULTS["MIN_TRENDING_VOLUME"])
UNIVERSE_SIZE = _i("UNIVERSE_SIZE", _DEFAULTS["UNIVERSE_SIZE"])
INTERVAL = os.getenv("INTERVAL", _DEFAULTS["INTERVAL"])
MAX_ATR_PCT = _f("MAX_ATR_PCT", _DEFAULTS["MAX_ATR_PCT"])  # skip coins wilder than this per candle

# --- risk ---
RISK_PER_TRADE = _f("RISK_PER_TRADE", _DEFAULTS["RISK_PER_TRADE"])  # max equity lost per trade
MAX_POSITION_PCT = _f("MAX_POSITION_PCT", _DEFAULTS["MAX_POSITION_PCT"])  # max equity in one coin
MAX_POSITIONS = _i("MAX_POSITIONS", _DEFAULTS["MAX_POSITIONS"])
MIN_ORDER_USDT = _f("MIN_ORDER_USDT", 6)
DAILY_LOSS_LIMIT = _f("DAILY_LOSS_LIMIT", _DEFAULTS["DAILY_LOSS_LIMIT"])  # stop buying for the day
MAX_DRAWDOWN = _f("MAX_DRAWDOWN", _DEFAULTS["MAX_DRAWDOWN"])  # stop buying for good
STOP_ATR = _f("STOP_ATR", _DEFAULTS["STOP_ATR"])
TRAIL_START_ATR = _f("TRAIL_START_ATR", _DEFAULTS["TRAIL_START_ATR"])
MIN_STOP_PCT = _f("MIN_STOP_PCT", _DEFAULTS["MIN_STOP_PCT"])
MAX_STOP_PCT = _f("MAX_STOP_PCT", _DEFAULTS["MAX_STOP_PCT"])
MAX_HOLD_HOURS = _f("MAX_HOLD_HOURS", _DEFAULTS["MAX_HOLD_HOURS"])
COOLDOWN_HOURS = _f("COOLDOWN_HOURS", _DEFAULTS["COOLDOWN_HOURS"])  # don't rebuy right after selling

# --- loop ---
CYCLE_SECONDS = _i("CYCLE_SECONDS", _DEFAULTS["CYCLE_SECONDS"])

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
