from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .extractors import (
    build_documents,
    parse_absence_summary,
    parse_absences,
    parse_catalog_modules,
    parse_catalog_options,
    parse_courses,
    parse_diploma,
    parse_element_grades,
    parse_filieres,
    parse_mark_statistics,
    parse_module_grades,
    parse_profile,
    parse_sanctions,
    parse_semester_results,
    parse_year_results,
)
from .models import (
    Absence,
    CatalogModule,
    CourseEnrollment,
    DiplomaResult,
    Document,
    ElementGrade,
    Filiere,
    MarkStatistics,
    ModuleGrade,
    Sanction,
    SemesterResult,
    StudentData,
    StudentProfile,
    YearResult,
)

SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
LOGIN_PATH = "/login"
INDEX_PATH = "/index"
ELEMENTS_PATH = "/student/noteselem-encours"
ELEMENTS_HISTORY_PATH = "/student/noteselem"
MODULES_PATH = "/student/notesmod-encours"
MODULES_HISTORY_PATH = "/student/notesmod"
SEMESTERS_PATH = "/student/notessem"
YEARS_PATH = "/student/notesannee"
DIPLOMA_PATH = "/student/notesdiplome"
ABSENCES_PATH = "/student/absence/bilan"
SANCTIONS_PATH = "/student/absence/sanctions"
COURSES_PATH = "/student/inscriptioncours"
STATS_PATH = "/notes-stat/elemevalsat"
CATALOG_PATH = "/plan-etudes-view/modules"
FILIERES_PATH = "/plan-etudes-view/filieres"


def extract_csrf(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    token = soup.select_one('input[name="_csrf"]')
    if not token:
        return None
    value = token.get("value")
    return value if isinstance(value, str) and value else None


def looks_like_login_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one('form[action="/login"]') and soup.select_one('input[name="password"]'))


