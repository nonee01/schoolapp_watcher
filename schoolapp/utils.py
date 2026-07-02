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

from .render import console, err_console  # themed: stdout=data, stderr=chrome

try:
    import keyring
except Exception:  # optional
    keyring = None

# Logging level control
LOG_LEVEL_NAME = os.environ.get("SCHOOLAPP_LOG_LEVEL", "INFO").upper()
_LEVELS = {"DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40}
LOG_LEVEL = _LEVELS.get(LOG_LEVEL_NAME, 20)

# When quiet, banner + logs (the stderr "chrome") are silenced; command results
# on stdout are unaffected.
QUIET = os.environ.get("SCHOOLAPP_QUIET", "").lower() in ("1", "true", "yes")


def set_quiet(value: bool) -> None:
    global QUIET
    QUIET = value


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
    if QUIET:
        return
    err_console.print("[bold cyan]SchoolApp[/bold cyan] [dim]semester CLI[/dim]")


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
    if num < LOG_LEVEL or QUIET:
        return
    color = palette.get(level_up, "white")
    # Logs are chrome -> stderr, so they never pollute piped stdout / --json.
    err_console.print(f"[dim][{stamp}][/dim] [{color}]{level_up}[/{color}] {message}")


def _create_env_from_example_in_dir(base_dir: Path) -> bool:
    """If `.env` is missing and `.env.example` exists, copy the example.

    Returns True if a file was created, False otherwise.
    """
    try:
        env = base_dir / ".env"
        example = base_dir / ".env.example"
        if env.exists() or not example.exists():
            return False
        env.write_bytes(example.read_bytes())
        try:
            env.chmod(0o600)
        except Exception:
            pass
        console.print(f"[yellow]Created {env} from {example}[/yellow]")
        return True
    except Exception:
        console.print(f"[red]Failed to create .env from .env.example in {base_dir}[/red]")
        return False


def load_env_file(path: str | None) -> None:
    """Load KEY=VALUE lines into `os.environ` without overriding existing env.

    If `path` is provided, attempt to load that file. If `path` is None, the
    function will try to auto-discover an env file by checking the current
    working directory for `.env` then `.env.example`, and also probing the
    project/package root for the same files. Before loading, if `.env` is
    missing but `.env.example` exists the function will create `.env` by
    copying the example (permissions attempted to be set to 0o600).
    The first existing file found is loaded.
    """
    candidates: list[Path] = []
    project_root: Path | None = None

    if path:
        candidates.append(Path(path))
    else:
        # Try copying from .env.example in current working dir first
        try:
            _create_env_from_example_in_dir(Path.cwd())
        except Exception:
            pass

        # Prefer local .env, then .env.example in the current working dir
        candidates.append(Path(".env"))
        candidates.append(Path(".env.example"))

        # Also check the package/project tree for a .env / .env.example
        try:
            pkg_root = Path(__file__).resolve().parent
            for parent in [pkg_root, *pkg_root.parents]:
                if (parent / "pyproject.toml").exists() or (parent / "setup.py").exists():
                    project_root = parent
                    candidates.append(parent / ".env")
                    candidates.append(parent / ".env.example")
                    break
            else:
                project_root = pkg_root
                candidates.append(pkg_root / ".env")
                candidates.append(pkg_root / ".env.example")
        except Exception:
            project_root = None

        # Also try copying from .env.example in the project root
        if project_root is not None:
            try:
                _create_env_from_example_in_dir(project_root)
            except Exception:
                pass

    for env_path in candidates:
        if not env_path or not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        # Stop after loading the first valid env file
        return


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
