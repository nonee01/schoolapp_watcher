from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

# Layout (spec §7): $XDG_STATE_HOME/schoolapp/ (default ~/.local/state/schoolapp/)
# Every resource file is an envelope {"fetched_at", "source", "data"} written atomically.
# The legacy s4_snapshot.json / changes.jsonl are NOT managed here and keep their format.


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME", "").strip() or (Path.home() / ".local" / "state")
    return Path(base) / "schoolapp"


def _jsonable(value):
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def resource_path(name: str, directory: Path | None = None) -> Path:
    return (directory or state_dir()) / f"{name}.json"


def save_resource(name: str, data, *, source: str = "", directory: Path | None = None) -> Path:
    """Atomic envelope write; `name` may be nested ("student/profile", "catalog/modules")."""
    path = resource_path(name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "data": _jsonable(data),
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_resource(name: str, directory: Path | None = None) -> dict | None:
    """Returns the envelope ({"fetched_at", "source", "data"}) or None if absent/corrupt."""
    path = resource_path(name, directory)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return envelope if isinstance(envelope, dict) and "data" in envelope else None


def freshness(names: list[str], directory: Path | None = None) -> dict[str, str | None]:
    """{resource name: fetched_at | None} — feeds /api/status `resources` (spec §8.1)."""
    out: dict[str, str | None] = {}
    for name in names:
        envelope = load_resource(name, directory)
        out[name] = envelope.get("fetched_at") if envelope else None
    return out
