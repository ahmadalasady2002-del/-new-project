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

# --- coin selection ---
MIN_QUOTE_VOLUME = _f("MIN_QUOTE_VOLUME", 20_000_000)  # 24h volume in USDT
MIN_TRENDING_VOLUME = _f("MIN_TRENDING_VOLUME", 5_000_000)
UNIVERSE_SIZE = _i("UNIVERSE_SIZE", 40)
INTERVAL = os.getenv("INTERVAL", "1h")

# --- risk ---
RISK_PER_TRADE = _f("RISK_PER_TRADE", 0.01)  # lose at most 1% of equity per trade
MAX_POSITION_PCT = _f("MAX_POSITION_PCT", 0.20)  # one coin never above 20% of equity
MAX_POSITIONS = _i("MAX_POSITIONS", 4)
MIN_ORDER_USDT = _f("MIN_ORDER_USDT", 6)
DAILY_LOSS_LIMIT = _f("DAILY_LOSS_LIMIT", 0.05)  # stop buying for the day after -5%
MAX_DRAWDOWN = _f("MAX_DRAWDOWN", 0.30)  # stop the bot completely after -30%
STOP_ATR = _f("STOP_ATR", 2.0)
TRAIL_START_ATR = _f("TRAIL_START_ATR", 1.5)
MIN_STOP_PCT = _f("MIN_STOP_PCT", 0.02)
MAX_STOP_PCT = _f("MAX_STOP_PCT", 0.08)
MAX_HOLD_HOURS = _f("MAX_HOLD_HOURS", 72)
COOLDOWN_HOURS = _f("COOLDOWN_HOURS", 12)  # don't rebuy a coin right after selling it

# --- loop ---
CYCLE_SECONDS = _i("CYCLE_SECONDS", 300)

STATE_FILE = ROOT / os.getenv("STATE_FILE", "state.json")
LOG_FILE = ROOT / os.getenv("LOG_FILE", "bot.log")

STABLECOINS = {
    "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "EUR", "AEUR", "USDE",
    "PYUSD", "USD1", "XUSD", "BFUSD", "RLUSD", "EURI", "PAXG", "WBTC", "WBETH",
    "USDQ", "USDR", "XAUT", "STETH", "METH", "CMETH",
}
