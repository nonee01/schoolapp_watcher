from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
from rich.panel import Panel
from rich.table import Table

from . import store
from .client import (
    ELEMENTS_PATH,
    LOGIN_PATH,
    MODULES_PATH,
    SCHOOLAPP_BASE,
    SchoolAppClient,
    extract_csrf as _extract_csrf,
    looks_like_login_page as _looks_like_login_page,
)
from .emailer import send_email
from .extractors import parse_element_grades, parse_module_grades
from .extractors._tables import (
    extract_table as _extract_table,
    fingerprint as _fingerprint,
    normalize_cell as _normalize_cell,
)
from .models import Absence, ModuleGrade, Sanction, SemesterResult
from .presets import modules_for_semester
from .calculator import _to_float, _calc_element_grade, _calc_element_rattrapage
from .utils import console, log

MARKS_PATH = ELEMENTS_PATH  # legacy name, kept for external callers


@dataclass
class Snapshot:
    headers: list[str]
    rows: list[list[str]]
    fingerprint: str
    extras: dict | None = None


_STATE_FIELDS = ("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")


def _marks_state(headers: list[str], rows: list[list[str]], semester: str) -> dict:
    """Per-element mark values for this semester's modules, ignoring row order
    and cosmetic columns, so only real grade changes count as a change."""
    if "CodeElem" not in headers:
        return {"__rows__": [list(r) for r in rows]}

    idx = {h: i for i, h in enumerate(headers)}
    try:
        prefixes = {m.code.upper() for m in modules_for_semester(semester)}
    except Exception:
        prefixes = set()

    ci = idx["CodeElem"]
    state: dict[str, dict[str, str]] = {}
    for r in rows:
        if len(r) <= ci:
            continue
        code = r[ci].strip()
        if not code:
            continue
        if prefixes and not any(code.upper().startswith(p) for p in prefixes):
            continue
        cells: dict[str, str] = {}
        for field in _STATE_FIELDS:
            i = idx.get(field)
            cells[field] = r[i].strip() if i is not None and i < len(r) else ""
        state[code] = cells
    return state


def _snapshot_path(semester: str, state_file: str | None) -> Path:
    if state_file:
        return Path(state_file)
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "schoolapp"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{semester.lower()}_snapshot.json"


def _history_path(semester: str, state_file: str | None) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "schoolapp"
    base.mkdir(parents=True, exist_ok=True)
    return base / "changes.jsonl"


