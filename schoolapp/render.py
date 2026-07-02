"""Shared presentation layer for the CLI.

One theme, one set of renderers. Commands render *results* to `console` (stdout);
banner/logs/spinners/progress go to `err_console` (stderr) so `--json` output on
stdout is always clean. Renderers consume the plain envelope `data` (dicts/lists
exactly as `store.load_resource(...)["data"]` returns them), never dataclasses,
so they work identically for the CLI and any other store reader.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme({
    "ok": "bold green",
    "fail": "bold red",
    "rat": "bold yellow",
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
    "muted": "dim",
    "header": "bold magenta",
    "accent": "cyan",
})

console = Console(theme=THEME)
err_console = Console(theme=THEME, stderr=True)


# ── primitives ───────────────────────────────────────────────────────────

def status_badge(value: str | None) -> Text:
    """Colorize an official decision code (VORD/VRAT/VRAC/NV/RAT/--)."""
    v = (value or "").strip()
    up = v.upper()
    if not v or v == "--":
        return Text("--", style="muted")
    if up.startswith("V"):
        return Text(f"✓ {v}", style="ok")
    if up == "NV":
        return Text(f"✗ {v}", style="fail")
    if "RAT" in up:
        return Text(v, style="rat")
    return Text(v, style="muted")


def data_table(title: str, columns: Sequence[str], rows: Iterable[Sequence[Any]],
               *, caption: str | None = None) -> Table:
    table = Table(title=title, header_style="header", caption=caption, caption_style="muted")
    for col in columns:
        table.add_column(str(col))
    for row in rows:
        table.add_row(*[c if isinstance(c, Text) else str(c) for c in row])
    return table


def error_panel(message: str, *, hint: str | None = None) -> Panel:
    body = Text(message, style="error")
    if hint:
        body.append("\n\n")
        body.append(hint, style="muted")
    return Panel(body, title="Error", border_style="error", expand=False)


def empty_hint(resource: str) -> Panel:
    return Panel(
        Text(f"No cached {resource}.", style="warning").append(
            "\nRun `schoolapp fetch-all` (or the watcher) to populate the store.", style="muted"),
        border_style="warning", expand=False,
    )


def _cell(d: dict, *keys: str, default: str = "--") -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


# ── per-resource renderers (input = envelope `data`) ─────────────────────

def profile_view(data: dict) -> Table:
    table = data_table("Student profile", ["Field", "Value"], [])
    raw = data.get("raw") or {}
    if raw:
        for k, v in raw.items():
            table.add_row(k, str(v) if v else Text("--", style="muted"))
    else:  # fall back to the typed fields
        for k, v in data.items():
            if k in ("raw", "photo_url"):
                continue
            table.add_row(k, str(v) if v else Text("--", style="muted"))
    if data.get("photo_url"):
        table.add_row("photo_url", data["photo_url"])
    return table


def element_grades_table(items: list[dict]) -> Table:
    rows = [
        [g.get("code", ""), g.get("au", ""), _cell(g, "cc"), _cell(g, "ex"), _cell(g, "tp"),
         _cell(g, "moy"), _cell(g, "rat"), status_badge(g.get("decision"))]
        for g in items
    ]
    return data_table(f"Element grades ({len(items)})",
                      ["Code", "AU", "CC", "EX", "TP", "Moy", "RAT", "Decision"], rows)


def module_grades_table(items: list[dict]) -> Table:
    rows = [[m.get("code", ""), m.get("au", ""), _cell(m, "moy"), status_badge(m.get("decision"))]
            for m in items]
    return data_table(f"Module grades ({len(items)})", ["Code", "AU", "Moy", "Decision"], rows)


def semesters_table(items: list[dict]) -> Table:
    rows = [[s.get("niveau", ""), s.get("semestre", ""), s.get("au", ""), _cell(s, "moy_sem"),
             _cell(s, "classement"), status_badge(s.get("decision"))] for s in items]
    return data_table(f"Semester results ({len(items)})",
                      ["Niveau", "Semestre", "AU", "Moy", "Rang", "Decision"], rows)


def years_table(items: list[dict]) -> Table:
    rows = [[y.get("niveau", ""), y.get("filiere", ""), y.get("au", ""), _cell(y, "statut"),
             _cell(y, "moy_annee"), _cell(y, "classement"), status_badge(y.get("decision"))]
            for y in items]
    return data_table(f"Year results ({len(items)})",
                      ["Niveau", "Filière", "AU", "Statut", "Moy", "Rang", "Decision"], rows)


def courses_table(items: list[dict]) -> Table:
    rows = [[c.get("code_elem", ""), _cell(c, "statut"), _cell(c, "section"),
             _cell(c, "groupe"), _cell(c, "sous_groupe"), _cell(c, "num")] for c in items]
    return data_table(f"Course enrollments ({len(items)})",
                      ["Element", "Statut", "Section", "Groupe", "Sous-grp", "Num"], rows)


def absences_view(absences: list[dict], summary: list[dict], sanctions: list[dict]) -> Group:
    parts: list[Any] = []
    log_rows = [[a.get("element", ""), a.get("date", ""), a.get("seance", ""),
                 Text("oui", style="ok") if a.get("justified") else Text("non", style="fail"),
                 _cell(a, "remarks", default="")] for a in absences]
    parts.append(data_table(f"Absences ({len(absences)})",
                            ["Element", "Date", "Séance", "Justifiée", "Remarques"], log_rows))
    if summary:
        cols = list(summary[0].keys())
        parts.append(data_table("Per-element summary", cols,
                                [[r.get(c, "") for c in cols] for r in summary]))
    if sanctions:
        parts.append(data_table("Sanctions", ["", ""],
                                [[s.get("key", ""), s.get("value", "")] for s in sanctions]))
    return Group(*parts)


def stats_view(items: list[dict]) -> Group:
    parts: list[Any] = []
    for s in items:
        title = s.get("title") or f"{s.get('element', '')} · {s.get('eval_kind', '')}"
        parts.append(data_table(title, ["Metric", "Value"],
                                [[r[0], r[1]] for r in s.get("rows", []) if len(r) >= 2]))
    return Group(*parts) if parts else Group(Text("No statistics cached.", style="muted"))


def documents_table(items: list[dict], *, cached: dict[str, bool] | None = None) -> Table:
    cached = cached or {}
    rows = []
    for d in items:
        fn = d.get("filename", "")
        is_cached = cached.get(fn, d.get("cached", False))
        rows.append([d.get("kind", ""), fn,
                     Text("cached", style="ok") if is_cached else Text("not downloaded", style="muted")])
    return data_table(f"Documents ({len(items)})", ["Kind", "Filename", "Status"], rows)


def catalog_table(items: list[dict]) -> Table:
    rows = []
    for m in items:
        elems = ", ".join(e.get("code", "") for e in (m.get("elements") or []))
        rows.append([m.get("code_mod", ""), m.get("intitule", ""), m.get("niveau", ""),
                     m.get("semestre", ""), m.get("filiere", ""), _cell(m, "coef_mod"),
                     _cell(m, "seuil"), elems or Text("--", style="muted")])
    return data_table(f"Catalog modules ({len(items)})",
                      ["Code", "Intitulé", "Niveau", "Sem", "Filière", "Coef", "Seuil", "Éléments"], rows)


def filieres_table(items: list[dict]) -> Table:
    rows = [[f.get("code", ""), _cell(f, "label", "intitule", default="")] for f in items]
    return data_table(f"Filières ({len(items)})", ["Code", "Intitulé"], rows)


def freshness_table(store_dir: str, freshness: dict[str, str | None]) -> Table:
    table = data_table(f"State store: {store_dir}", ["Resource", "Fetched at (UTC)"], [])
    for name, ts in freshness.items():
        table.add_row(name, ts or Text("— not cached", style="muted"))
    return table
