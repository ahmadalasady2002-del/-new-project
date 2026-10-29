"""Buy on exchange listing news.

When Binance or Upbit announces it will list a coin, that coin usually jumps on
every exchange that already trades it. This watcher polls both announcement
pages every few seconds and, for a fresh listing that Bybit already trades and
that hasn't jumped yet, buys right away. Exits are fast: the jump usually
happens in the first hours.

The two announcement pages are public website endpoints, not documented APIs,
so parsing is defensive and each source reports its health to Telegram (/news).
"""
import logging
import re
import time

from . import config, data, notify
from .strategy import Signal

log = logging.getLogger("bot")

SOURCES = {
    "binance": ("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                {"type": 1, "catalogId": 48, "pageNo": 1, "pageSize": 20}),
    "upbit": ("https://api-manager.upbit.com/api/v1/announcements",
              {"os": "web", "page": 1, "per_page": 20, "category": "trade"}),
    # Official public API: a new KRW market appearing means Upbit just listed the coin.
    # Slower than the announcement, but works from anywhere.
    "upbit_markets": ("https://api.upbit.com/v1/market/all", {"isDetails": "false"}),
}
BROWSER = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
           "Accept": "application/json", "clienttype": "web"}
UPBIT_SITE = {"Origin": "https://upbit.com", "Referer": "https://upbit.com/"}
SOURCE_AR = {"binance": "Binance", "upbit": "إعلانات Upbit", "upbit_markets": "أسواق Upbit"}
TICKER = re.compile(r"\(([A-Z0-9]{2,15})\)")
NOT_COINS = {"KRW", "BTC", "USDT", "USD", "ETH"}
MAX_NEW_PER_READ = 3


