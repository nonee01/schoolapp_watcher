"""Design-token contract (spec §3). One JSON consumed by every frontend:
render.py (rich styles), watcher.py emails (hexes), Android Theme.kt and the
plasmoid Theme.qml (parity tests read the same file from the repo)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("design_tokens.json")

COMPUTED_MARKER = "*"


@lru_cache(maxsize=1)
def load_tokens() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def color(name: str) -> dict:
    """{'hex', 'hex_bg', 'rich'} for a semantic color name."""
    return load_tokens()["colors"][name]


STATUS_BADGES: dict[str, dict] = {}
RESOURCES: list[dict] = []


def _init() -> None:
    data = load_tokens()
    STATUS_BADGES.update(data["statuses"])
    RESOURCES.extend(data["resources"])


_init()
