from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from .presets import ElementDef, ModuleDef, modules_for_semester
from .utils import console


TARGET_AVG = 10.0


def _prompt_mark(label: str) -> float | None:
    while True:
        raw = Prompt.ask(label + " (0-20, blank=skip)", default="").strip()
        if raw == "":
            return None
        try:
            val = float(raw)
        except ValueError:
            console.print("[red]Invalid number[/red]")
            continue
        if 0.0 <= val <= 20.0:
            return val
        console.print("[red]Value must be between 0 and 20[/red]")


def _calc_element_grade(defn: ElementDef, marks: dict[str, float]) -> float:
    cc = marks.get(f"{defn.code}.cc", 0.0)
    if f"{defn.code}.ecrit" in marks or f"{defn.code}.tp" in marks:
        ecrit = marks.get(f"{defn.code}.ecrit", 0.0)
        tp = marks.get(f"{defn.code}.tp", 0.0)
        denom = defn.coef_ecrit + defn.coef_tp
        ex = (ecrit * defn.coef_ecrit + tp * defn.coef_tp) / denom if denom > 0 else 0.0
    else:
        ex = marks.get(f"{defn.code}.ex", 0.0)
    return cc * defn.coef_cc + ex * defn.coef_ex


def _calc_element_rattrapage(defn: ElementDef, marks: dict[str, float], ordinary_grade: float) -> float:
    rat_key = f"{defn.code}.rat"
    if rat_key not in marks:
        return ordinary_grade

    cc = marks.get(f"{defn.code}.cc", 0.0)
    rat = marks[rat_key]
    weighted_rat = cc * defn.coef_cc + rat * defn.coef_ex
    rat_session = max(weighted_rat, rat)
    return max(ordinary_grade, rat_session)


def _to_float(value: str) -> float | None:
    raw = value.strip()
    if not raw or raw == "--":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _default_snapshot_path(semester: str) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "schoolapp"
    return base / f"{semester.lower()}_snapshot.json"


def _marks_from_snapshot(semester: str, snapshot_file: str | None) -> dict[str, float]:
    path = Path(snapshot_file) if snapshot_file else _default_snapshot_path(semester)
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    if not isinstance(headers, list) or not isinstance(rows, list):
        return {}

    index = {str(h): i for i, h in enumerate(headers)}
    if "CodeElem" not in index:
        return {}

    marks: dict[str, float] = {}

    def get(row: list[str], key: str) -> float | None:
        i = index.get(key)
        if i is None or i >= len(row):
            return None
        return _to_float(str(row[i]))

    for row in rows:
        if not isinstance(row, list) or index["CodeElem"] >= len(row):
            continue
        code = str(row[index["CodeElem"]]).strip()
        if not code:
            continue

        cc = get(row, "CC")
        ex = get(row, "EX")
        tp = get(row, "TP")
        rat = get(row, "RAT")

        if cc is not None:
            marks[f"{code}.cc"] = cc
        if ex is not None:
            marks[f"{code}.ecrit"] = ex
            marks[f"{code}.ex"] = ex
        if tp is not None:
            marks[f"{code}.tp"] = tp
        if rat is not None:
            marks[f"{code}.rat"] = rat

    if marks:
        console.print(Panel.fit(f"Loaded marks from snapshot: {path}", border_style="cyan"))

    return marks


