#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import textwrap
import smtplib
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from rich.console import Console
    from rich import box
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except Exception:  # pragma: no cover
    Console = None
    box = None
    RichHandler = None
    Prompt = None


logger = logging.getLogger("schoolapp-watcher")


class EgradingStyleUI:
    def __init__(self, *, use_color: bool = True) -> None:
        self.con = _console()
        self.use_color = use_color

    def section(self, title: str) -> None:
        line = "=" * 70
        arrow = f"→ {title}"

        if self.con is not None and self.use_color:
            self.con.print()
            self.con.print(f"[bold cyan]{line}[/bold cyan]")
            self.con.print(f"[bold cyan]{arrow}[/bold cyan]")
            self.con.print(f"[bold cyan]{line}[/bold cyan]\n")
        else:
            print(f"\n{line}\n{arrow}\n{line}\n")

    def log(self, msg: str, *, level: str = "info") -> None:
        t = datetime.now().isoformat(sep=" ", timespec="seconds")
        prefixes = {
            "info": ("[INFO]", "blue"),
            "ok": ("[✓]", "green"),
            "warn": ("[!]", "yellow"),
            "err": ("[✗]", "red"),
        }
        prefix, color = prefixes.get(level, ("", "white"))

        if self.con is not None and self.use_color:
            self.con.print(f"[dim][{t}][/dim] [{color}]{prefix}[/{color}] {msg}")
        else:
            print(f"[{t}] {prefix} {msg}")


SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
MARKS_PATH = "/student/noteselem-encours"
LOGIN_PATH = "/login"


@dataclass
class Snapshot:
    url: str
    headers: list[str]
    rows: list[list[str]]
    fingerprint: str


def _console():
    return Console() if Console is not None else None


def _setup_logging(verbose: bool, log_file: str | None, *, console_logs: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = []
    if console_logs and RichHandler is not None:
        handlers.append(
            RichHandler(
                rich_tracebacks=verbose,
                show_time=True,
                show_level=True,
                show_path=verbose,
                markup=True,
            )
        )
    elif console_logs:
        handlers.append(logging.StreamHandler(sys.stderr))
    else:
        handlers.append(logging.NullHandler())

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Keep noisy libraries quieter unless verbose is requested.
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing env."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value


def _infer_project_root_from_venv() -> Path | None:
    """Try to infer the project root when running from a venv.

    Note: On some systems, the venv interpreter is a symlink to a global
    Python (e.g. /usr/bin/python3). In that case, resolving sys.executable
    breaks venv path inference. Prefer VIRTUAL_ENV / sys.prefix.
    """

    candidates: list[Path] = []

    venv_env = os.environ.get("VIRTUAL_ENV")
    if venv_env:
        candidates.append(Path(venv_env))

    # sys.prefix points to the venv root when a venv is active.
    try:
        candidates.append(Path(sys.prefix))
    except Exception:
        pass

    for venv_root in candidates:
        try:
            venv_root = venv_root.resolve()
        except Exception:
            continue
        if venv_root.name == ".venv":
            return venv_root.parent

    # Fallback: when installed editable, this file often lives in the project
    # root; search upwards for pyproject.toml.
    try:
        here = Path(__file__).resolve()
        for parent in [here.parent, *here.parents]:
            if (parent / "pyproject.toml").exists():
                return parent
    except Exception:
        return None

    return None


@dataclass(frozen=True)
class ElementDef:
    code: str
    title: str
    coef_cc: float
    coef_ex: float
    coef_ecrit: float
    coef_tp: float
    coef_eelem: float


@dataclass(frozen=True)
class ModuleDef:
    code: str
    title: str
    niveau: str
    semestre: str
    coef_mod: float
    seuil: float
    eliminatoire: float
    elements: list[ElementDef]


# Preset based on the user's pasted S3 (2A) coefficients.
PRESET_2A_S3: list[ModuleDef] = [
    ModuleDef(
        code="API31",
        title="Analyse 3",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API311",
                title="Analyse 3",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=5.0,
                coef_tp=0.0,
                coef_eelem=5.0,
            )
        ],
    ),
    ModuleDef(
        code="API32",
        title="Chimie organique et métallurgie",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API321",
                title="Chimie organique",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=2.5,
                coef_tp=0.5,
                coef_eelem=3.0,
            ),
            ElementDef(
                code="API322",
                title="Métallurgie",
                coef_cc=0.0,
                coef_ex=1.0,
                coef_ecrit=1.5,
                coef_tp=0.5,
                coef_eelem=2.0,
            ),
        ],
    ),
    ModuleDef(
        code="API33",
        title="Mécanique du solide et usinage",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API331",
                title="Mécanique du solide appliquée",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=3.0,
                coef_tp=0.0,
                coef_eelem=3.0,
            ),
            ElementDef(
                code="API332",
                title="Usinage 2",
                coef_cc=0.0,
                coef_ex=1.0,
                coef_ecrit=1.5,
                coef_tp=0.5,
                coef_eelem=2.0,
            ),
        ],
    ),
    ModuleDef(
        code="API34",
        title="Automatique et RDM",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API341",
                title="Automatique des systèmes",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=2.25,
                coef_tp=0.5,
                coef_eelem=2.75,
            ),
            ElementDef(
                code="API342",
                title="RDM",
                coef_cc=0.0,
                coef_ex=1.0,
                coef_ecrit=1.75,
                coef_tp=0.5,
                coef_eelem=2.25,
            ),
        ],
    ),
    ModuleDef(
        code="API35",
        title="Programmation et Probabilités",
        niveau="2A",
        semestre="S3",
        coef_mod=4.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API351",
                title="Programmation C++ et Algorithmique",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=2.25,
                coef_tp=0.0,
                coef_eelem=2.25,
            ),
            ElementDef(
                code="API352",
                title="Calcul des Probabilités",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=1.75,
                coef_tp=0.0,
                coef_eelem=1.75,
            ),
        ],
    ),
    ModuleDef(
        code="API36",
        title="Langues 3",
        niveau="2A",
        semestre="S3",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API361",
                title="Initiation à la communication",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=1.5,
                coef_tp=0.0,
                coef_eelem=1.5,
            ),
            ElementDef(
                code="API362",
                title="English for International communication",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=1.5,
                coef_tp=0.0,
                coef_eelem=1.5,
            ),
        ],
    ),
    ModuleDef(
        code="API37",
        title="Culture et Arts",
        niveau="2A",
        semestre="S3",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef(
                code="API371",
                title="Culture et Arts",
                coef_cc=0.3,
                coef_ex=0.7,
                coef_ecrit=3.0,
                coef_tp=0.0,
                coef_eelem=3.0,
            )
        ],
    ),
]


