"""The design-token contract: one JSON, consumed by render (rich styles) and
watcher emails (hexes). Android/plasmoid parity tests read the same file."""

import json
from pathlib import Path

from schoolapp import render, tokens


def test_tokens_file_is_valid_and_complete():
    data = json.loads(
        (Path(tokens.__file__).with_name("design_tokens.json")).read_text(encoding="utf-8"))
    for name in ("ok", "fail", "rat", "info", "success", "warning",
                 "error", "muted", "header", "accent"):
        assert {"hex", "hex_bg", "rich"} <= set(data["colors"][name]), name
    assert data["computed_marker"] == "*"
    ids = [r["id"] for r in data["resources"]]
    assert ids[0] == "student/profile" and "student/elements" in ids and "catalog/modules" in ids
    for r in data["resources"]:
        assert r["name"] and r["icon"]


def test_render_theme_derives_from_tokens():
    for name, c in tokens.load_tokens()["colors"].items():
        assert str(render.THEME.styles[name]) == str(
            render.THEME.styles[name].__class__.parse(c["rich"]))


def test_email_palette_matches_current_look():
    # Tokens codify the exact hexes the emails already use - no visual change.
    assert tokens.color("ok")["hex"] == "#166534" and tokens.color("ok")["hex_bg"] == "#dcfce7"
    assert tokens.color("fail")["hex"] == "#991b1b" and tokens.color("fail")["hex_bg"] == "#fee2e2"
    assert tokens.color("muted")["hex"] == "#374151" and tokens.color("muted")["hex_bg"] == "#f3f4f6"
    assert tokens.color("info")["hex"] == "#6366f1"


def test_watcher_has_no_hardcoded_status_hexes():
    src = Path("schoolapp/watcher.py").read_text(encoding="utf-8")
    for hexcode in ("#166534", "#991b1b", "#374151", "#6366f1"):
        assert hexcode not in src, f"{hexcode} should come from tokens"