def list_modules(semester: str, single_table: bool = False,
                 show_module: str | None = None, coefs: bool = False) -> None:
    """Modules and elements, showing what each assessment is actually worth.

    The default columns are the share of the element decided by the tests
    (contrôle continu), the exam and the TP — they sum to 100%. The raw
    CoefCC/CoefEX/CoefEcrit/CoefTP behind them are shown with `--coefs`;
    on their own they mislead, because CoefCC 0.3 on an element with a TP
    is 20% of the mark, not 30%.
    """
    from . import academics as ac

    modules = modules_for_semester(semester)
    console.print(Panel.fit(f"{semester.upper()} - Modules et éléments", border_style="cyan"))

    show_module_norm = show_module.strip().upper() if show_module else None

    def columns(table: Table, with_module: bool) -> None:
        if with_module:
            table.add_column("Module", style="bold")
        table.add_column("CodeElem", style="bold cyan")
        table.add_column("Intitule")
        if coefs:
            for c in ("CoefCC", "CoefEX", "CoefEcrit", "CoefTP"):
                table.add_column(c, justify="right")
        table.add_column("Test", justify="right")
        table.add_column("Exam", justify="right")
        table.add_column("TP", justify="right")
        table.add_column("CoefElem", justify="right")

    def row(table: Table, module, el, with_module: bool) -> None:
        sh = ac.element_shares(el)
        cells = [module.code] if with_module else []
        cells += [el.code, el.title]
        if coefs:
            cells += [f"{el.coef_cc:.2f}", f"{el.coef_ex:.2f}",
                      f"{el.coef_ecrit:.2f}", f"{el.coef_tp:.2f}"]
        def pct(v: float, style: str | None = None) -> Text:
            txt = "--" if v == 0 else f"{v:.0%}"
            return Text(txt, style=style or ("muted" if v == 0 else ""))
        # The TP is the only component with no second session (art. 8).
        cells += [pct(sh["test"]), pct(sh["exam"]),
                  pct(sh["tp"], "rat" if sh["tp"] else "muted"),
                  f"{el.coef_eelem:.2f}"]
        table.add_row(*cells)

    if single_table:
        table = Table(title=f"{semester.upper()} - Modules et éléments (consolidated)",
                      header_style="bold magenta")
        columns(table, with_module=True)
        for module in modules:
            if show_module_norm and module.code.upper() != show_module_norm:
                continue
            for el in module.elements:
                row(table, module, el, with_module=True)
        console.print(table)
        console.print("[muted]Test / Exam / TP = part de l'élément décidée par chacun "
                      "(somme 100%). Le TP ne se rattrape jamais (art. 8).[/muted]")
        return

    for module in modules:
        if show_module_norm and module.code.upper() != show_module_norm:
            continue
        table = Table(
            title=f"{module.code} - {module.title} (CoefMod {module.coef_mod:.2f})",
            header_style="bold magenta",
        )
        columns(table, with_module=False)
        for el in module.elements:
            row(table, module, el, with_module=False)
        console.print(table)

    console.print("[muted]Test / Exam / TP = part de l'élément décidée par chacun "
                  "(somme 100%). Le TP ne se rattrape jamais (art. 8).[/muted]")


