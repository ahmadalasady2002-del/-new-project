"""Telegram alerts. Silent no-op until TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are set."""
import json
import logging
import urllib.request

from . import config

log = logging.getLogger("bot")


def send(text):
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    try:
        body = json.dumps({"chat_id": config.TELEGRAM_CHAT_ID, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as e:
        # A Telegram outage must never stop trading.
        log.warning("telegram failed: %s", e)
