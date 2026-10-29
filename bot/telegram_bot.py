"""Control the bot from Telegram. Only the chat in TELEGRAM_CHAT_ID is obeyed."""
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from . import config, data, notify

log = logging.getLogger("bot")

MODES = {"meme": "الميم", "lotto": "اليانصيب", "safe": "الهادئ"}

HELP = """🤖 أوامر البوت

📊 الحالة: الرصيد والعملات اللي ماسكها هسه
📜 الصفقات: آخر الصفقات والربح الكلي
⏸ وگف الشراء: ما يشتري شي جديد، بس يكمل يدير العملات اللي عنده
▶️ كمّل الشراء: يرجع يشتري
🧪 اختبار: يجرب الوضع الحالي على أسعار آخر 30 يوم
🎟 اختبار اليانصيب: يجرب اليانصيب على آخر 120 يوم

أوامر تكتبها:
/mode lotto أو /mode meme أو /mode safe: يغيّر الوضع
/test lotto: يجرب اليانصيب على آخر 120 يوم
/sellall: يبيع كل العملات هسه"""

BUTTONS = {
    "📊 الحالة": "/status", "📜 الصفقات": "/trades", "⏸ وگف الشراء": "/pause",
    "▶️ كمّل الشراء": "/resume", "🧪 اختبار": "/test", "🎟 اختبار اليانصيب": "/test lotto",
    "❓ مساعدة": "/help",
}


