from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from rich.panel import Panel
from rich.table import Table

from .emailer import send_email
from .presets import modules_for_semester
from .calculator import _to_float, _calc_element_grade, _calc_element_rattrapage
from .utils import console, log

SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
LOGIN_PATH = "/login"
MARKS_PATH = "/student/noteselem-encours"
STATS_PATH = "/notes-stat/elemevalsat"


@dataclass
class Snapshot:
    headers: list[str]
    rows: list[list[str]]
    fingerprint: str


def _normalize_cell(text: str) -> str:
    return " ".join(text.split())


def _extract_csrf(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    token = soup.select_one('input[name="_csrf"]')
    if not token:
        return None
    value = token.get("value")
    return value if isinstance(value, str) and value else None


def _looks_like_login_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one('form[action="/login"]') and soup.select_one('input[name="password"]'))


def _extract_table(html: str) -> tuple[list[str], list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No table found on marks page")

    best = max(tables, key=lambda t: len(t.find_all("tr")))
    headers = [_normalize_cell(th.get_text(" ", strip=True)) for th in best.find_all("th")]

    rows: list[list[str]] = []
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [_normalize_cell(td.get_text(" ", strip=True)) for td in tds]
        if any(row):
            rows.append(row)

    return headers, rows


def _fingerprint(headers: list[str], rows: list[list[str]]) -> str:
    payload = json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_path(semester: str, state_file: str | None) -> Path:
    if state_file:
        return Path(state_file)
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "schoolapp"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{semester.lower()}_snapshot.json"


def _load_snapshot(path: Path) -> Snapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Snapshot(headers=data.get("headers", []), rows=data.get("rows", []), fingerprint=data.get("fingerprint", ""))


def _save_snapshot(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"headers": snap.headers, "rows": snap.rows, "fingerprint": snap.fingerprint}, indent=2), encoding="utf-8")


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
    console.print(Panel.fit(f"{semester} — Notes des éléments (grouped by module)", border_style="cyan"))

    known_codes: set[str] = set()
    non_validated: list[str] = []
    for module in modules:
        module_table = Table(
            title=f"{module.code} — {module.title}",
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

            console.print(Panel.fit(f"Module {module.code}: {mlabel} — Ord {mod_avg_ord:.2f} / RATT {mod_avg_ratt:.2f} / Final {mod_avg_final:.2f}", border_style=mstyle))

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
        console.print(Panel.fit(f"Modules non validés: {len(non_validated)} — {', '.join(non_validated)}", border_style="red"))
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

    table = Table(title=f"{semester.upper()} — Consolidated marks table", header_style="bold magenta", show_lines=False)
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


def check_once(*, email: str, password: str, timeout: int, semester: str, state_file: str | None, notify_email: bool, config: dict | None) -> int:
    session = requests.Session()
    session.headers.update({"User-Agent": "schoolapp-cli/0.2"})

    login_url = f"{SCHOOLAPP_BASE}{LOGIN_PATH}"
    marks_url = f"{SCHOOLAPP_BASE}{MARKS_PATH}"

    r = session.get(login_url, timeout=timeout)
    log("INFO", f"GET {login_url}")
    r.raise_for_status()
    log("SUCCESS", "Fetched login page")

    csrf = _extract_csrf(r.text)
    if not csrf:
        log("ERROR", "CSRF token missing on login page")
        raise RuntimeError("Login page changed: CSRF token missing")

    payload = {"email": email, "password": password, "_csrf": csrf}
    log("INFO", f"POST {login_url} (auth) using email={email}")
    posted = session.post(login_url, data=payload, timeout=timeout)
    posted.raise_for_status()
    log("SUCCESS", "Authentication POST completed")

    log("INFO", f"GET {marks_url}")
    page = session.get(marks_url, timeout=timeout)
    page.raise_for_status()
    log("SUCCESS", "Fetched marks page")

    if _looks_like_login_page(page.text):
        raise RuntimeError("Login failed: verify email/password")

    headers, rows = _extract_table(page.text)
    snap = Snapshot(headers=headers, rows=rows, fingerprint=_fingerprint(headers, rows))

    path = _snapshot_path(semester, state_file)
    old = _load_snapshot(path)
    changed = old is None or old.fingerprint != snap.fingerprint
    _save_snapshot(path, snap)

    if changed:
        log("SUCCESS", f"Change detected for {semester}. Snapshot updated at {path}")
        _render_table(headers, rows, semester)
        if notify_email:
            send_email(
                subject=f"SchoolApp update detected ({semester})",
                body=f"SchoolApp marks changed for {semester}.",
                config=config,
            )
            log("SUCCESS", "Email notification sent")
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
    session = requests.Session()
    session.headers.update({"User-Agent": "schoolapp-cli/0.2"})

    login_url = f"{SCHOOLAPP_BASE}{LOGIN_PATH}"
    
    log("INFO", f"GET {login_url}")
    r = session.get(login_url, timeout=timeout)
    r.raise_for_status()
    log("SUCCESS", "Fetched login page")

    csrf = _extract_csrf(r.text)
    if not csrf:
        log("ERROR", "CSRF token missing on login page")
        raise RuntimeError("Login page changed: CSRF token missing")

    payload = {"email": email, "password": password, "_csrf": csrf}
    log("INFO", f"POST {login_url} (auth) using email={email}")
    posted = session.post(login_url, data=payload, timeout=timeout)
    posted.raise_for_status()
    log("SUCCESS", "Authentication POST completed")

    # Fetch the main marks page to get element details
    marks_url = f"{SCHOOLAPP_BASE}{MARKS_PATH}"
    log("INFO", f"GET {marks_url}")
    page = session.get(marks_url, timeout=timeout)
    page.raise_for_status()
    log("SUCCESS", "Fetched marks page")

    if _looks_like_login_page(page.text):
        raise RuntimeError("Login failed: verify email/password")

    soup = BeautifulSoup(page.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None

    best = max(tables, key=lambda t: len(t.find_all("tr")))
    details: dict = {"element_code": element_code, "stats": []}

    tr_match = None
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        code = _normalize_cell(tds[0].get_text(" ", strip=True)) if len(tds) >= 1 else ""
        if code.upper() == element_code.upper():
            tr_match = tr
            details["data"] = [_normalize_cell(td.get_text(" ", strip=True)) for td in tds]
            break

    if tr_match is None:
        return None

    tds = tr_match.find_all("td")
    if len(tds) < 10:
        return None

    au = _normalize_cell(tds[1].get_text(" ", strip=True))
    class_to_eval = {
        "notecc": ("NoteCC", 2),
        "noteex": ("NoteEX", 3),
        "notetp": ("NoteTP", 4),
        "moyelem": ("MoyElem", 8),
    }

    normalized_eval = eval_kind.strip().lower()
    wanted_classes: set[str]
    if normalized_eval in {"cc", "notecc"}:
        wanted_classes = {"notecc"}
    elif normalized_eval in {"ex", "noteex"}:
        wanted_classes = {"noteex"}
    elif normalized_eval in {"tp", "notetp"}:
        wanted_classes = {"notetp"}
    elif normalized_eval in {"moy", "moyelem", "moyenne"}:
        wanted_classes = {"moyelem"}
    else:
        wanted_classes = set(class_to_eval.keys())

    stats_url = f"{SCHOOLAPP_BASE}{STATS_PATH}"
    for css_class, (eval_param, idx) in class_to_eval.items():
        if css_class not in wanted_classes:
            continue
        if idx >= len(tds):
            continue
        note = _normalize_cell(tds[idx].get_text(" ", strip=True))
        if not note or note == "--":
            continue

        params = {
            "eval": eval_param,
            "codeelem": element_code.upper(),
            "au": au,
            "note": note,
        }
        log("INFO", f"GET {stats_url} eval={eval_param} codeelem={element_code.upper()} au={au} note={note}")
        resp = session.get(stats_url, params=params, timeout=timeout)
        resp.raise_for_status()

        popup_soup = BeautifulSoup(resp.text, "html.parser")
        stat_div = popup_soup.select_one("div.stat")
        scope = stat_div if stat_div else popup_soup

        title_node = scope.find("p")
        title = _normalize_cell(title_node.get_text(" ", strip=True)) if title_node else f"Statistiques {eval_param} - {element_code.upper()}"

        stat_table = scope.find("table")
        rows: list[list[str]] = []
        if stat_table:
            for row in stat_table.find_all("tr"):
                cols = row.find_all(["th", "td"])
                if not cols:
                    continue
                parsed = [_normalize_cell(c.get_text(" ", strip=True)) for c in cols]
                if any(parsed):
                    rows.append(parsed)

        details["stats"].append({
            "eval": eval_param,
            "title": title,
            "rows": rows,
        })

    return details if details.get("stats") else None


def watch_loop(*, email: str, password: str, timeout: int, semester: str, state_file: str | None, interval: int, notify_email: bool, config: dict | None) -> int:
    log("INFO", f"Watching {semester} every {interval}s")
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
                    config=config,
                )
            except requests.RequestException as exc:
                log("WARNING", f"Network error: {exc}")
            except Exception as exc:
                log("ERROR", str(exc))
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print(Panel.fit("Stopped watch mode"))
        return 0