class SchoolAppClient:
    """Authenticated session facade. Owns all HTTP/login I/O; re-auths once on expiry."""

    def __init__(self, base_url: str = SCHOOLAPP_BASE, session: requests.Session | None = None,
                 timeout: int = 20, min_interval: float = 0.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.min_interval = min_interval
        self._email: str | None = None
        self._password: str | None = None
        self._last_request = 0.0
        # Raw HTML of the last successful response per path — lets cache-layer
        # consumers (the watcher) reuse the exact bytes fetch_all parsed instead
        # of re-fetching. Bounded: one entry per distinct path.
        self.last_pages: dict[str, str] = {}

    def _throttle(self) -> None:
        if self.min_interval > 0:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()

    def login(self, email: str, password: str) -> None:
        self._email, self._password = email, password
        self._do_login()

    def set_credentials(self, email: str, password: str) -> None:
        """Store credentials without logging in now; auth happens lazily when a
        request lands on the login page (a still-valid session costs nothing)."""
        self._email, self._password = email, password

    def _do_login(self) -> None:
        self._throttle()
        r = self.session.get(self.base_url + LOGIN_PATH, timeout=self.timeout)
        r.raise_for_status()
        csrf = extract_csrf(r.text)
        if not csrf:
            raise RuntimeError("Login page changed: CSRF token missing")
        self._throttle()
        payload = {"email": self._email, "password": self._password, "_csrf": csrf}
        page = self.session.post(self.base_url + LOGIN_PATH, data=payload, timeout=self.timeout)
        page.raise_for_status()
        if looks_like_login_page(page.text):
            raise RuntimeError("Login failed: verify email/password")

    def get_page(self, path: str) -> str:
        """Raw HTML of a portal page (re-auth handled) — for cache-layer consumers
        that need the exact bytes (the watcher's legacy snapshot format)."""
        return self._get(path)

    def _get(self, path: str, **params: str) -> str:
        return self._request("GET", path, params=params)

    def _post(self, path: str, data: dict) -> str:
        return self._request("POST", path, data=data)

    def _request(self, method: str, path: str, params: dict | None = None,
                 data: dict | None = None, _retried: bool = False) -> str:
        self._throttle()
        url = self.base_url + path
        if method == "GET":
            resp = self.session.get(url, params=params or {}, timeout=self.timeout)
        else:
            resp = self.session.post(url, data=data or {}, timeout=self.timeout)
        resp.raise_for_status()
        if looks_like_login_page(resp.text):
            if _retried or not self._email:
                raise RuntimeError("Session expired and re-authentication failed")
            self._do_login()
            return self._request(method, path, params=params, data=data, _retried=True)
        self.last_pages[path] = resp.text
        return resp.text

    # ── per-student resources (spec §5) ──────────────────────────────────

    def profile(self) -> StudentProfile:
        return parse_profile(self._get(INDEX_PATH))

    def element_grades(self, history: bool = False) -> list[ElementGrade]:
        return parse_element_grades(self._get(ELEMENTS_HISTORY_PATH if history else ELEMENTS_PATH))

    def module_grades(self, history: bool = False) -> list[ModuleGrade]:
        return parse_module_grades(self._get(MODULES_HISTORY_PATH if history else MODULES_PATH))

    def semester_results(self) -> list[SemesterResult]:
        return parse_semester_results(self._get(SEMESTERS_PATH))

    def year_results(self) -> list[YearResult]:
        return parse_year_results(self._get(YEARS_PATH))

    def diploma(self) -> DiplomaResult:
        return parse_diploma(self._get(DIPLOMA_PATH))

    def absences(self) -> list[Absence]:
        return parse_absences(self._get(ABSENCES_PATH))

    def absence_summary(self) -> list[dict[str, str]]:
        return parse_absence_summary(self._get(ABSENCES_PATH))

    def sanctions(self) -> list[Sanction]:
        return parse_sanctions(self._get(SANCTIONS_PATH))

    def courses(self) -> list[CourseEnrollment]:
        return parse_courses(self._get(COURSES_PATH))

    _EVAL_ALIASES = {
        "cc": "NoteCC", "notecc": "NoteCC",
        "ex": "NoteEX", "noteex": "NoteEX",
        "tp": "NoteTP", "notetp": "NoteTP",
        "rat": "NoteRAT", "noterat": "NoteRAT",
        "moy": "MoyElem", "moyelem": "MoyElem", "moyenne": "MoyElem",
    }

    def mark_statistics(self, code: str, eval_kind: str = "all") -> list[MarkStatistics]:
        grades = parse_element_grades(self._get(ELEMENTS_PATH))
        target = next((g for g in grades if g.code.upper() == code.upper()), None)
        if target is None:
            return []
        notes = {"NoteCC": target.cc, "NoteEX": target.ex, "NoteTP": target.tp,
                 "NoteRAT": target.rat, "MoyElem": target.moy}
        wanted = self._EVAL_ALIASES.get(eval_kind.strip().lower())
        out: list[MarkStatistics] = []
        for eval_param in ([wanted] if wanted else list(notes)):
            note = notes[eval_param]
            if not note or note == "--":
                continue
            html = self._get(STATS_PATH, eval=eval_param, codeelem=target.code.upper(),
                             au=target.au, note=note)
            stat = parse_mark_statistics(html, element=target.code.upper(),
                                         eval_kind=eval_param, au=target.au, note=note)
            if stat:
                out.append(stat)
        return out

    def documents(self, year_results: list[YearResult] | None = None,
                  semester_results: list[SemesterResult] | None = None) -> list[Document]:
        yr = year_results if year_results is not None else self.year_results()
        sr = semester_results if semester_results is not None else self.semester_results()
        return build_documents(yr, sr)

    def download(self, doc: Document, _retried: bool = False) -> bytes:
        """Fetch a document's bytes (PDF). Explicit step — never part of fetch_all."""
        self._throttle()
        resp = self.session.get(self.base_url + doc.url, timeout=self.timeout)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if "html" in ctype and looks_like_login_page(resp.text):
            if _retried or not self._email:
                raise RuntimeError("Session expired and re-authentication failed")
            self._do_login()
            return self.download(doc, _retried=True)
        return resp.content

    # ── institution-wide catalog (spec §11) ─────────────────────────────

    def catalog_options(self) -> dict:
        return parse_catalog_options(self._get(CATALOG_PATH))

    def catalog_modules(self, niveau: str, filiere: str, semestre: str,
                        csrf: str | None = None) -> list[CatalogModule]:
        if csrf is None:
            csrf = self.catalog_options()["csrf"]
        html = self._post(CATALOG_PATH, {"niveau": niveau, "filiere": filiere,
                                         "semestre": semestre, "_csrf": csrf})
        return parse_catalog_modules(html, filiere=filiere)

    def filieres(self) -> list[Filiere]:
        return parse_filieres(self._get(FILIERES_PATH))

    # ── aggregate ────────────────────────────────────────────────────────

    def fetch_all(self, include_history: bool = True, include_stats: bool = False) -> StudentData:
        """Fetch every per-student resource; a failing resource lands in .errors, never aborts the rest."""
        data = StudentData(fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

        def grab(name, fn, default):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — per-resource isolation (spec §10)
                data.errors[name] = str(exc)
                return default

        data.profile = grab("profile", self.profile, None)

        current = grab("element_grades", self.element_grades, [])
        history = (grab("element_grades_history", lambda: self.element_grades(history=True), [])
                   if include_history else [])
        seen = {(g.code, g.au) for g in current}
        data.element_grades = current + [g for g in history if (g.code, g.au) not in seen]

        mods = grab("module_grades", self.module_grades, [])
        mods_hist = (grab("module_grades_history", lambda: self.module_grades(history=True), [])
                     if include_history else [])
        seen_mods = {(m.code, m.au) for m in mods}
        data.module_grades = mods + [m for m in mods_hist if (m.code, m.au) not in seen_mods]

        data.semester_results = grab("semester_results", self.semester_results, [])
        data.year_results = grab("year_results", self.year_results, [])
        data.diploma = grab("diploma", self.diploma, None)

        absences_html = grab("absences", lambda: self._get(ABSENCES_PATH), None)
        if absences_html is not None:
            data.absences = parse_absences(absences_html)
            data.absence_summary = parse_absence_summary(absences_html)

        data.sanctions = grab("sanctions", self.sanctions, [])
        data.courses = grab("courses", self.courses, [])
        data.documents = grab(
            "documents", lambda: build_documents(data.year_results, data.semester_results), [])

        if include_stats:
            data.stats = grab("stats", lambda: self._all_stats(current), [])
        try:
            from .academics import annotate_student_data
            annotate_student_data(data)
        except Exception as exc:  # noqa: BLE001 — computed fields are best-effort
            data.errors["academics"] = str(exc)
        return data

    def _all_stats(self, grades: list[ElementGrade]) -> list[MarkStatistics]:
        out: list[MarkStatistics] = []
        for g in grades:
            # (eval kind, note) pairs worth a popup: the element moyenne, and the
            # rattrapage note when taken (promo stats over rattrapage takers).
            for eval_kind, note in (("MoyElem", g.moy), ("NoteRAT", g.rat)):
                if not note or note == "--":
                    continue
                html = self._get(STATS_PATH, eval=eval_kind, codeelem=g.code.upper(),
                                 au=g.au, note=note)
                stat = parse_mark_statistics(html, element=g.code.upper(), eval_kind=eval_kind,
                                             au=g.au, note=note)
                if stat:
                    out.append(stat)
        return out