def _append_history(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_snapshot(path: Path) -> Snapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Snapshot(headers=data.get("headers", []), rows=data.get("rows", []), fingerprint=data.get("fingerprint", ""), extras=data.get("extras"))


def _save_snapshot(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"headers": snap.headers, "rows": snap.rows, "fingerprint": snap.fingerprint, "extras": snap.extras or {}}, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _render_grouped_marks(headers: list[str], rows: list[list[str]], semester: str) -> bool:
    if "CodeElem" not in headers:
        return False

    index = {h: i for i, h in enumerate(headers)}
    metrics = ["AU", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    row_by_code = {r[index["CodeElem"]]: r for r in rows if len(r) > index["CodeElem"]}

    def value(row: list[str], key: str) -> str:
        i = index.get(key)
        if i is None or i >= len(row):
            return "--"
        cell = row[i].strip()
        return cell if cell else "--"

    modules = modules_for_semester(semester)
    console.print(Panel.fit(f"{semester} - Notes des éléments (grouped by module)", border_style="cyan"))

    known_codes: set[str] = set()
    non_validated: list[str] = []
    for module in modules:
        module_table = Table(
            title=f"{module.code} - {module.title}",
            show_header=True,
            header_style="bold magenta",
        )
        module_table.add_column("CodeElem", style="bold cyan")
        module_table.add_column("Intitule")
        for metric in metrics:
            module_table.add_column(metric, justify="center")

        for element in module.elements:
            row = row_by_code.get(element.code, [])
            known_codes.add(element.code)

            values = [value(row, metric) if row else "--" for metric in metrics]
            if values[-1] == "VORD":
                values[-1] = "[green]VORD[/green]"
            elif values[-1] == "RAT":
                values[-1] = "[yellow]RAT[/yellow]"

            module_table.add_row(element.code, element.title, *values)

        console.print(module_table)

        # Compute module-level status using available scraped values and presets
        module_marks: dict[str, float] = {}
        for el in module.elements:
            r = row_by_code.get(el.code, [])
            def getf(k: str) -> float | None:
                if not r:
                    return None
                return _to_float(value(r, k))

            cc = getf("CC")
            ex = getf("EX")
            tp = getf("TP")
            rat = getf("RAT")

            if cc is not None:
                module_marks[f"{el.code}.cc"] = cc
            if ex is not None:
                module_marks[f"{el.code}.ecrit"] = ex
                module_marks[f"{el.code}.ex"] = ex
            if tp is not None:
                module_marks[f"{el.code}.tp"] = tp
            if rat is not None:
                module_marks[f"{el.code}.rat"] = rat

        # If we have at least one element mark, estimate module averages
        if module_marks:
            pts_ord = pts_ratt = pts_final = 0.0
            for el in module.elements:
                ordg = _calc_element_grade(el, module_marks)
                rattg = _calc_element_rattrapage(el, module_marks, ordg)
                finalg = max(ordg, rattg)
                pts_ord += ordg * el.coef_eelem
                pts_ratt += rattg * el.coef_eelem
                pts_final += finalg * el.coef_eelem

            mod_avg_ord = pts_ord / (module.coef_mod or 1.0)
            mod_avg_ratt = pts_ratt / (module.coef_mod or 1.0)
            mod_avg_final = pts_final / (module.coef_mod or 1.0)
            if mod_avg_ord < module.seuil <= mod_avg_ratt:
                mod_avg_final = module.seuil

            # ENSAM labels
            if mod_avg_ord >= module.seuil:
                mlabel = "VORD"
                mstyle = "green"
            elif mod_avg_ratt >= module.seuil:
                mlabel = "RAT"
                mstyle = "yellow"
            else:
                mlabel = "NV"
                mstyle = "red"
                non_validated.append(module.code)

            console.print(Panel.fit(f"Module {module.code}: {mlabel} - Ord {mod_avg_ord:.2f} / RATT {mod_avg_ratt:.2f} / Final {mod_avg_final:.2f}", border_style=mstyle))

    # Only show unknown rows that appear to belong to this semester's modules
    module_prefixes = {m.code.upper() for m in modules}
    unknown_rows: list[list[str]] = []
    for r in rows:
        if len(r) <= index["CodeElem"]:
            continue
        code = str(r[index["CodeElem"]]).strip()
        if not code:
            continue
        if code in known_codes:
            continue
        # include only if code prefix matches a module of this semester
        if any(code.upper().startswith(prefix) for prefix in module_prefixes):
            unknown_rows.append(r)
    if unknown_rows:
        extra = Table(title="Other elements", header_style="bold")
        for h in headers[:12]:
            extra.add_column(h or " ")
        for row in unknown_rows[:15]:
            padded = (row + [""] * 12)[:12]
            extra.add_row(*[(cell if cell else "--") for cell in padded])
        console.print(extra)

    # Summary of non validés modules
    if non_validated:
        console.print(Panel.fit(f"Modules non validés: {len(non_validated)} - {', '.join(non_validated)}", border_style="red"))
    else:
        console.print(Panel.fit("Modules non validés: 0", border_style="green"))

    return True


def _render_table(headers: list[str], rows: list[list[str]], semester: str) -> None:
    if _render_grouped_marks(headers, rows, semester):
        return

    table = Table(show_header=True, header_style="bold")
    for h in headers[:12]:
        table.add_column(h or " ")
    for row in rows[:15]:
        padded = (row + [""] * 12)[:12]
        table.add_row(*[(cell if cell else "--") for cell in padded])
    console.print(table)


def _render_consolidated_snapshot(headers: list[str], rows: list[list[str]], semester: str) -> None:
    """Render a single consolidated table from a snapshot, filtering elements by semester module prefixes."""
    if "CodeElem" not in headers:
        return
    index = {h: i for i, h in enumerate(headers)}
    modules = modules_for_semester(semester)
    module_prefixes = {m.code.upper() for m in modules}

    # Build element lookup by code
    element_lookup: dict[str, str] = {}
    for mod in modules:
        for el in mod.elements:
            element_lookup[el.code.upper()] = el.title

    def get_cell(row: list[str], key: str) -> str:
        i = index.get(key)
        if i is None or i >= len(row):
            return "--"
        cell = row[i].strip()
        return cell if cell else "--"

    table = Table(title=f"{semester.upper()} - Consolidated marks table", header_style="bold magenta", show_lines=False)
    table.add_column("Code", style="bold cyan", no_wrap=True)
    table.add_column("Element", overflow="fold")
    table.add_column("CC", justify="center", style="cyan")
    table.add_column("EX", justify="center", style="cyan")
    table.add_column("TP", justify="center", style="cyan")
    table.add_column("Moy SO", justify="center", style="green")
    table.add_column("RAT", justify="center", style="yellow")
    table.add_column("Moy SR", justify="center", style="magenta")
    table.add_column("Moy", justify="center", style="bold green")
    table.add_column("Status", justify="center", style="bold")

    for r in rows:
        if len(r) <= index["CodeElem"]:
            continue
        code = str(r[index["CodeElem"]]).strip()
        if not code:
            continue
        # filter by semester prefixes
        if not any(code.upper().startswith(pref) for pref in module_prefixes):
            continue
        
        # Get element title from presets
        intitule = element_lookup.get(code.upper(), "Unknown element")
        
        # Build row with proper values
        cc = get_cell(r, "CC")
        ex = get_cell(r, "EX")
        tp = get_cell(r, "TP")
        moyso = get_cell(r, "MoySO")
        rat = get_cell(r, "RAT")
        moysr = get_cell(r, "MoySR")
        moy = get_cell(r, "Moy")
        dec = get_cell(r, "Dec")
        
        # Color status based on value
        if dec == "VORD":
            dec_styled = "[green]VORD[/green]"
        elif dec == "RAT":
            dec_styled = "[yellow]RAT[/yellow]"
        elif dec == "NV":
            dec_styled = "[red]NV[/red]"
        else:
            dec_styled = dec
        
        table.add_row(code, intitule, cc, ex, tp, moyso, rat, moysr, moy, dec_styled)

    console.print(table)


def _is_validated(moy: str) -> bool:
    try:
        return float(moy.rstrip("*")) >= 11.0
    except (ValueError, AttributeError):
        return False


def _status_style(moy: str) -> tuple[str, str, str]:
    """Return (color, background, label) based on moyenne value vs 11 threshold."""
    try:
        val = float(moy.rstrip("*"))
        if val >= 11.0:
            return "#166534", "#dcfce7", "✓ Validé"
        return "#991b1b", "#fee2e2", "✗ Non validé"
    except (ValueError, AttributeError):
        return "#374151", "#f3f4f6", "En attente"


def _compute_moy(code: str, cc: str, ex: str, tp: str, element_defs: dict) -> str:
    """Calculate moyenne from available marks using preset weights when site shows '--'."""
    from .calculator import _to_float
    defn = element_defs.get(code.upper())
    if defn is None:
        return "--"
    cc_f = _to_float(cc)
    ex_f = _to_float(ex)
    tp_f = _to_float(tp)
    # Need at least EX or TP to compute anything meaningful
    if ex_f is None and tp_f is None:
        return "--"
    cc_val = cc_f if cc_f is not None else 0.0
    denom = defn.coef_ecrit + defn.coef_tp
    if tp_f is not None and denom > 0:
        ex_combined = ((ex_f or 0.0) * defn.coef_ecrit + tp_f * defn.coef_tp) / denom
    else:
        ex_combined = ex_f if ex_f is not None else 0.0
    moy = cc_val * defn.coef_cc + ex_combined * defn.coef_ex
    return f"{moy:.2f}*"


def _score_cell(label: str, value: str) -> str:
    is_estimated = value.endswith("*")
    display = value
    color = "#111827" if not is_estimated else "#2563eb"
    return f"""
    <td style="text-align:center;padding:8px 6px;">
      <div style="font-size:11px;color:#6b7280;margin-bottom:2px;">{label}</div>
      <div style="font-weight:600;font-size:15px;color:{color};">{display}</div>
    </td>"""


def _card_new(code: str, title: str, cc: str, ex: str, tp: str, moy: str) -> str:
    fg, bg, status_label = _status_style(moy)
    return f"""
<div style="background:#ffffff;border-radius:12px;padding:16px;margin-bottom:12px;border-left:4px solid {fg};box-shadow:0 1px 3px rgba(0,0,0,.08);">
  <div style="font-size:13px;color:#6b7280;margin-bottom:2px;">{code} &nbsp;·&nbsp; <span style="color:#2563eb;font-weight:600;">NOUVEAU</span></div>
  <div style="font-size:17px;font-weight:700;color:#111827;margin-bottom:12px;">{title}</div>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      {_score_cell("CC", cc)}
      {_score_cell("EX", ex)}
      {_score_cell("TP", tp)}
      {_score_cell("Moyenne", moy)}
    </tr>
  </table>
  <div style="margin-top:12px;display:inline-block;background:{bg};color:{fg};font-weight:700;font-size:13px;padding:4px 12px;border-radius:20px;">{status_label}</div>
</div>"""


def _card_updated(code: str, title: str, cc: str, ex: str, tp: str, moy: str, diffs: dict[str, tuple[str, str]]) -> str:
    fg, bg, status_label = _status_style(moy)
    diff_rows = []
    field_labels = {"CC": "CC", "EX": "EX", "TP": "TP", "Moy": "Moyenne", "MoySO": "Moy. ordinaire", "RAT": "Rattrapage", "MoySR": "Moy. rattrapage"}
    for field, (old_val, new_val) in diffs.items():
        if field == "Dec":
            continue
        diff_rows.append(f'<tr><td style="color:#6b7280;font-size:12px;padding:3px 0;width:70px;">{field_labels.get(field, field)}</td><td style="padding:3px 0;font-weight:600;">{old_val} -> {new_val}</td></tr>')

    return f"""
<div style="background:#ffffff;border-radius:12px;padding:16px;margin-bottom:12px;border-left:4px solid {fg};box-shadow:0 1px 3px rgba(0,0,0,.08);">
  <div style="font-size:13px;color:#6b7280;margin-bottom:2px;">{code} &nbsp;·&nbsp; <span style="color:#d97706;font-weight:600;">MODIFIÉ</span></div>
  <div style="font-size:17px;font-weight:700;color:#111827;margin-bottom:12px;">{title}</div>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      {_score_cell("CC", cc)}
      {_score_cell("EX", ex)}
      {_score_cell("TP", tp)}
      {_score_cell("Moyenne", moy)}
    </tr>
  </table>
  <div style="margin-top:12px;border-top:1px solid #f3f4f6;padding-top:10px;">
    <table style="width:100%;border-collapse:collapse;">{"".join(diff_rows)}</table>
  </div>
  <div style="margin-top:10px;display:inline-block;background:{bg};color:{fg};font-weight:700;font-size:13px;padding:4px 12px;border-radius:20px;">{status_label}</div>
</div>"""


def _compute_module_moy(mod, new_by_code: dict, idx: dict, element_defs: dict) -> tuple[str, bool]:
    """Return (moyenne_str, is_partial). is_partial when some elements have no grades yet."""
    from .calculator import _to_float

    def cell(row: list[str], key: str) -> str:
        i = idx.get(key)
        if i is None or i >= len(row):
            return "--"
        v = row[i].strip()
        return v if v else "--"

    pts = 0.0
    missing_coef = 0.0
    has_any = False

    for el in mod.elements:
        row = new_by_code.get(el.code)
        if row is None:
            missing_coef += el.coef_eelem
            continue

        # Use site Moy if available, otherwise compute
        site_moy = cell(row, "Moy")
        if site_moy != "--":
            try:
                pts += float(site_moy) * el.coef_eelem
                has_any = True
                continue
            except ValueError:
                pass

        el_moy = _compute_moy(el.code, cell(row, "CC"), cell(row, "EX"), cell(row, "TP"), element_defs)
        if el_moy == "--":
            missing_coef += el.coef_eelem
            continue
        try:
            pts += float(el_moy.rstrip("*")) * el.coef_eelem
            has_any = True
        except ValueError:
            missing_coef += el.coef_eelem

    if not has_any:
        return "--", False

    avg = pts / (mod.coef_mod or 1.0)
    is_partial = missing_coef > 0
    return f"{avg:.2f}{'*' if is_partial else ''}", is_partial


def _module_summary_card(mod_title: str, mod_code: str, moy: str, seuil: float) -> str:
    fg, bg, status_label = _status_style(moy)
    is_partial = moy.endswith("*")
    moy_display = moy if moy != "--" else "-"
    note = " <span style='font-size:11px;color:#6b7280;'>(partielle)</span>" if is_partial else ""
    return f"""
<div style="background:{bg};border-radius:10px;padding:12px 16px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="font-size:11px;color:{fg};opacity:0.8;margin-bottom:2px;">{mod_code} · seuil {seuil:.0f}/20</div>
    <div style="font-size:14px;font-weight:700;color:{fg};">Module : {mod_title}</div>
    <div style="font-size:13px;color:{fg};margin-top:2px;">{status_label}</div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:11px;color:{fg};opacity:0.8;">Moyenne</div>
    <div style="font-size:24px;font-weight:800;color:{fg};">{moy_display}{note}</div>
  </div>
</div>"""


def _html_wrap(semester: str, cards_html: str, heading: str = "Nouvelles notes disponibles") -> str:
    ts = datetime.now().strftime("%d %b %Y, %H:%M")
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:520px;margin:0 auto;padding:16px;">
  <div style="background:#1e40af;border-radius:12px;padding:16px 20px;margin-bottom:16px;">
    <div style="color:#bfdbfe;font-size:12px;margin-bottom:2px;">SchoolApp · {semester}</div>
    <div style="color:#ffffff;font-size:20px;font-weight:700;">{heading}</div>
    <div style="color:#93c5fd;font-size:12px;margin-top:4px;">{ts}</div>
  </div>
  {cards_html}
  <div style="text-align:center;color:#9ca3af;font-size:11px;margin-top:16px;">SchoolApp Watcher · ENSAM UMI</div>
</div>
</body>
</html>"""


# ---------- Extra watchers: absences, sanctions, official module & semester results ----------


# ── legacy extras blob adapters ──────────────────────────────────────────
# The snapshot's extras dict is a frozen cache format (api.py + old snapshots on
# disk read it); these rebuild it byte-for-byte from the library's typed models.
# tests/test_watcher_wiring.py pins parity against the original parsing algorithm.

def _absences_blob(items: list[Absence]) -> dict[str, dict[str, str]]:
    return {
        f"{a.element}|{a.date}|{a.seance}": {
            "element": a.element,
            "date": a.date,
            "seance": a.seance,
            "justif": a.raw.get("Justif", "").lower(),
            "remarks": a.remarks,
        }
        for a in items
    }


def _sanctions_blob(items: list[Sanction]) -> dict[str, str]:
    return {s.key: s.value for s in items}


def _modules_blob(items: list[ModuleGrade]) -> dict[str, dict[str, str]]:
    return {
        f"{m.code}|{m.au}": {"code": m.code, "au": m.au, "moy": m.moy, "dec": m.decision}
        for m in items
    }


def _semesters_blob(items: list[SemesterResult]) -> dict[str, dict[str, str]]:
    return {
        f"{s.niveau}|{s.semestre}|{s.au}": {
            "niveau": s.niveau,
            "sem": s.semestre,
            "au": s.au,
            "moy": s.moy_sem,
            "dec": s.decision,
            "rank": s.classement,
            "pj": s.pj,
        }
        for s in items
    }


def _all_titles() -> tuple[dict[str, str], dict[str, str]]:
    """Element and module titles across both semesters."""
    elements: dict[str, str] = {}
    modules: dict[str, str] = {}
    for sem in ("S3", "S4"):
        try:
            for m in modules_for_semester(sem):
                modules[m.code.upper()] = m.title
                for e in m.elements:
                    elements[e.code.upper()] = e.title
        except Exception:
            pass
    return elements, modules


def _dec_badge(dec: str) -> tuple[str, str, str]:
    """Color/label for an official decision code (VORD/VRAT/VRAC/NV/--)."""
    d = (dec or "").upper().strip()
    if d.startswith("V"):
        return "#166534", "#dcfce7", f"✓ {d}"
    if d == "NV":
        return "#991b1b", "#fee2e2", "✗ NV"
    return "#374151", "#f3f4f6", d if d and d != "--" else "En attente"


def _simple_card(border: str, kicker_html: str, title: str, body_html: str) -> str:
    return f"""
<div style="background:#ffffff;border-radius:12px;padding:16px;margin-bottom:12px;border-left:4px solid {border};box-shadow:0 1px 3px rgba(0,0,0,.08);">
  <div style="font-size:13px;color:#6b7280;margin-bottom:2px;">{kicker_html}</div>
  <div style="font-size:17px;font-weight:700;color:#111827;margin-bottom:8px;">{title}</div>
  {body_html}
</div>"""


def _diff_absence_cards(old_log: dict | None, new_log: dict, old_sanc: dict | None, new_sanc: dict, element_titles: dict[str, str]) -> tuple[list[str], str | None]:
    cards: list[str] = []
    subject: str | None = None

    if old_log is not None:
        for key, a in new_log.items():
            old_a = old_log.get(key)
            title = element_titles.get(a["element"].upper(), a["element"])
            justified = a.get("justif") == "true"
            if old_a is None:
                fg = "#166534" if justified else "#991b1b"
                bg = "#dcfce7" if justified else "#fee2e2"
                badge = "Justifiée" if justified else "Non justifiée"
                body = (
                    f"<div style='font-size:14px;color:#374151;'>{a['date']} · {a['seance']}</div>"
                    f"<div style='margin-top:8px;display:inline-block;background:{bg};color:{fg};font-weight:700;font-size:13px;padding:4px 12px;border-radius:20px;'>{badge}</div>"
                )
                if a.get("remarks"):
                    body += f"<div style='font-size:12px;color:#6b7280;margin-top:6px;'>{a['remarks']}</div>"
                cards.append(_simple_card(fg, f"{a['element']} · <span style='color:#dc2626;font-weight:600;'>ABSENCE</span>", title, body))
                if subject is None:
                    subject = f"🚨 Absence {'justifiée' if justified else 'non justifiée'} - {title}"
            elif old_a.get("justif") != a.get("justif") and justified:
                body = f"<div style='font-size:14px;color:#374151;'>{a['date']} · {a['seance']} - désormais justifiée</div>"
                cards.append(_simple_card("#166534", f"{a['element']} · <span style='color:#16a34a;font-weight:600;'>ABSENCE JUSTIFIÉE</span>", title, body))
                subject = subject or f"Absence justifiée - {title}"

    if old_sanc is not None and new_sanc and new_sanc != old_sanc:
        rows_html = "".join(
            (
                f"<tr><td style='color:#6b7280;font-size:12px;padding:3px 0;'>{k}</td>"
                f"<td style='padding:3px 0;font-weight:600;'>{old_sanc.get(k, '-')} -> {v}</td></tr>"
                if old_sanc.get(k) != v
                else f"<tr><td style='color:#6b7280;font-size:12px;padding:3px 0;'>{k}</td><td style='padding:3px 0;'>{v}</td></tr>"
            )
            for k, v in new_sanc.items()
        )
        cards.append(_simple_card(
            "#dc2626",
            "<span style='color:#dc2626;font-weight:600;'>SANCTIONS ABSENCES</span>",
            new_sanc.get("Message", "Mise à jour"),
            f"<table style='width:100%;border-collapse:collapse;'>{rows_html}</table>",
        ))
        subject = subject or f"⚠️ Sanction absences: {new_sanc.get('Message', 'mise à jour')}"

    return cards, subject


def _diff_module_cards(old_mods: dict | None, new_mods: dict, module_titles: dict[str, str]) -> tuple[list[str], str | None]:
    cards: list[str] = []
    subject: str | None = None
    if old_mods is None:
        return cards, subject
    for key, m in new_mods.items():
        o = old_mods.get(key)
        if o == m:
            continue
        fg, bg, label = _dec_badge(m.get("dec", ""))
        title = module_titles.get(m["code"].upper(), m["code"])
        before = "" if o is None else f"<div style='font-size:12px;color:#6b7280;margin-top:6px;'>Avant: Moy {o.get('moy', '-')} · {o.get('dec', '-')}</div>"
        body = (
            "<table style='width:100%;border-collapse:collapse;'><tr>"
            + _score_cell("Moyenne", m.get("moy") or "--")
            + f"<td style='text-align:center;padding:8px 6px;'><div style='font-size:11px;color:#6b7280;margin-bottom:2px;'>Décision</div>"
            + f"<div style='display:inline-block;background:{bg};color:{fg};font-weight:700;font-size:13px;padding:3px 10px;border-radius:20px;'>{label}</div></td>"
            + "</tr></table>" + before
        )
        cards.append(_simple_card(fg, f"{m['code']} · {m.get('au', '')} · <span style='color:#7c3aed;font-weight:600;'>RÉSULTAT MODULE OFFICIEL</span>", title, body))
        if subject is None:
            subject = f"Résultat module: {title} - {m.get('dec', '?')} ({m.get('moy', '?')})"
    return cards, subject


def _diff_semester_cards(old_sems: dict | None, new_sems: dict) -> tuple[list[str], str | None]:
    cards: list[str] = []
    subject: str | None = None
    if old_sems is None:
        return cards, subject
    for key, sres in new_sems.items():
        o = old_sems.get(key)
        if o == sres:
            continue
        fg, bg, label = _dec_badge(sres.get("dec", ""))
        body = (
            "<table style='width:100%;border-collapse:collapse;'><tr>"
            + _score_cell("Moy SEM", sres.get("moy") or "--")
            + _score_cell("Classement", sres.get("rank") or "--")
            + _score_cell("PJ", sres.get("pj") or "--")
            + f"<td style='text-align:center;padding:8px 6px;'><div style='font-size:11px;color:#6b7280;margin-bottom:2px;'>Décision</div>"
            + f"<div style='display:inline-block;background:{bg};color:{fg};font-weight:700;font-size:13px;padding:3px 10px;border-radius:20px;'>{label}</div></td>"
            + "</tr></table>"
        )
        cards.append(_simple_card("#1e40af", f"{sres.get('niveau', '')} {sres.get('sem', '')} · {sres.get('au', '')} · <span style='color:#1e40af;font-weight:600;'>RÉSULTAT SEMESTRE</span>", f"Semestre {sres.get('sem', '')}", body))
        if subject is None:
            subject = f"Résultat {sres.get('sem', '?')}: Moy {sres.get('moy', '?')} - Rang {sres.get('rank', '?')}"
    return cards, subject


def _build_diff_email(semester: str, old: Snapshot | None, new_snap: Snapshot) -> tuple[str, str]:
    """Return (subject, unwrapped cards HTML) describing grade changes."""
    from .presets import modules_for_semester

    headers = new_snap.headers
    if "CodeElem" not in headers:
        return (
            f"📚 New grade - SchoolApp {semester}",
            '<p style="color:#666;text-align:center;">SchoolApp marks changed. Check the app for details.</p>',
        )

    # Build code -> element title and def lookups from presets
    try:
        element_titles: dict[str, str] = {}
        element_defs: dict[str, object] = {}
        for mod in modules_for_semester(semester):
            for el in mod.elements:
                element_titles[el.code.upper()] = el.title
                element_defs[el.code.upper()] = el
    except Exception:
        element_titles = {}
        element_defs = {}

    def label(code: str) -> str:
        title = element_titles.get(code.upper())
        return f"{code} - {title}" if title else code

    def fmt_status(dec: str) -> str:
        if dec == "VORD":
            return "✓ Validé"
        if dec in ("NV", ""):
            return "✗ Non validé"
        if dec == "RAT":
            return "~ Rattrapage"
        return dec

    idx = {h: i for i, h in enumerate(headers)}

    def get(row: list[str], key: str) -> str:
        i = idx.get(key)
        if i is None or i >= len(row):
            return "--"
        v = row[i].strip()
        return v if v else "--"

    old_by_code: dict[str, list[str]] = {}
    if old and "CodeElem" in (old.headers or []):
        old_idx = {h: i for i, h in enumerate(old.headers)}
        ci = old_idx.get("CodeElem", 0)
        for r in old.rows:
            if len(r) > ci and r[ci].strip():
                old_by_code[r[ci].strip()] = r

    new_by_code: dict[str, list[str]] = {}
    ci = idx.get("CodeElem", 0)
    for r in new_snap.rows:
        if len(r) > ci and r[ci].strip():
            new_by_code[r[ci].strip()] = r

    # Build element -> module mapping
    try:
        all_modules = modules_for_semester(semester)
    except Exception:
        all_modules = []
    elem_to_mod: dict[str, object] = {}
    for mod in all_modules:
        for el in mod.elements:
            elem_to_mod[el.code.upper()] = mod

    # Collect changed element cards grouped by module
    from collections import defaultdict
    changed_by_mod: dict[str, list[str]] = defaultdict(list)  # mod_code -> element cards
    affected_names: list[str] = []

    for code, row in new_by_code.items():
        cc = get(row, "CC")
        ex = get(row, "EX")
        tp = get(row, "TP")
        moy = get(row, "Moy")
        title = element_titles.get(code.upper(), code)
        if moy == "--":
            moy = _compute_moy(code, cc, ex, tp, element_defs)

        mod = elem_to_mod.get(code.upper())
        if mod is None and all_modules and not any(code.upper().startswith(m.code.upper()) for m in all_modules):
            continue
        mod_code = mod.code if mod else "OTHER"

        if code not in old_by_code:
            affected_names.append(title)
            changed_by_mod[mod_code].append(_card_new(code, title, cc, ex, tp, moy))
        else:
            old_row = old_by_code[code]
            old_snap_idx = {h: i for i, h in enumerate(old.headers)} if old else idx
            def get_old(key: str) -> str:
                i = old_snap_idx.get(key)
                if i is None or i >= len(old_row):
                    return "--"
                v = old_row[i].strip()
                return v if v else "--"

            diffs: dict[str, tuple[str, str]] = {}
            for field in ("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"):
                old_val = get_old(field)
                new_val = get(row, field)
                if old_val != new_val and not (old_val == "--" and new_val == "--"):
                    diffs[field] = (old_val, new_val)
            if diffs:
                affected_names.append(title)
                changed_by_mod[mod_code].append(_card_updated(code, title, cc, ex, tp, moy, diffs))

    # Build final HTML: element cards + module summary per affected module
    mod_by_code = {mod.code: mod for mod in all_modules}
    sections: list[str] = []
    for mod_code, elem_cards in changed_by_mod.items():
        sections.extend(elem_cards)
        mod = mod_by_code.get(mod_code)
        if mod is not None:
            mod_moy, _ = _compute_module_moy(mod, new_by_code, idx, element_defs)
            sections.append(_module_summary_card(mod.title, mod.code, mod_moy, mod.seuil))

    names_str = ", ".join(affected_names[:2]) if affected_names else semester
    if len(affected_names) > 2:
        names_str += f" +{len(affected_names) - 2} more"
    subject = f"📚 {names_str} - SchoolApp {semester}"

    if not sections:
        return subject, '<p style="color:#666;text-align:center;">Something changed but could not pinpoint the diff. Check the app.</p>'

    return subject, "\n".join(sections)


def _tg_grade_section(semester: str, old: Snapshot | None, new_snap: Snapshot) -> str | None:
    from .presets import modules_for_semester

    headers = new_snap.headers
    if "CodeElem" not in headers:
        return None

    try:
        element_titles: dict[str, str] = {}
        element_defs: dict[str, object] = {}
        for mod in modules_for_semester(semester):
            for el in mod.elements:
                element_titles[el.code.upper()] = el.title
                element_defs[el.code.upper()] = el
    except Exception:
        element_titles = {}
        element_defs = {}

    idx = {h: i for i, h in enumerate(headers)}
    ci = idx.get("CodeElem", 0)

    def getv(row: list[str], hmap: dict[str, int], key: str) -> str:
        i = hmap.get(key)
        if i is None or i >= len(row):
            return "--"
        v = row[i].strip()
        return v if v else "--"

    old_by_code: dict[str, list[str]] = {}
    old_idx: dict[str, int] = {}
    if old and "CodeElem" in (old.headers or []):
        old_idx = {h: i for i, h in enumerate(old.headers)}
        oci = old_idx.get("CodeElem", 0)
        for r in old.rows:
            if len(r) > oci and r[oci].strip():
                old_by_code[r[oci].strip()] = r

    new_by_code: dict[str, list[str]] = {}
    for r in new_snap.rows:
        if len(r) > ci and r[ci].strip():
            new_by_code[r[ci].strip()] = r

    try:
        all_mods = modules_for_semester(semester)
    except Exception:
        all_mods = []

    elem_to_mod = {el.code.upper(): mod for mod in all_mods for el in mod.elements}
    mod_by_code = {mod.code: mod for mod in all_mods}

    changed_by_mod: dict[str, list[tuple]] = {}
    for code, row in new_by_code.items():
        mod = elem_to_mod.get(code.upper())
        if not mod and all_mods and not any(code.upper().startswith(m.code.upper()) for m in all_mods):
            continue
        mod_code = mod.code if mod else "OTHER"

        cc = getv(row, idx, "CC")
        ex = getv(row, idx, "EX")
        tp = getv(row, idx, "TP")
        moy = getv(row, idx, "Moy")
        title = element_titles.get(code.upper(), code)
        if moy == "--":
            moy = _compute_moy(code, cc, ex, tp, element_defs)

        if code not in old_by_code:
            changed_by_mod.setdefault(mod_code, []).append((code, title, cc, ex, tp, moy, "new", {}))
        else:
            old_row = old_by_code[code]
            diffs = {}
            for field in ("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy"):
                ov = getv(old_row, old_idx, field)
                nv = getv(row, idx, field)
                if ov != nv and not (ov == "--" and nv == "--"):
                    diffs[field] = (ov, nv)
            if diffs:
                changed_by_mod.setdefault(mod_code, []).append((code, title, cc, ex, tp, moy, "updated", diffs))

    if not changed_by_mod:
        return None

    lines = [f"📚 <b>Nouvelles notes - {semester}</b>"]
    for mod_code, elements in changed_by_mod.items():
        mod = mod_by_code.get(mod_code)
        if mod:
            lines.append(f"\n📦 <b>{mod_code}</b> - {mod.title}")
        for code, title, cc, ex, tp, moy, kind, diffs in elements:
            icon = "✅" if _is_validated(moy) else "❌" if moy not in ("--", "") else "⏳"
            kind_str = "NOUVEAU" if kind == "new" else "MODIFIÉ"
            lines.append(f"\n<b>{code}</b> - {title}  <i>({kind_str})</i>")
            lines.append(f"CC: {cc} · EX: {ex} · TP: {tp}")
            lines.append(f"Moy: <b>{moy}</b>  {icon}")
            if diffs:
                diff_parts = [f"{k}: {ov}->{nv}" for k, (ov, nv) in list(diffs.items())[:3]]
                lines.append(f"<i>{' · '.join(diff_parts)}</i>")
        if mod:
            mod_moy, _ = _compute_module_moy(mod, new_by_code, idx, element_defs)
            mod_icon = "✅" if _is_validated(mod_moy) else "❌" if mod_moy not in ("--", "") else "⏳"
            lines.append(f"-> Moy. module: <b>{mod_moy}</b>  {mod_icon}")

    return "\n".join(lines)


def _tg_absence_section(
    new_abs: dict,
    old_abs: dict | None,
    new_sanc: dict,
    old_sanc: dict | None,
    el_titles: dict[str, str],
) -> str | None:
    lines: list[str] = []
    if old_abs is not None:
        for key, a in new_abs.items():
            justified = a.get("justif") == "true"
            title = el_titles.get((a.get("element") or "").upper(), a.get("element", "?"))
            if key not in old_abs:
                icon = "✅" if justified else "🚨"
                badge = "Justifiée" if justified else "Non justifiée"
                lines.append(f"{icon} <b>Absence {badge}</b>")
                lines.append(f"<b>{a.get('element', '?')}</b> - {title}")
                lines.append(f"📅 {a.get('date', '?')} · {a.get('seance', '?')}")
            elif old_abs[key].get("justif") != a.get("justif") and justified:
                lines.append("✅ <b>Absence justifiée</b>")
                lines.append(f"<b>{a.get('element', '?')}</b> - {title}")

    if old_sanc is not None and new_sanc and new_sanc != old_sanc:
        if lines:
            lines.append("")
        lines.append("⚠️ <b>Sanctions mises à jour</b>")
        for k, v in new_sanc.items():
            if old_sanc.get(k) != v:
                lines.append(f"{k}: {old_sanc.get(k, '-')} -> {v}")

    return "\n".join(lines) if lines else None


def _tg_module_section(new_mods: dict, old_mods: dict | None, mod_titles: dict) -> str | None:
    if old_mods is None:
        return None
    lines: list[str] = []
    for key, m in new_mods.items():
        if old_mods.get(key) == m:
            continue
        dec = (m.get("dec") or "").upper()
        icon = "✅" if dec.startswith("V") else "❌" if dec == "NV" else "⏳"
        title = mod_titles.get((m.get("code") or "").upper(), m.get("code", "?"))
        lines.append(f"📋 <b>Résultat module officiel</b>")
        lines.append(f"<b>{m.get('code', '?')}</b> - {title}")
        lines.append(f"Moy: <b>{m.get('moy', '--')}</b>  {icon} {dec or '--'}")
    return "\n".join(lines) if lines else None


def _tg_semester_section(new_sems: dict, old_sems: dict | None) -> str | None:
    if old_sems is None:
        return None
    lines: list[str] = []
    for key, s in new_sems.items():
        if old_sems.get(key) == s:
            continue
        dec = (s.get("dec") or "").upper()
        icon = "✅" if dec.startswith("V") else "❌" if dec == "NV" else "⏳"
        lines.append(f"🎓 <b>Résultat semestre</b>")
        lines.append(f"{s.get('niveau', '')} {s.get('sem', '')} · {s.get('au', '')}")
        lines.append(f"Moy: <b>{s.get('moy', '--')}</b>  Rang: <b>{s.get('rank', '--')}</b>")
        lines.append(f"{icon} {dec or '--'}")
    return "\n".join(lines) if lines else None


def check_once(*, email: str, password: str, timeout: int, semester: str, state_file: str | None, notify_email: bool, config: dict | None, notify_telegram: bool = False, session: requests.Session | None = None) -> int:
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": "schoolapp-cli/0.2"})

    client = SchoolAppClient(session=session, timeout=timeout)
    client.set_credentials(email, password)

    # Pre-flight the marks page: bad credentials fail here after a single login
    # attempt (as before), instead of once per resource inside fetch_all.
    marks_url = f"{SCHOOLAPP_BASE}{MARKS_PATH}"
    log("INFO", f"GET {marks_url}")
    marks_html = client.get_page(MARKS_PATH)
    log("SUCCESS", "Fetched marks page")
    headers, rows = _extract_table(marks_html)

    log("INFO", "Fetching remaining student resources (library fetch_all)")
    data = client.fetch_all()
    for name, err in data.errors.items():
        log("WARNING", f"Could not fetch {name}: {err}")

    path = _snapshot_path(semester, state_file)
    old = _load_snapshot(path)
    grades_changed = old is None or _marks_state(old.headers, old.rows, semester) != _marks_state(headers, rows, semester)

    # Extra pages: absences, sanctions, official module & semester results.
    # None means the fetch failed - carry the previous cached blob forward.
    # Modules are re-parsed from the encours page bytes because data.module_grades
    # merges in past-year rows, which must not enter the legacy blob.
    mods_blob = None
    if "module_grades" not in data.errors and MODULES_PATH in client.last_pages:
        mods_blob = _modules_blob(parse_module_grades(client.last_pages[MODULES_PATH]))
    fetched: dict[str, dict | None] = {
        "absences": None if "absences" in data.errors else _absences_blob(data.absences),
        "sanctions": None if "sanctions" in data.errors else _sanctions_blob(data.sanctions),
        "modules": mods_blob,
        "semesters": None if "semester_results" in data.errors else _semesters_blob(data.semester_results),
    }
    extras_old = old.extras if old and isinstance(old.extras, dict) else {}
    extras_new: dict[str, dict | None] = {}
    for key, value in fetched.items():
        extras_new[key] = extras_old.get(key) if value is None else value

    el_titles, mod_titles = _all_titles()
    abs_cards, abs_subj = _diff_absence_cards(
        extras_old.get("absences"), extras_new.get("absences") or {},
        extras_old.get("sanctions"), extras_new.get("sanctions") or {},
        el_titles,
    )
    mod_cards, mod_subj = _diff_module_cards(extras_old.get("modules"), extras_new.get("modules") or {}, mod_titles)
    sem_cards, sem_subj = _diff_semester_cards(extras_old.get("semesters"), extras_new.get("semesters") or {})
    extra_cards = abs_cards + mod_cards + sem_cards

    snap = Snapshot(headers=headers, rows=rows, fingerprint=_fingerprint(headers, rows), extras=extras_new)
    _save_snapshot(path, snap)

    # Per-resource envelopes for the new API endpoints (spec §8.3). A store write
    # failure must not cost the notification below.
    try:
        store.save_student_data(data, source="watcher")
    except Exception as exc:  # noqa: BLE001
        log("WARNING", f"Could not persist resource store: {exc}")

    changed = grades_changed or bool(extra_cards)

    if changed:
        if grades_changed:
            log("SUCCESS", f"Grade change detected for {semester}. Snapshot updated at {path}")
            _render_table(headers, rows, semester)
        if abs_cards:
            log("SUCCESS", f"Absence/sanction update detected ({len(abs_cards)} item(s))")
        if mod_cards:
            log("SUCCESS", f"Official module result update detected ({len(mod_cards)} item(s))")
        if sem_cards:
            log("SUCCESS", f"Semester result update detected ({len(sem_cards)} item(s))")

        if notify_email:
            sections: list[str] = []
            subjects: list[str] = []
            if grades_changed:
                g_subj, g_cards = _build_diff_email(semester, old, snap)
                sections.append(g_cards)
                subjects.append(g_subj)
            for subj, cards in ((abs_subj, abs_cards), (mod_subj, mod_cards), (sem_subj, sem_cards)):
                if cards:
                    sections.append("\n".join(cards))
                    if subj:
                        subjects.append(subj)
            subject = subjects[0] if subjects else f"SchoolApp {semester} - mise à jour"
            if len(subjects) > 1:
                subject += f" (+{len(subjects) - 1})"
            heading = "Nouvelles notes disponibles" if grades_changed else "Mises à jour SchoolApp"
            html = _html_wrap(semester, "\n".join(sections), heading=heading)
            send_email(
                subject=subject,
                body=f"SchoolApp {semester} update. Open in an HTML email viewer to see details.",
                html=html,
                config=config,
            )
            log("SUCCESS", "Email notification sent")

        if notify_telegram:
            tg_parts: list[str] = []
            if grades_changed:
                s = _tg_grade_section(semester, old, snap)
                if s:
                    tg_parts.append(s)
            if abs_cards:
                s = _tg_absence_section(
                    extras_new.get("absences") or {},
                    extras_old.get("absences"),
                    extras_new.get("sanctions") or {},
                    extras_old.get("sanctions"),
                    el_titles,
                )
                if s:
                    tg_parts.append(s)
            if mod_cards:
                s = _tg_module_section(extras_new.get("modules") or {}, extras_old.get("modules"), mod_titles)
                if s:
                    tg_parts.append(s)
            if sem_cards:
                s = _tg_semester_section(extras_new.get("semesters") or {}, extras_old.get("semesters"))
                if s:
                    tg_parts.append(s)
            if tg_parts:
                try:
                    from .telegram_notifier import send_telegram
                    send_telegram("\n\n".join(tg_parts), config=config)
                    log("SUCCESS", "Telegram notification sent")
                except Exception as exc:
                    log("WARNING", f"Telegram notification failed: {exc}")

        hist_path = _history_path(semester, state_file)
        if grades_changed:
            _append_history(hist_path, {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "type": "grades",
                "semester": semester,
                "summary": f"Notes mises à jour - {semester}",
            })
        for _htype, _hcards, _hsubj in [
            ("absences", abs_cards, abs_subj),
            ("modules", mod_cards, mod_subj),
            ("semesters", sem_cards, sem_subj),
        ]:
            if _hcards:
                _append_history(hist_path, {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "type": _htype,
                    "semester": semester,
                    "summary": _hsubj or f"{_htype.title()} update",
                })
    else:
        log("INFO", f"No change detected for {semester}")

    return 1 if changed else 0


def run_health_check(*, email: str, password: str, timeout: int) -> dict[str, str | int | bool]:
    """Run a non-destructive connectivity/auth check against SchoolApp."""
    session = requests.Session()
    session.headers.update({"User-Agent": "schoolapp-cli/0.2"})

    login_url = f"{SCHOOLAPP_BASE}{LOGIN_PATH}"
    marks_url = f"{SCHOOLAPP_BASE}{MARKS_PATH}"

    result: dict[str, str | int | bool] = {
        "ok": False,
        "login_http": 0,
        "auth_http": 0,
        "marks_http": 0,
        "rows": 0,
        "message": "",
    }

    r = session.get(login_url, timeout=timeout)
    result["login_http"] = r.status_code
    r.raise_for_status()

    csrf = _extract_csrf(r.text)
    if not csrf:
        result["message"] = "CSRF token missing on login page"
        return result

    payload = {"email": email, "password": password, "_csrf": csrf}
    posted = session.post(login_url, data=payload, timeout=timeout)
    result["auth_http"] = posted.status_code
    posted.raise_for_status()

    page = session.get(marks_url, timeout=timeout)
    result["marks_http"] = page.status_code
    page.raise_for_status()

    if _looks_like_login_page(page.text):
        result["message"] = "Authentication failed: still on login page"
        return result

    headers, rows = _extract_table(page.text)
    result["rows"] = len(rows)
    result["ok"] = True
    result["message"] = f"Connected successfully, parsed {len(rows)} rows"
    # Keep one extra useful field for diagnostics
    result["has_codeelem"] = "CodeElem" in headers
    return result


def fetch_element_details(*, email: str, password: str, timeout: int, element_code: str, eval_kind: str = "all") -> dict | None:
    """Fetch statistics popup data for a specific element (CC/EX/TP/Moy)."""
    client = SchoolAppClient(timeout=timeout)
    client.session.headers.update({"User-Agent": "schoolapp-cli/0.2"})
    log("INFO", f"Authenticating as {email}")
    client.login(email, password)
    log("SUCCESS", "Authenticated")

    stats = client.mark_statistics(element_code, eval_kind=eval_kind)
    if not stats:
        return None

    grades = parse_element_grades(client.last_pages.get(ELEMENTS_PATH, ""))
    target = next((g for g in grades if g.code.upper() == element_code.upper()), None)

    return {
        "element_code": element_code,
        "data": list(target.raw.values()) if target else [],
        "stats": [
            {
                "eval": s.eval_kind,
                "title": s.title or f"Statistiques {s.eval_kind} - {element_code.upper()}",
                "rows": s.rows,
            }
            for s in stats
        ],
    }


SLOW_WINDOW = (4, 6)  # local hours with reduced polling
SLOW_INTERVAL = 1800
ALERT_AFTER_SECONDS = 3600


def _scheduled_interval(fast: int) -> float:
    """Fast interval all day; slow between 04:00 and 06:00 local, with jitter."""
    base = SLOW_INTERVAL if SLOW_WINDOW[0] <= datetime.now().hour < SLOW_WINDOW[1] else fast
    return max(30.0, base + random.uniform(-30, 30))


def _try_notify(config: dict | None, enabled: bool, subject: str, text: str, notify_telegram: bool = False) -> bool:
    sent = False
    if enabled:
        try:
            send_email(subject=subject, body=text, html=f"<p>{text}</p>", config=config)
            sent = True
        except Exception as exc:
            log("WARNING", f"Could not send alert email: {exc}")
    if notify_telegram:
        try:
            from .telegram_notifier import send_telegram
            send_telegram(f"<b>{subject}</b>\n{text}", config=config)
            sent = True
        except Exception as exc:
            log("WARNING", f"Could not send Telegram alert: {exc}")
    return sent


def watch_loop(*, email: str, password: str, timeout: int, semester: str, state_file: str | None, interval: int, notify_email: bool, config: dict | None, notify_telegram: bool = False) -> int:
    log("INFO", f"Watching {semester}: every {interval}s (every {SLOW_INTERVAL // 60} min between {SLOW_WINDOW[0]:02d}:00-{SLOW_WINDOW[1]:02d}:00)")
    session = requests.Session()
    session.headers.update({"User-Agent": "schoolapp-cli/0.2"})

    failures = 0
    first_failure: float | None = None
    alerted = False
    last_error = ""

    try:
        while True:
            try:
                check_once(
                    email=email,
                    password=password,
                    timeout=timeout,
                    semester=semester,
                    state_file=state_file,
                    notify_email=notify_email,
                    notify_telegram=notify_telegram,
                    config=config,
                    session=session,
                )
                if alerted:
                    _try_notify(config, notify_email, "✅ SchoolApp watcher recovered", "Grade checks are succeeding again.", notify_telegram=notify_telegram)
                failures = 0
                first_failure = None
                alerted = False
            except requests.RequestException as exc:
                failures += 1
                first_failure = first_failure or time.time()
                last_error = str(exc)
                log("WARNING", f"Network error ({failures} consecutive): {exc}")
            except Exception as exc:
                failures += 1
                first_failure = first_failure or time.time()
                last_error = str(exc)
                log("ERROR", f"Check failed ({failures} consecutive): {exc}")

            if failures and not alerted and first_failure and time.time() - first_failure >= ALERT_AFTER_SECONDS:
                alerted = _try_notify(
                    config,
                    notify_email,
                    "⚠️ SchoolApp watcher is failing",
                    f"Grade checks have been failing for over an hour ({failures} attempts). Last error: {last_error}",
                    notify_telegram=notify_telegram,
                )

            sleep_s = _scheduled_interval(interval)
            if failures:
                sleep_s = max(sleep_s, min(interval * 2 ** min(failures, 5), 1800.0))
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        console.print(Panel.fit("Stopped watch mode"))
        return 0