def run_calculator(
    semester: str,
    marks_file: str | None = None,
    snapshot_file: str | None = None,
    ask_missing: bool = False,
    ask_rattrapage: bool = False,
) -> int:
    modules = modules_for_semester(semester)
    marks: dict[str, float] = _marks_from_snapshot(semester, snapshot_file)

    if marks_file:
        data = json.loads(Path(marks_file).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("marks file must be a JSON object")
        file_marks = {str(k): float(v) for k, v in data.items()}
        marks.update(file_marks)

    summary = Table(title=f"Calculator {semester.upper()} (Ordinaire + Rattrapage)", header_style="bold")
    summary.add_column("Module")
    summary.add_column("Ord", justify="right")
    summary.add_column("RATT", justify="center")
    summary.add_column("Final", justify="right")
    summary.add_column("Status")

    sem_points_ord = 0.0
    sem_points_final = 0.0
    sem_weight = sum(m.coef_mod for m in modules) or 1.0
    known_points_final = 0.0
    known_weight = 0.0

    target_avg = min((m.seuil for m in modules), default=TARGET_AVG)
    interactive = sys.stdin.isatty()

    non_validated_codes: list[str] = []

    for mod in modules:
        module_points_ord = 0.0
        module_points_ratt = 0.0
        module_points_final = 0.0
        module_known = True

        console.print(Panel.fit(f"{mod.code} - {mod.title}"))
        for el in mod.elements:
            cc_key = f"{el.code}.cc"
            ex_key = f"{el.code}.ex"
            ecrit_key = f"{el.code}.ecrit"
            tp_key = f"{el.code}.tp"
            rat_key = f"{el.code}.rat"

            if cc_key not in marks and el.coef_cc > 0:
                if ask_missing and interactive:
                    value = _prompt_mark(f"{el.code} CC")
                    if value is not None:
                        marks[cc_key] = value
                    else:
                        module_known = False
                else:
                    module_known = False

            has_tp_weight = el.coef_tp > 0
            if has_tp_weight:
                if ecrit_key not in marks:
                    if ask_missing and interactive:
                        value = _prompt_mark(f"{el.code} EX (écrit)")
                        if value is not None:
                            marks[ecrit_key] = value
                        else:
                            module_known = False
                    else:
                        module_known = False
                if tp_key not in marks:
                    if ask_missing and interactive:
                        value = _prompt_mark(f"{el.code} TP")
                        if value is not None:
                            marks[tp_key] = value
                        else:
                            module_known = False
                    else:
                        module_known = False
            else:
                if ex_key not in marks and ecrit_key not in marks:
                    if ask_missing and interactive:
                        value = _prompt_mark(f"{el.code} EX")
                        if value is not None:
                            marks[ex_key] = value
                        else:
                            module_known = False
                    else:
                        module_known = False

            if ask_rattrapage and interactive and rat_key not in marks:
                rat_value = _prompt_mark(f"{el.code} RATT")
                if rat_value is not None:
                    marks[rat_key] = rat_value

            ordinary_grade = _calc_element_grade(el, marks)
            rattrapage_grade = _calc_element_rattrapage(el, marks, ordinary_grade)
            final_grade = max(ordinary_grade, rattrapage_grade)

            module_points_ord += ordinary_grade * el.coef_eelem
            module_points_ratt += rattrapage_grade * el.coef_eelem
            module_points_final += final_grade * el.coef_eelem

            console.print(
                f"[dim]{el.code}[/dim] {el.title}: Ord [bold]{ordinary_grade:.2f}[/bold] | "
                f"RATT [bold]{rattrapage_grade:.2f}[/bold] | Final [bold]{final_grade:.2f}[/bold]"
            )

        module_avg_ord = module_points_ord / (mod.coef_mod or 1.0)
        module_avg_ratt = module_points_ratt / (mod.coef_mod or 1.0)
        module_avg_final = module_points_final / (mod.coef_mod or 1.0)

        if module_avg_ord < mod.seuil <= module_avg_ratt:
            module_avg_final = mod.seuil

        sem_points_ord += module_avg_ord * mod.coef_mod
        sem_points_final += module_avg_final * mod.coef_mod

        if module_known:
            known_points_final += module_avg_final * mod.coef_mod
            known_weight += mod.coef_mod

        # Determine ENSAM-style status labels:
        # - VORD: validated in ordinary session (Ordinaire >= seuil)
        # - RAT: validated thanks to rattrapage (Ordinaire < seuil and Rattrapage >= seuil)
        # - NV: non validé (even after rattrapage)
        vord = module_avg_ord >= mod.seuil
        ratt_valid = module_avg_ratt >= mod.seuil
        if vord:
            status_label = "VORD"
        elif ratt_valid:
            status_label = "RAT"
        else:
            status_label = "NV"

        color_map = {"VORD": "green", "RAT": "yellow", "NV": "red"}
        status = f"[{color_map[status_label]}]{status_label}[/{color_map[status_label]}]"

        ratt_values = [marks.get(f"{el.code}.rat") for el in mod.elements if f"{el.code}.rat" in marks]
        ratt_display = f"{module_avg_ratt:.2f}" if ratt_values else "--"
        summary.add_row(mod.code, f"{module_avg_ord:.2f}", ratt_display, f"{module_avg_final:.2f}", status)

        if status_label == "NV":
            non_validated_codes.append(mod.code)

    sem_avg_ord = sem_points_ord / sem_weight
    sem_avg_final = sem_points_final / sem_weight
    summary.add_row("TOTAL", f"{sem_avg_ord:.2f}", "--", f"{sem_avg_final:.2f}", "")
    console.print(summary)

    # Modules non validés summary (ENSAM wording)
    non_valid_count = len(non_validated_codes)
    if non_valid_count > 0:
        console.print(Panel.fit(f"Modules non validés: {non_valid_count} - {', '.join(non_validated_codes)}", border_style="red"))
    else:
        console.print(Panel.fit("Modules non validés: 0", border_style="green"))

    remaining_weight = max(0.0, sem_weight - known_weight)
    needed_points = target_avg * sem_weight - known_points_final
    if remaining_weight > 0:
        required_mark = needed_points / remaining_weight
        required_mark = min(20.0, max(0.0, required_mark))
        console.print(
            Panel.fit(
                f"Required average on missing modules to reach {target_avg:.0f}/20: [bold]{required_mark:.2f}[/bold]"
            )
        )
    else:
        console.print(Panel.fit("No missing modules; all marks provided."))

    console.print(Panel.fit(f"Current semester average (final): [bold]{sem_avg_final:.2f}[/bold] / 20"))
    return 0
