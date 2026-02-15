from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None

try:
    import tomli
except Exception:  # pragma: no cover
    tomli = None

from rich.console import Console


console = Console()

try:
    import keyring
except Exception:  # optional
    keyring = None

# Logging level control
LOG_LEVEL_NAME = os.environ.get("SCHOOLAPP_LOG_LEVEL", "INFO").upper()
_LEVELS = {"DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40}
LOG_LEVEL = _LEVELS.get(LOG_LEVEL_NAME, 20)


def set_log_level(level: str) -> None:
    global LOG_LEVEL
    LOG_LEVEL = _LEVELS.get(level.upper(), LOG_LEVEL)


def get_log_level() -> int:
    return LOG_LEVEL


@dataclass
class AppContext:
    debug: bool
    config: dict[str, Any]


def banner() -> None:
    console.print("[bold cyan]SchoolApp[/bold cyan] [dim]semester CLI[/dim]")


def log(level: str, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    palette = {
        "INFO": "cyan",
        "SUCCESS": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "DEBUG": "blue",
    }
    level_up = level.upper()
    num = _LEVELS.get(level_up, 20)
    if num < LOG_LEVEL:
        return
    color = palette.get(level_up, "white")
    console.print(f"[dim][{stamp}][/dim] [{color}]{level_up}[/{color}] {message}")


def load_env_file(path: str | None) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = path.read_bytes()
    if tomllib is not None:
        return tomllib.loads(data.decode("utf-8"))
    if tomli is not None:
        return tomli.loads(data.decode("utf-8"))
    return {}


def load_config(config_path: str | None) -> dict[str, Any]:
    default_path = Path.home() / ".schoolapp" / "config.toml"
    path = Path(config_path).expanduser() if config_path else default_path
    return _read_toml(path)


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def resolve_credentials(email: str | None = None, config: dict | None = None) -> tuple[str | None, str | None]:
    """Resolve SchoolApp credentials.

    Order: explicit `email` arg -> config `schoolapp.email`/`schoolapp.password` ->
    env vars `SCHOOLAPP_EMAIL`/`SCHOOLAPP_PASSWORD` -> keyring (if available).
    Returns (email, password) or (None, None) if not found.
    """
    cfg = config.get("schoolapp", {}) if isinstance(config, dict) else {}

    resolved_email = email or cfg.get("email") or os.environ.get("SCHOOLAPP_EMAIL")
    resolved_password = cfg.get("password") or os.environ.get("SCHOOLAPP_PASSWORD")

    # Try keyring if password not provided
    if not resolved_password and keyring and resolved_email:
        try:
            kr = keyring.get_password("schoolapp", resolved_email)
            if kr:
                resolved_password = kr
        except Exception:
            pass

    return resolved_email, resolved_password
