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
    """Root of the on-disk store: $XDG_STATE_HOME/schoolapp, defaulting to
    ~/.local/state/schoolapp when XDG_STATE_HOME is unset."""
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
    """Envelope path for a resource name ("student/profile" -> .../student/profile.json)."""
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


def documents_dir(directory: Path | None = None) -> Path:
    """Directory that cached document PDFs are stored under."""
    return (directory or state_dir()) / "documents"


def document_path(filename: str, directory: Path | None = None) -> Path:
    """Path a cached document's PDF would live at (existence not checked)."""
    return documents_dir(directory) / filename


def save_document(filename: str, content: bytes, directory: Path | None = None) -> Path:
    """Cache a downloaded PDF so /api/documents/<kind> can serve it offline."""
    path = document_path(filename, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)
    return path


# StudentData attribute -> per-resource envelope name (shared by CLI + watcher + API).
RESOURCE_FILES = {
    "profile": "student/profile",
    "element_grades": "student/elements",
    "module_grades": "student/modules",
    "semester_results": "student/semesters",
    "year_results": "student/years",
    "diploma": "student/diploma",
    "absences": "student/absences",
    "absence_summary": "student/absence_summary",
    "sanctions": "student/sanctions",
    "courses": "student/courses",
    "stats": "student/stats",
    "documents": "student/documents",
}


def save_student_data(data, *, source: str = "fetch_all", directory: Path | None = None) -> None:
    """Persist a StudentData bundle: student/all plus one envelope per resource."""
    save_resource("student/all", data, source=source, directory=directory)
    for attr, name in RESOURCE_FILES.items():
        save_resource(name, getattr(data, attr), source=source, directory=directory)


def changes_path(directory: Path | None = None) -> Path:
    """The watcher's changes.jsonl (legacy format, one JSON object per line)."""
    return (directory or state_dir()) / "changes.jsonl"


def read_changes(*, limit: int = 50, since: str | None = None,
                 type: str | None = None, directory: Path | None = None) -> list[dict]:
    """Newest-first change history; [] when the file is absent. Feeds
    /api/changes and `schoolapp changes` (spec §5)."""
    try:
        text = changes_path(directory).read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if type and entry.get("type") != type:
            continue
        if since and str(entry.get("ts", "")) <= since:
            continue
        out.append(entry)
    out.reverse()
    return out[:limit] if limit and limit > 0 else out


def freshness(names: list[str], directory: Path | None = None) -> dict[str, str | None]:
    """{resource name: fetched_at | None} — feeds /api/status `resources` (spec §8.1)."""
    out: dict[str, str | None] = {}
    for name in names:
        envelope = load_resource(name, directory)
        out[name] = envelope.get("fetched_at") if envelope else None
    return out
