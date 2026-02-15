from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(subject: str, body: str, *, config: dict | None = None) -> None:
    cfg = config or {}
    smtp_cfg = cfg.get("smtp", {}) if isinstance(cfg, dict) else {}

    host = smtp_cfg.get("host") or os.environ.get("SMTP_HOST")
    port = int(smtp_cfg.get("port") or os.environ.get("SMTP_PORT") or 0)
    username = smtp_cfg.get("username") or os.environ.get("SMTP_USERNAME")
    password = smtp_cfg.get("password") or os.environ.get("SMTP_PASSWORD")
    from_addr = smtp_cfg.get("from") or os.environ.get("SMTP_FROM")
    to_addr = smtp_cfg.get("to") or os.environ.get("SMTP_TO")

    if not all([host, port, username, password, from_addr, to_addr]):
        raise RuntimeError("SMTP config missing. Set SMTP_* env vars or ~/.schoolapp/config.toml [smtp].")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=context)
            server.login(username, password)
            server.send_message(msg)