def _element_title_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for mod in PRESET_2A_S3:
        for el in mod.elements:
            out[el.code] = el.title
    return out


def _prompt_float(label: str, default: float | None = None) -> float:
    con = _console()
    if Prompt is not None and con is not None:
        while True:
            txt = Prompt.ask(label, default=(str(default) if default is not None else None))
            try:
                val = float(txt)
            except Exception:
                con.print("[red]Invalid number[/red]")
                continue
            if 0.0 <= val <= 20.0:
                return val
            con.print("[red]Enter a value between 0 and 20[/red]")

    while True:
        raw = input(f"{label}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return float(default)
        try:
            val = float(raw)
        except Exception:
            print("Invalid number", file=sys.stderr)
            continue
        if 0.0 <= val <= 20.0:
            return val
        print("Enter a value between 0 and 20", file=sys.stderr)


def _calc_element_grade(defn: ElementDef, marks: dict[str, float]) -> float:
    """Compute element final grade out of 20.

    Accepted marks keys per element code:
    - <CODE>.cc
    - <CODE>.ex  (exam overall)
    - <CODE>.ecrit, <CODE>.tp (optional; if present used to compute exam overall)
    """

    cc = marks.get(f"{defn.code}.cc", 0.0)

    if f"{defn.code}.ecrit" in marks or f"{defn.code}.tp" in marks:
        ecrit = marks.get(f"{defn.code}.ecrit", 0.0)
        tp = marks.get(f"{defn.code}.tp", 0.0)
        denom = (defn.coef_ecrit + defn.coef_tp) if (defn.coef_ecrit + defn.coef_tp) > 0 else 1.0
        ex = (ecrit * defn.coef_ecrit + tp * defn.coef_tp) / denom
    else:
        ex = marks.get(f"{defn.code}.ex", 0.0)

    return cc * defn.coef_cc + ex * defn.coef_ex


def run_calculator(*, preset: str, marks_file: str | None) -> int:
    con = _console()

    presets: dict[str, list[ModuleDef]] = {
        "2A-S3": PRESET_2A_S3,
        "S3": PRESET_2A_S3,
    }

    modules = presets.get(preset.upper()) if preset.upper() in presets else presets.get(preset)
    if modules is None:
        raise RuntimeError(f"Unknown preset '{preset}'. Available: {', '.join(sorted(presets.keys()))}")

    marks: dict[str, float] = {}
    if marks_file:
        data = json.loads(Path(marks_file).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("Marks file must be a JSON object")
        marks = {str(k): float(v) for k, v in data.items()}

    if con is not None:
        con.print(Panel.fit(Text(f"Calculator — {preset}", style="bold")))
        con.print("Enter marks out of 20. You can leave CC at 0 if not applicable.")

    module_results: list[tuple[ModuleDef, float, bool]] = []
    total_weight = sum(m.coef_mod for m in modules) or 1.0
    sem_sum = 0.0

    for mod in modules:
        if con is not None:
            con.print(Panel.fit(f"[bold]{mod.code}[/bold] — {mod.title}  (Coef {mod.coef_mod})"))

        mod_sum = 0.0
        for el in mod.elements:
            # prompt missing marks
            cc_key = f"{el.code}.cc"
            ex_key = f"{el.code}.ex"

            if cc_key not in marks and el.coef_cc > 0:
                marks[cc_key] = _prompt_float(f"{el.code} CC")
            if ex_key not in marks and (f"{el.code}.ecrit" not in marks and f"{el.code}.tp" not in marks):
                marks[ex_key] = _prompt_float(f"{el.code} EX")

            el_grade = _calc_element_grade(el, marks)
            mod_sum += el_grade * el.coef_eelem

            if con is not None:
                con.print(f"[dim]{el.code}[/dim] {el.title}: [bold]{el_grade:.2f}[/bold] / 20  (Coef {el.coef_eelem})")

        mod_avg = mod_sum / (mod.coef_mod or 1.0)
        eliminated = mod_avg < mod.eliminatoire
        module_results.append((mod, mod_avg, eliminated))
        sem_sum += mod_avg * mod.coef_mod

        if con is not None:
            style = "red" if eliminated else ("yellow" if mod_avg < mod.seuil else "green")
            con.print(f"Module average: [{style}][bold]{mod_avg:.2f}[/bold][/{style}] / 20  (Seuil {mod.seuil}, Eliminatoire {mod.eliminatoire})")
        else:
            print(f"{mod.code}: {mod_avg:.2f}/20")

    sem_avg = sem_sum / total_weight
    any_elim = any(e for _, _, e in module_results)

    if con is not None:
        con.print(Panel.fit(f"Semester average: [bold]{sem_avg:.2f}[/bold] / 20"))
        if any_elim:
            con.print("[bold red]Warning:[/bold red] at least one module is below eliminatoire.")
    else:
        print(f"Semester average: {sem_avg:.2f}/20")

    return 0


def _default_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "schoolapp-watcher"
    return Path.home() / ".local" / "state" / "schoolapp-watcher"


def _normalize_cell(text: str) -> str:
    return " ".join(text.split())


def _extract_csrf(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    token = soup.select_one('input[name="_csrf"]')
    if not token:
        return None
    value = token.get("value")
    return value if isinstance(value, str) and value else None


def _extract_table(html: str) -> tuple[list[str], list[list[str]]]:
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No <table> elements found on marks page (maybe not logged in or page layout changed).")

    expected_headers = ["CodeElem", "AU", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]

    def table_headers(t) -> list[str]:
        ths = t.find_all("th")
        return [_normalize_cell(th.get_text(" ", strip=True)) for th in ths]

    # Prefer the specific marks-by-element table if present.
    best = None
    for t in tables:
        hs = table_headers(t)
        if not hs:
            continue
        if all(h in hs for h in expected_headers) or ("CodeElem" in hs and "AU" in hs):
            best = t
            break

    if best is None:
        best = max(tables, key=lambda t: len(t.find_all("tr")))

    header_cells = best.find_all("th")
    headers: list[str]
    if header_cells:
        headers = [_normalize_cell(th.get_text(" ", strip=True)) for th in header_cells]
    else:
        first_tr = best.find("tr")
        if not first_tr:
            return [], []
        headers = [_normalize_cell(td.get_text(" ", strip=True)) for td in first_tr.find_all("td")]

    rows: list[list[str]] = []
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [_normalize_cell(td.get_text(" ", strip=True)) for td in tds]
        if any(cell for cell in row):
            rows.append(row)

    return headers, rows


def _fingerprint(headers: list[str], rows: list[list[str]]) -> str:
    payload = json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _looks_like_login_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.select_one('form[action="/login"]') and soup.select_one('input[name="password"]'))


class SchoolAppClient:
    def __init__(self, timeout_s: int = 20) -> None:
        self.session = requests.Session()
        self.timeout_s = timeout_s
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) schoolapp-watcher/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def _request_https_redirects(self, method: str, url: str, *, max_hops: int = 10, **kwargs) -> requests.Response:
        current_url = url
        for _ in range(max_hops + 1):
            resp = self.session.request(method, current_url, timeout=self.timeout_s, allow_redirects=False, **kwargs)
            if resp.status_code not in (301, 302, 303, 307, 308):
                return resp

            location = resp.headers.get("Location")
            if not location:
                return resp

            next_url = requests.compat.urljoin(current_url, location)
            if next_url.startswith("http://"):
                next_url = "https://" + next_url[len("http://") :]

            if method.upper() != "GET" and resp.status_code in (302, 303):
                method = "GET"
                kwargs.pop("data", None)
                kwargs.pop("json", None)

            current_url = next_url

        raise RuntimeError("Too many redirects while requesting SchoolApp.")

    def login(self, email: str, password: str) -> str:
        login_url = f"{SCHOOLAPP_BASE}{LOGIN_PATH}"
        logger.debug("Fetching login page")
        r = self._request_https_redirects("GET", login_url)
        r.raise_for_status()
        csrf = _extract_csrf(r.text)
        if not csrf:
            raise RuntimeError("Could not find _csrf token on login page; login flow may have changed.")

        logger.debug("Login page OK; csrf token extracted")

        data = {"email": email, "password": password, "_csrf": csrf}
        logger.debug("Submitting credentials")
        pr = self._request_https_redirects(
            "POST",
            login_url,
            data=data,
            headers={"Referer": login_url},
        )
        pr.raise_for_status()

        logger.debug("Login submit OK; verifying access to marks page")

        marks_html = self.fetch_marks_html()
        if _looks_like_login_page(marks_html):
            raise RuntimeError("Login appears to have failed (still on login page after login attempt).")

        return marks_html

    def fetch_marks_html(self) -> str:
        url = f"{SCHOOLAPP_BASE}{MARKS_PATH}"
        logger.debug("Fetching marks page")
        r = self._request_https_redirects("GET", url)
        r.raise_for_status()
        return r.text


def load_snapshot(path: Path) -> Snapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Snapshot(
        url=str(data.get("url", "")),
        headers=list(data.get("headers", [])),
        rows=list(data.get("rows", [])),
        fingerprint=str(data.get("fingerprint", "")),
    )


def save_snapshot(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "url": snap.url,
                "headers": snap.headers,
                "rows": snap.rows,
                "fingerprint": snap.fingerprint,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _render_table(headers: list[str], rows: list[list[str]], *, max_rows: int = 10) -> None:
    con = _console()
    if con is None:
        return

    # If this looks like the marks-by-element table, render it fully with '--' placeholders.
    expected = ["CodeElem", "AU", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    is_marks_table = all(h in headers for h in expected)

    if is_marks_table:
        ordered_headers = ["CodeElem", "Intitule"] + [h for h in expected if h != "CodeElem"]
        table_box = box.HEAVY_HEAD if box is not None else None
        table = Table(
            show_header=True,
            header_style="bold",
            box=table_box,
            pad_edge=False,
        )
        table.add_column("CodeElem", style="bold cyan", no_wrap=True)
        table.add_column("Intitule", style="white")
        for h in expected[1:]:
            table.add_column(h, style="bright_white", no_wrap=True, justify="center")

        idx = {h: headers.index(h) for h in expected}
        titles = _element_title_map()

        for row in rows:
            def cell(h: str) -> str:
                i = idx[h]
                v = row[i] if i < len(row) else ""
                return v if v else "--"

            code = cell("CodeElem")
            title = titles.get(code, "--") if code != "--" else "--"
            table.add_row(code, title, *(cell(h) for h in expected[1:]))

        con.print(table)
        return

    table = Table(show_header=True, header_style="bold")
    for h in headers[:12]:
        table.add_column(h or " ")

    shown = rows[:max_rows]
    for row in shown:
        padded = (row + [""] * 12)[:12]
        table.add_row(*[(c if c else "--") for c in padded])

    con.print(table)
    if len(rows) > max_rows:
        con.print(f"… {len(rows) - max_rows} more rows")


def _smtp_from_env() -> dict[str, str] | None:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_TO"]
    env = {k: os.environ.get(k, "") for k in required}
    if all(env.values()):
        return env
    return None


def send_email_notification(subject: str, body: str) -> None:
    cfg = _smtp_from_env()
    if cfg is None:
        raise RuntimeError(
            "Email env not set. Required: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, SMTP_TO"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = cfg["SMTP_TO"]
    msg.set_content(body)

    host = cfg["SMTP_HOST"]
    port = int(cfg["SMTP_PORT"])
    username = cfg["SMTP_USERNAME"]
    password = cfg["SMTP_PASSWORD"]

    context = ssl.create_default_context()

    # 465 usually SSL, 587 usually STARTTLS
    if port == 465:
        logger.debug("Sending email via SMTP_SSL %s:%s", host, port)
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        logger.debug("Sending email via STARTTLS %s:%s", host, port)
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(msg)


def check_once(
    email: str,
    password: str,
    state_path: Path,
    timeout: int,
    *,
    notify_email: bool,
    ui: EgradingStyleUI | None = None,
) -> tuple[bool, Snapshot]:
    client = SchoolAppClient(timeout_s=timeout)
    if ui is not None:
        ui.section("AUTHENTICATION")
        ui.log(f"Logging in as {email}")

    html = client.login(email=email, password=password)

    if ui is not None:
        ui.log("Authentication successful", level="ok")
        ui.section("MARKS TABLE")
        ui.log("Fetching marks page", level="info")

    # Refresh once after login to ensure latest values (the login flow may land on /index first)
    html = client.fetch_marks_html()
    headers, rows = _extract_table(html)
    logger.info("Parsed table: %d rows, %d headers", len(rows), len(headers))
    if ui is not None:
        ui.log(f"Parsed table: {len(rows)} rows", level="ok")
    snap = Snapshot(
        url=f"{SCHOOLAPP_BASE}{MARKS_PATH}",
        headers=headers,
        rows=rows,
        fingerprint=_fingerprint(headers, rows),
    )

    old = load_snapshot(state_path)
    if old is None:
        logger.info("No previous snapshot found; initializing")
        save_snapshot(state_path, snap)
        if ui is not None:
            ui.section("RESULT")
            ui.log("Initialized snapshot (first run)", level="ok")
        return False, snap

    if old.fingerprint == snap.fingerprint:
        logger.info("No change detected")
        if ui is not None:
            ui.section("RESULT")
            ui.log("No change detected", level="ok")
        return False, snap

    save_snapshot(state_path, snap)
    logger.info("Change detected; snapshot updated")
    if notify_email:
        subject = "SchoolApp update detected"
        body = (
            "A change was detected in your SchoolApp marks table.\n\n"
            f"URL: {snap.url}\n"
            f"Rows: {len(snap.rows)}\n"
            f"Fingerprint: {snap.fingerprint}\n"
        )
        send_email_notification(subject, body)

    if ui is not None:
        ui.section("RESULT")
        ui.log("CHANGE DETECTED", level="warn")

    return True, snap


def main(argv: list[str] | None = None) -> int:
    con = _console()

    if argv is None:
        argv = sys.argv[1:]

    # Pre-parse just for --env-file so env defaults are available for the main parser.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=None)
    pre_args, _ = pre.parse_known_args(argv)

    if pre_args.env_file:
        _load_env_file(Path(pre_args.env_file))
    else:
        # Convenience: auto-load from current working directory.
        _load_env_file(Path(".env"))
        _load_env_file(Path(".env.example"))

        # Also auto-load from the project root (useful when running `schoolapp`
        # from anywhere, because the venv lives under the project folder).
        project_root = _infer_project_root_from_venv()
        if project_root is not None:
            _load_env_file(project_root / ".env")
            _load_env_file(project_root / ".env.example")

    prog_name = os.path.basename(sys.argv[0]) or "schoolapp"
    description = textwrap.dedent(
        """
        Watch ENSAM SchoolApp marks table and notify when it changes.

        What it does:
          - Logs in to SchoolApp
          - Fetches the "notes éléments" table
          - Prints it in a boxed, readable format
          - Saves a snapshot and detects updates on next runs
        """
    ).strip()

    epilog = textwrap.dedent(
        """
        Examples:
          # Run once using .env.example (recommended)
          schoolapp --env-file .env.example

          # Watch every 5 minutes
          schoolapp --watch --interval 300

          # Calculator (no login)
          schoolapp --calc

        Tips:
          - Prefer env files / env vars for passwords (avoid --password).
          - Use --verbose to see detailed debug logs.
        """
    ).strip()

    parser = argparse.ArgumentParser(
        prog=prog_name,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    io_group = parser.add_argument_group("Input / Config")
    io_group.add_argument("--env-file", default=None, help="Load environment variables from a file (KEY=VALUE)")
    io_group.add_argument(
        "--state-file",
        default=str(_default_state_dir() / "snapshot.json"),
        help="Where to store the last snapshot JSON",
    )
    io_group.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")

    auth_group = parser.add_argument_group("Login")
    auth_group.add_argument("--email", default=os.environ.get("SCHOOLAPP_EMAIL"), help="SchoolApp email (or env SCHOOLAPP_EMAIL)")
    auth_group.add_argument(
        "--password",
        default=os.environ.get("SCHOOLAPP_PASSWORD"),
        help="SchoolApp password (or env SCHOOLAPP_PASSWORD). If omitted, prompts securely.",
    )

    watch_group = parser.add_argument_group("Watch Mode")
    watch_group.add_argument("--watch", action="store_true", help="Continuously poll and alert on changes")
    watch_group.add_argument("--interval", type=int, default=900, help="Polling interval in seconds (watch mode)")

    notify_group = parser.add_argument_group("Notifications")
    notify_group.add_argument(
        "--notify-email",
        action="store_true",
        help="Send an email when a change is detected (requires SMTP_* env vars)",
    )

    calc_group = parser.add_argument_group("Calculator")
    calc_group.add_argument("--calc", action="store_true", help="Run the grade calculator (no login required)")
    calc_group.add_argument("--preset", default="2A-S3", help="Calculator preset (default: 2A-S3)")
    calc_group.add_argument(
        "--marks-file",
        default=None,
        help="JSON file with marks (e.g. {'API311.cc': 12, 'API311.ex': 14})",
    )

    debug_group = parser.add_argument_group("Debug")
    debug_group.add_argument("--verbose", action="store_true", help="Enable more detailed logs")
    debug_group.add_argument("--log-file", default=None, help="Write logs to a file (in addition to stderr)")
    debug_group.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args(argv)

    # Console output uses egrading-style UI; only show Python logging on console in verbose mode.
    _setup_logging(verbose=bool(args.verbose), log_file=args.log_file, console_logs=bool(args.verbose))
    ui = EgradingStyleUI(use_color=not bool(args.no_color))

    if args.calc:
        try:
            return run_calculator(preset=str(args.preset), marks_file=args.marks_file)
        except Exception as exc:
            logger.exception("Calculator failed")
            con = _console()
            if con is not None:
                con.print(f"[bold red]Error:[/bold red] {exc}")
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return 2

    email = args.email
    if not email:
        print("Missing --email (or set SCHOOLAPP_EMAIL).", file=sys.stderr)
        return 2

    password = args.password
    if not password:
        password = getpass.getpass("SchoolApp password: ")

    state_path = Path(args.state_file)

    ui.section("SCHOOLAPP WATCHER")
    ui.log(f"State file: {state_path}")
    ui.log("Tip: add --verbose for detailed HTTP/debug logs")

    def run_check() -> int:
        changed, snap = check_once(
            email=email,
            password=password,
            state_path=state_path,
            timeout=args.timeout,
            notify_email=bool(args.notify_email),
            ui=ui,
        )

        _render_table(snap.headers, snap.rows)

        return 1 if changed else 0

    if not args.watch:
        try:
            return run_check()
        except Exception as exc:
            logger.exception("Run failed")
            if con is not None:
                con.print(f"[bold red]Error:[/bold red] {exc}")
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.interval < 30:
        if con is not None:
            con.print("[yellow]Warning:[/yellow] interval < 30s is likely too aggressive.")

    if con is not None:
        ui.section("WATCH")
        ui.log(f"Watching every {args.interval}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                exit_code = run_check()
                if exit_code == 1 and con is not None:
                    con.print("[dim]Email sent (if configured).[/dim]" if args.notify_email else "")
            except Exception as exc:
                logger.exception("Watch iteration failed")
                if con is not None:
                    con.print(f"[bold red]Error:[/bold red] {exc}")
                else:
                    print(f"Error: {exc}", file=sys.stderr)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        if con is not None:
            con.print("Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
