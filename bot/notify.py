"""Telegram alerts. Silent no-op until TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are set."""
import json
import logging
import urllib.request

from . import config

log = logging.getLogger("bot")


# Buttons under the chat box; each one sends its own label as a message.
KEYBOARD = {
    "keyboard": [["📊 الحالة", "📜 الصفقات"], ["⏸ وگف الشراء", "▶️ كمّل الشراء"], ["🧪 اختبار", "❓ مساعدة"]],
    "resize_keyboard": True,
}


def api(method, payload, timeout=10):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def enabled():
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID)


def send(text):
    if not enabled():
        return
    try:
        api("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "reply_markup": KEYBOARD})
    except Exception as e:
        # A Telegram outage must never stop trading.
        log.warning("telegram failed: %s", e)