class Commands:
    def __init__(self, state, broker, lock):
        self.state, self.broker, self.lock = state, broker, lock
        self.test_proc = None
        self.confirm_sellall_until = 0

    def run(self):
        offset = None
        while True:
            try:
                params = {"timeout": 25, "allowed_updates": ["message"]}
                if offset is not None:
                    params["offset"] = offset
                else:
                    params["offset"] = -1  # first call: skip messages sent while the bot was down
                updates = notify.api("getUpdates", params, timeout=35).get("result", [])
                for u in updates:
                    if offset is None:
                        offset = u["update_id"] + 1
                        continue
                    offset = u["update_id"] + 1
                    msg = u.get("message") or {}
                    if str(msg.get("chat", {}).get("id")) != str(config.TELEGRAM_CHAT_ID):
                        continue  # strangers who find the bot get nothing
                    reply = self.handle(msg.get("text", ""))
                    if reply:
                        notify.send(reply)
                if offset is None:
                    offset = 0
            except Exception as e:
                log.warning("telegram commands: %s", e)
                time.sleep(10)

    def handle(self, text):
        text = BUTTONS.get(text.strip(), text.strip())
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        handler = {
            "/status": self.status, "/trades": self.trades, "/pause": self.pause, "/resume": self.resume,
            "/test": self.test, "/mode": self.mode, "/sellall": self.sellall, "/help": lambda _: HELP,
            "/start": lambda _: HELP,
        }.get(cmd)
        if not handler:
            handler = self.guess(text)
        if not handler:
            return "ما فهمت 🤔 دوس أحد الأزرار، أو اكتب /help"
        try:
            return handler(arg.strip().lower())
        except Exception as e:
            log.exception("command %s failed", cmd)
            return f"⚠️ صار خطأ: {e}"

    def guess(self, text):
        """Plain questions like "كم المبلغ الحالي" map to the matching button."""
        lotto_words = ("يانصيب", "لوتو", "lotto")
        if any(w in text for w in ("جرب", "اختبر", "اختبار", "تست")):
            return (lambda _: self.test("lotto")) if any(w in text for w in lotto_words) else self.test
        if any(w in text for w in ("حول", "حوّل", "غير", "غيّر", "شغل", "شغّل")):
            for mode, keys in (("lotto", lotto_words), ("meme", ("ميم", "meme")), ("safe", ("هادئ", "هادي", "safe"))):
                if any(k in text for k in keys):
                    return lambda _, m=mode: self.mode(m)
        words = {
            self.status: ("مبلغ", "رصيد", "فلوس", "حالة", "شلون", "الوضع", "ربح", "خسر", "كم"),
            self.trades: ("صفقات", "صفقة", "اشترى", "باع"),
            (lambda _: HELP): ("مساعدة", "اوامر", "أوامر", "شتسوي", "شنو تگدر"),
        }
        for handler, keys in words.items():
            if any(k in text for k in keys):
                return handler
        return None

    def status(self, _):
        px = {t["symbol"]: float(t["lastPrice"]) for t in data.tickers_24h()}
        with self.lock:
            st = self.state
            cash = self.broker.cash()
            positions = dict(st["positions"])
            eq = cash + sum(p["qty"] * px.get(s, p["entry"]) for s, p in positions.items())
            start, day_start = st.get("start_equity", eq), st.get("day_start_equity", eq)
            paused, halted = st.get("paused"), st.get("halted")
        lines = [
            f"📊 الحالة ({'💵 فلوس حقيقية' if self.broker.live else '🧪 فلوس وهمية'}، وضع {MODES.get(config.STRATEGY, config.STRATEGY)})",
            f"💰 الرصيد: {eq:.2f}$",
            f"{'📈' if eq >= start else '📉'} من البداية: {eq - start:+.2f}$ ({eq / start - 1:+.1%})",
            f"📅 اليوم: {eq - day_start:+.2f}$",
            f"💵 كاش: {cash:.2f}$",
        ]
        if halted:
            lines.append("⛔ البوت واگف شراء لأن الخسارة وصلت الحد")
        elif paused:
            lines.append("⏸ الشراء واگف بطلبك")
        if positions:
            lines.append("")
            lines.append(f"⏳ ماسك {len(positions)} عملات:")
            for s, p in positions.items():
                now = px.get(s, p["entry"])
                change = now / p["entry"] - 1
                lines.append(f"  {'🟢' if change >= 0 else '🔴'} {s[:-4]}: {change:+.1%} (حاط {p['cost']:.2f}$)")
        else:
            lines.append("⏳ ما ماسك ولا عملة هسه")
        return "\n".join(lines)

    def trades(self, _):
        with self.lock:
            trades = list(self.state["trades"])
        if not trades:
            return "📜 لحد هسه ما سوى ولا صفقة"
        total = sum(t["pnl"] for t in trades)
        wins = sum(t["pnl"] > 0 for t in trades)
        lines = [f"📜 {len(trades)} صفقة، ربحت منها {wins} ({wins / len(trades):.0%})",
                 f"{'📈 الربح' if total >= 0 else '📉 الخسارة'} الكلي: {total:+.2f}$", "", "آخر الصفقات:"]
        for t in trades[-10:][::-1]:
            when = datetime.fromtimestamp(t["closed"], timezone.utc).strftime("%m-%d %H:%M")
            lines.append(f"{'🟢' if t['pnl'] > 0 else '🔴'} {t['symbol'][:-4]} {t['pnl']:+.2f}$  ({when})")
        return "\n".join(lines)

    def pause(self, _):
        with self.lock:
            self.state["paused"] = True
            self._save()
        return "⏸ وگفت الشراء. العملات اللي عندي أكمل أديرها وأبيعها بوقتها.\nحتى أرجع أشتري دوس ▶️ كمّل الشراء"

    def resume(self, _):
        with self.lock:
            self.state.pop("paused", None)
            self._save()
        return "▶️ رجعت أدور على فرص وأشتري"

    def test(self, arg):
        if self.test_proc and self.test_proc.poll() is None:
            return "🧪 أكو اختبار شغال هسه، انتظره يخلص"
        args = ["--lotto", "--days", "120"] if arg == "lotto" else ["--days", "30"]
        self.test_proc = subprocess.Popen([sys.executable, "-m", "bot.backtest", *args], cwd=config.ROOT,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "🧪 بديت الاختبار، النتيجة توصلك هنا بعد كم دقيقة"

    def mode(self, arg):
        if arg not in MODES:
            return "اكتب وحدة من هذني:\n/mode meme\n/mode lotto\n/mode safe"
        script = "/usr/local/bin/bot-mode"
        if not os.path.exists(script):
            return "⚠️ اكتب bot-update بـ Termius أول"
        notify.send(f"🔄 دا أحول البوت لوضع {MODES[arg]}...")
        with self.lock:  # hold the lock so the main loop can't save over the moved state file
            out = subprocess.run([script, arg], capture_output=True, text=True)
        # On success the service restarts and the new process says hello; we only get here on failure.
        if "holds coins" in out.stdout:
            return "⚠️ ما گدرت أحول: البوت ماسك عملات بفلوس حقيقية. انتظر لحد ما يبيعهن."
        return f"⚠️ ما گدرت أحول:\n{out.stdout or out.stderr}"

    def sellall(self, arg):
        with self.lock:
            if not self.state["positions"]:
                return "ما ماسك ولا عملة"
            if arg != "yes" or time.time() > self.confirm_sellall_until:
                if arg == "yes":
                    return "انتهى وقت التأكيد، اكتب /sellall مرة ثانية"
                self.confirm_sellall_until = time.time() + 60
                return (f"⚠️ متأكد تريد أبيع كل العملات ({len(self.state['positions'])}) هسه؟\n"
                        f"إذا متأكد اكتب: /sellall yes")
            from .main import close_position
            px = {t["symbol"]: float(t["lastPrice"]) for t in data.tickers_24h()}
            for sym in list(self.state["positions"]):
                close_position(self.state, self.broker, sym, px.get(sym, self.state["positions"][sym]["entry"]),
                               "manual")
            self._save()
        return "✅ بعت كل العملات"

    def _save(self):
        from .main import save_state
        save_state(self.state)
