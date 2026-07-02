from __future__ import annotations

import os

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"


def send_telegram(message: str, *, config: dict | None = None) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if config:
        tg = config.get("telegram", {})
        if isinstance(tg, dict):
            token = tg.get("bot_token", token)
            chat_id = tg.get("chat_id", chat_id)
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    resp = requests.post(
        f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