def find_articles(obj):
    """Every dict that looks like an article ({id/code, title}), wherever it sits in the JSON."""
    if isinstance(obj, dict):
        if "title" in obj and ("id" in obj or "code" in obj):
            yield obj
        for v in obj.values():
            yield from find_articles(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_articles(v)


def listing_coins(source, title):
    """Coins a spot-listing headline announces, or [] if it isn't one."""
    if source == "upbit_markets":
        return [title[4:]] if title.startswith("KRW-") else []
    if source == "binance":
        t = title.lower()
        if "will list" not in t or "alpha" in t or "futures" in t:
            return []
    elif "신규 거래지원" not in title:  # Upbit: "new trading support"
        return []
    return [c for c in TICKER.findall(title) if c not in NOT_COINS]


def fetch(source):
    url, params = SOURCES[source]
    headers = {**BROWSER, **(UPBIT_SITE if source == "upbit" else {})}
    payload = data.get_json(url, params, headers=headers, tries=1, timeout=8)
    if source == "upbit_markets":
        return [(f"{source}:{m['market']}", m["market"]) for m in payload if isinstance(m, dict) and "market" in m]
    return [(f"{source}:{a.get('id') or a.get('code')}", a["title"]) for a in find_articles(payload)]


def exits(pos, price, now):
    """Fast exits for a news pump: why to sell, or None to hold."""
    pos["highest"] = max(pos["highest"], price)
    gain = pos["highest"] / pos["entry"] - 1
    if gain >= config.ANN_TRAIL_START and price <= pos["highest"] * (1 - config.ANN_TRAIL):
        return "trail"
    if price <= pos["entry"] * (1 - config.ANN_STOP):
        return "stop"
    if now - pos["opened"] >= config.ANN_MAX_HOURS * 3600:
        return "time"
    return None


class Watcher:
    def __init__(self, state, broker, lock):
        self.state, self.broker, self.lock = state, broker, lock
        self.health = {s: {"ok": None, "checked": 0, "error": ""} for s in SOURCES}
        self.recent = []  # last listing headlines seen, newest first, for /news
        self.last_title = {}  # newest headline read from each source, to show parsing works
        self.warned = set()

    def run(self):
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("announcement watcher")
            time.sleep(config.ANN_POLL_SECONDS)

    def tick(self):
        seen = self.state.setdefault("ann_seen", {})
        for source in SOURCES:
            try:
                articles = fetch(source)
                if not articles:
                    raise ValueError("no articles in the response")
                self.health[source] = {"ok": True, "checked": time.time(), "error": ""}
            except Exception as e:
                self.health[source] = {"ok": False, "checked": time.time(), "error": str(e)[:120]}
                if source not in self.warned:
                    self.warned.add(source)
                    log.warning("announcements %s failing: %s", source, e)
                    notify.send(f"⚠️ ما گدرت أقرا إعلانات {SOURCE_AR[source]}: {str(e)[:80]}\n"
                                f"أكمل أحاول، واكتب /news حتى تشوف الحالة")
                continue
            self.warned.discard(source)
            if source != "upbit_markets":
                self.last_title[source] = articles[0][1]
            first_time = source not in seen
            known = set(seen.get(source, []))
            fresh = [(aid, title, coins) for aid, title in articles if aid not in known
                     for coins in [listing_coins(source, title)] if coins]
            # Real listings come one or two at a time. A burst means our memory of the page
            # is off (first read, or the page changed shape): resync silently instead of trading.
            act = not first_time and len(fresh) <= MAX_NEW_PER_READ
            if fresh and not act and not first_time:
                log.warning("announcements %s: %d 'new' listings at once, resyncing without trading",
                            source, len(fresh))
            for aid, title, coins in fresh:
                self.recent.insert(0, (time.time(), source, title, coins))
                del self.recent[10:]
                if act:
                    for coin in coins:
                        self.on_listing(source, coin, title)
            ids = [a for a, _ in articles]
            with self.lock:
                # Keep every id on the page (Upbit's market list has hundreds), plus older ones.
                seen[source] = (ids + [a for a in seen.get(source, []) if a not in ids])[:max(len(ids), 200) + 200]
        self.manage()

    def on_listing(self, source, coin, title):
        from .main import open_position, save_state
        symbol = f"{coin}USDT"
        log.info("LISTING NEWS %s: %s", source, title)
        try:
            price = data.price(symbol)
        except Exception:
            notify.send(f"📢 {SOURCE_AR[source]} أعلنت إدراج {coin}، بس هي مو موجودة على Bybit فما اشتريت")
            return
        try:
            hour = data.klines(symbol, "5m", 13)
            base = hour[0]["open"] if hour else price
        except Exception:
            base = price
        jump = price / base - 1 if base else 0
        if jump > config.ANN_MAX_JUMP:
            notify.send(f"📢 {SOURCE_AR[source]} أعلنت إدراج {coin}، بس سعرها صاعد {jump:.0%} من قبل ساعة، "
                        f"فتأخرنا وما اشتريت")
            return
        with self.lock:
            ann_open = sum(1 for p in self.state["positions"].values() if p.get("ann"))
            if symbol in self.state["positions"] or ann_open >= config.ANN_MAX_POSITIONS:
                return
            eq = self.broker.cash() + sum(p["cost"] for p in self.state["positions"].values())
            usdt = min(eq * config.ANN_POSITION_PCT, self.broker.cash() * 0.99)
            if usdt < config.MIN_ORDER_USDT:
                notify.send(f"📢 {SOURCE_AR[source]} أعلنت إدراج {coin}، بس ماكو كاش كافي")
                return
            sig = Signal(symbol, 100, price, price * 0.02, f"news {source}: {title[:80]}", ("ann", source))
            open_position(self.state, self.broker, sig, usdt, price, config.ANN_STOP, ann=True)
            save_state(self.state)

    def manage(self):
        from .main import close_position, save_state
        held = [s for s, p in self.state["positions"].items() if p.get("ann")]
        if not held:
            return
        now = time.time()
        for symbol in held:
            try:
                price = data.price(symbol)
            except Exception:
                continue
            with self.lock:
                pos = self.state["positions"].get(symbol)
                why = pos and exits(pos, price, now)
                if why:
                    close_position(self.state, self.broker, symbol, price, why)
                    save_state(self.state)

    def report(self):
        lines = ["📢 مراقب الإعلانات"]
        for source, h in self.health.items():
            if h["ok"] is None:
                state = "⏳ بعده ما فحص"
            elif h["ok"]:
                state = f"✅ شغال، آخر فحص قبل {time.time() - h['checked']:.0f} ثانية"
            else:
                state = f"❌ ما يشتغل: {h['error']}"
            lines.append(f"{SOURCE_AR[source]}: {state}")
            if source in self.last_title:
                lines.append(f"   آخر خبر قريته: {self.last_title[source][:90]}")
        lines.append("")
        if self.recent:
            lines.append("آخر إعلانات إدراج شفتها:")
            for ts, source, title, coins in self.recent[:5]:
                lines.append(f"• {SOURCE_AR[source]}: {', '.join(coins)}")
        else:
            lines.append("لحد هسه ما شفت إعلان إدراج جديد")
        return "\n".join(lines)
