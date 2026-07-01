# SchoolApp Extraction — Phase 1: Library Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the reusable extraction library's foundation — a test harness, typed data models, shared HTML-table primitives, and an authenticated `SchoolAppClient` — without changing any watcher or API runtime behavior.

**Architecture:** New layered package under the existing `schoolapp/`: `models.py` (pure typed dataclasses), `extractors/_tables.py` (pure table helpers migrated out of `watcher.py`), and `client.py` (all HTTP/login I/O). `watcher.py` imports the migrated helpers instead of defining them, so behavior is identical. Per-resource extractors and consumer wiring are later phases (separate plans).

**Tech Stack:** Python ≥3.10, `requests`, `beautifulsoup4`, `dataclasses`, `pytest` (new dev dependency).

**Source spec:** `docs/superpowers/specs/2026-06-28-schoolapp-comprehensive-extraction-design.md` (§3 architecture, §4 models, §5 client, §6 extractors, §7 storage).

## Global Constraints

- **Python floor:** `requires-python = ">=3.10"` — use `X | Y` unions and built-in generics freely.
- **Dependency pinning:** pin every new dependency with `==` (match existing style). New dev dep: `pytest==8.3.4`.
- **Package location:** library lives under existing `schoolapp/`; public import must be `from schoolapp import SchoolAppClient`.
- **Back-compat (hard):** do NOT change `watcher.py`/`api.py` runtime behavior, the `s4_snapshot.json` format, or any existing `/api/*` response shape. Migrations in this plan are pure code moves + import rewrites.
- **CSRF field name:** the portal login hidden input is `_csrf` (verified). Login POST body is `{"email", "password", "_csrf"}`.
- **Pass threshold:** an element/module is "validated" when `float(moy.rstrip("*")) >= 11.0` (matches existing `_is_validated`).
- **Base + paths:** `SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"`, `LOGIN_PATH = "/login"`.
- **No PII in fixtures:** Phase 1 tests use synthetic inline HTML only (no live captures). Real sanitized fixtures arrive in Phase 2 (see the `sanitizing-schoolapp-fixtures` skill).
- **Run tests with:** `python -m pytest` from the repo root (a `.venv` is present; activate or use its interpreter).

---

### Task 1: Test harness setup

**Files:**
- Modify: `pyproject.toml` (add dev extra + pytest config)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable `python -m pytest` and the `tests/` package other tasks add to.

- [ ] **Step 1: Write the smoke test**

Create `tests/__init__.py` as an empty file, then create `tests/test_smoke.py`:

```python
def test_package_imports():
    import schoolapp

    assert hasattr(schoolapp, "__version__")
```

- [ ] **Step 2: Run it to confirm pytest is missing**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `No module named pytest` (pytest not yet installed).

- [ ] **Step 3: Add pytest as a dev dependency and configure it**

In `pyproject.toml`, after the `[project]` table's `dependencies = [...]` list, add:

```toml
[project.optional-dependencies]
dev = ["pytest==8.3.4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Then install it: `python -m pip install "pytest==8.3.4"`

- [ ] **Step 4: Run the smoke test — it passes**

Run: `python -m pytest -v`
Expected: PASS — `tests/test_smoke.py::test_package_imports PASSED`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/test_smoke.py
git commit -m "test: add pytest harness and smoke test"
```

---

### Task 2: Typed data models (`schoolapp/models.py`)

**Files:**
- Create: `schoolapp/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing (pure dataclasses).
- Produces: `PASS_THRESHOLD`, and dataclasses `StudentProfile`, `ElementGrade` (props `is_estimated: bool`, `validated: bool | None`), `ModuleGrade`, `SemesterResult`, `YearResult`, `DiplomaResult`, `Absence`, `Sanction`, `CourseEnrollment`, `MarkStatistics`, `CatalogModule`, `Filiere`, `Document`, `StudentData`. Every model has a `raw` field; all are `dataclasses.asdict`-serializable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from dataclasses import asdict

from schoolapp.models import ElementGrade, StudentData, Absence, PASS_THRESHOLD


def test_pass_threshold_is_eleven():
    assert PASS_THRESHOLD == 11.0


def test_element_grade_is_estimated_and_validated():
    assert ElementGrade(code="API101", moy="12.5*").is_estimated is True
    assert ElementGrade(code="API101", moy="12.5").is_estimated is False
    assert ElementGrade(code="API101", moy="12.5*").validated is True
    assert ElementGrade(code="API101", moy="10.0").validated is False
    assert ElementGrade(code="API101", moy="--").validated is None
    assert ElementGrade(code="API101", moy="").validated is None
    assert ElementGrade(code="API101", moy="n/a").validated is None


def test_models_are_asdict_serializable():
    eg = ElementGrade(code="API101", cc="12", raw={"CC": "12"})
    d = asdict(eg)
    assert d["code"] == "API101"
    assert d["raw"] == {"CC": "12"}


def test_studentdata_defaults_are_independent():
    a, b = StudentData(), StudentData()
    a.absences.append(Absence(element="API101"))
    assert b.absences == []          # default_factory, not shared
    assert a.errors == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.models'`.

- [ ] **Step 3: Write the models**

Create `schoolapp/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

PASS_THRESHOLD = 11.0


@dataclass
class StudentProfile:
    code: str = ""
    cne_masar: str = ""
    nom: str = ""
    prenom: str = ""
    nom_ar: str = ""
    prenom_ar: str = ""
    cin: str = ""
    sexe: str = ""
    date_naissance: str = ""
    email: str = ""
    filiere: str = ""
    niveau: str = ""
    statut: str = ""
    section: str = ""
    groupe: str = ""
    sous_groupe: str = ""
    photo_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class ElementGrade:
    code: str = ""
    au: str = ""
    cc: str = ""
    ex: str = ""
    tp: str = ""
    moy_so: str = ""
    rat: str = ""
    moy_sr: str = ""
    moy: str = ""
    decision: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def is_estimated(self) -> bool:
        return self.moy.endswith("*")

    @property
    def validated(self) -> bool | None:
        m = self.moy.rstrip("*")
        if m in ("", "--"):
            return None
        try:
            return float(m) >= PASS_THRESHOLD
        except ValueError:
            return None


@dataclass
class ModuleGrade:
    code: str = ""
    au: str = ""
    moy: str = ""
    decision: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class SemesterResult:
    niveau: str = ""
    semestre: str = ""
    au: str = ""
    moy_sem: str = ""
    pj: str = ""
    decision: str = ""
    classement: str = ""
    releve_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class YearResult:
    niveau: str = ""
    filiere: str = ""
    au: str = ""
    statut: str = ""
    moy_annee: str = ""
    pj: str = ""
    decision: str = ""
    classement: str = ""
    releve_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class DiplomaResult:
    empty: bool = True
    message: str | None = None
    rows: list[dict[str, str]] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Absence:
    element: str = ""
    date: str = ""
    seance: str = ""
    justified: bool = False
    remarks: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Sanction:
    key: str = ""
    value: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class CourseEnrollment:
    code_elem: str = ""
    statut: str = ""
    section: str = ""
    groupe: str = ""
    sous_groupe: str = ""
    num: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class MarkStatistics:
    element: str = ""
    eval_kind: str = ""
    au: str = ""
    note: str = ""
    title: str = ""
    rows: list[list[str]] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class CatalogModule:
    code_mod: str = ""
    intitule: str = ""
    descriptif: str = ""
    niveau: str = ""
    semestre: str = ""
    vh_mod: str = ""
    coef_mod: str = ""
    seuil: str = ""
    eliminatoire: str = ""
    filiere: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Filiere:
    code: str = ""
    label: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Document:
    kind: str = ""
    url: str = ""
    params: dict[str, str] = field(default_factory=dict)
    filename: str = ""
    content_type: str = ""


@dataclass
class StudentData:
    profile: StudentProfile | None = None
    element_grades: list[ElementGrade] = field(default_factory=list)
    module_grades: list[ModuleGrade] = field(default_factory=list)
    semester_results: list[SemesterResult] = field(default_factory=list)
    year_results: list[YearResult] = field(default_factory=list)
    diploma: DiplomaResult | None = None
    absences: list[Absence] = field(default_factory=list)
    sanctions: list[Sanction] = field(default_factory=list)
    courses: list[CourseEnrollment] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    fetched_at: str = ""
    errors: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS — all four tests green.

- [ ] **Step 5: Commit**

```bash
git add schoolapp/models.py tests/test_models.py
git commit -m "feat(models): add typed extraction dataclasses with raw escape hatch"
```

---

### Task 3: Migrate shared table helpers (`schoolapp/extractors/_tables.py`)

**Files:**
- Create: `schoolapp/extractors/__init__.py` (empty)
- Create: `schoolapp/extractors/_tables.py`
- Modify: `schoolapp/watcher.py` (delete the four local helper defs; import them instead)
- Test: `tests/test_tables.py`

**Interfaces:**
- Consumes: nothing.
- Produces: pure functions `normalize_cell(text) -> str`, `extract_table(html) -> tuple[list[str], list[list[str]]]` (raises `RuntimeError` when no table), `table_by_headers(html, wanted: set[str]) -> tuple[list[str], list[list[str]]] | None`, `fingerprint(headers, rows) -> str`. `watcher.py` re-binds its private `_normalize_cell`/`_extract_table`/`_table_by_headers`/`_fingerprint` names to these.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tables.py`:

```python
import pytest

from schoolapp.extractors._tables import (
    normalize_cell,
    extract_table,
    table_by_headers,
    fingerprint,
)

TABLE_HTML = """
<table>
  <tr><th>CodeElem</th><th>Moy</th></tr>
  <tr><td>API101</td><td> 12.5 </td></tr>
  <tr><td>API102</td><td>9</td></tr>
</table>
"""


def test_normalize_cell_collapses_whitespace():
    assert normalize_cell("  hello \n  world ") == "hello world"


def test_extract_table_reads_headers_and_rows():
    headers, rows = extract_table(TABLE_HTML)
    assert headers == ["CodeElem", "Moy"]
    assert rows == [["API101", "12.5"], ["API102", "9"]]


def test_extract_table_raises_when_no_table():
    with pytest.raises(RuntimeError):
        extract_table("<p>no table here</p>")


def test_table_by_headers_matches_subset_or_none():
    headers, rows = table_by_headers(TABLE_HTML, {"CodeElem"})
    assert rows[0] == ["API101", "12.5"]
    assert table_by_headers(TABLE_HTML, {"Nope"}) is None


def test_fingerprint_is_stable_and_sensitive():
    fp1 = fingerprint(["A"], [["1"]])
    fp2 = fingerprint(["A"], [["1"]])
    fp3 = fingerprint(["A"], [["2"]])
    assert fp1 == fp2
    assert fp1 != fp3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tables.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.extractors'`.

- [ ] **Step 3: Create the extractors package and move the helpers**

Create `schoolapp/extractors/__init__.py` (empty). Create `schoolapp/extractors/_tables.py`:

```python
from __future__ import annotations

import hashlib
import json

from bs4 import BeautifulSoup


def normalize_cell(text: str) -> str:
    return " ".join(text.split())


def extract_table(html: str) -> tuple[list[str], list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No table found on marks page")

    best = max(tables, key=lambda t: len(t.find_all("tr")))
    headers = [normalize_cell(th.get_text(" ", strip=True)) for th in best.find_all("th")]

    rows: list[list[str]] = []
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [normalize_cell(td.get_text(" ", strip=True)) for td in tds]
        if any(row):
            rows.append(row)

    return headers, rows


def table_by_headers(html: str, wanted: set[str]) -> tuple[list[str], list[list[str]]] | None:
    """Find the first table whose header row contains all `wanted` columns."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        headers = [normalize_cell(th.get_text(" ", strip=True)) for th in t.find_all("th")]
        if wanted.issubset(set(headers)):
            rows = []
            for tr in t.find_all("tr"):
                tds = [normalize_cell(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
                if tds and any(tds):
                    rows.append(tds)
            return headers, rows
    return None


def fingerprint(headers: list[str], rows: list[list[str]]) -> str:
    payload = json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Rewire `watcher.py` to use the migrated helpers (no behavior change)**

In `schoolapp/watcher.py`:
1. Delete the local `def _normalize_cell`, `def _extract_table`, `def _table_by_headers`, and `def _fingerprint` definitions (they now live in `_tables.py`).
2. Add this import alongside the other `from .` imports near the top of the file (keeps every existing `_normalize_cell(...)`, `_extract_table(...)`, `_table_by_headers(...)`, `_fingerprint(...)` call site working):

```python
from .extractors._tables import (
    normalize_cell as _normalize_cell,
    extract_table as _extract_table,
    table_by_headers as _table_by_headers,
    fingerprint as _fingerprint,
)
```

- [ ] **Step 5: Run the table tests + verify the watcher still imports**

Run: `python -m pytest tests/test_tables.py -v`
Expected: PASS.

Run: `python -c "import schoolapp.watcher, schoolapp.api; print('imports ok')"`
Expected: prints `imports ok` (no NameError / ImportError — proves the migration preserved every call site).

- [ ] **Step 6: Commit**

```bash
git add schoolapp/extractors/__init__.py schoolapp/extractors/_tables.py schoolapp/watcher.py tests/test_tables.py
git commit -m "refactor(extractors): migrate table helpers out of watcher into extractors._tables"
```

---

### Task 4: Authenticated client (`schoolapp/client.py`)

**Files:**
- Create: `schoolapp/client.py`
- Modify: `schoolapp/watcher.py` (import `extract_csrf`/`looks_like_login_page` from `client`; delete local defs)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (uses `requests`, `bs4`).
- Produces: module functions `extract_csrf(html) -> str | None`, `looks_like_login_page(html) -> bool`; class `SchoolAppClient(base_url=SCHOOLAPP_BASE, session=None, timeout=20, min_interval=0.0)` with `login(email, password)`, `_get(path, **params) -> str`, `_post(path, data) -> str` (re-auth once on session expiry; throttled by `min_interval`). Later phases add per-resource methods that call `_get`/`_post`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_client.py`:

```python
import pytest

from schoolapp.client import SchoolAppClient, extract_csrf, looks_like_login_page

LOGIN_HTML = '<form action="/login"><input name="password"><input name="_csrf" value="TOK"></form>'
DASH_HTML = "<h1>Bienvenue</h1>"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    """Serves queued responses; records every request as (method, url, data)."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def _next(self, method, url, data):
        self.calls.append((method, url, data))
        return FakeResponse(self._script.pop(0))

    def get(self, url, params=None, timeout=None):
        return self._next("GET", url, None)

    def post(self, url, data=None, timeout=None):
        return self._next("POST", url, data)


def test_extract_csrf_and_login_page_detection():
    assert extract_csrf(LOGIN_HTML) == "TOK"
    assert extract_csrf(DASH_HTML) is None
    assert looks_like_login_page(LOGIN_HTML) is True
    assert looks_like_login_page(DASH_HTML) is False


def test_login_posts_csrf_token():
    session = FakeSession([LOGIN_HTML, DASH_HTML])  # GET login page, POST -> dashboard
    client = SchoolAppClient(session=session)
    client.login("me@example.test", "pw")
    method, url, data = session.calls[1]
    assert method == "POST"
    assert url.endswith("/login")
    assert data == {"email": "me@example.test", "password": "pw", "_csrf": "TOK"}


def test_login_failure_raises():
    session = FakeSession([LOGIN_HTML, LOGIN_HTML])  # POST still returns login page
    client = SchoolAppClient(session=session)
    with pytest.raises(RuntimeError, match="Login failed"):
        client.login("me@example.test", "bad")


def test_get_reauths_once_on_session_expiry():
    # login (2), then _get: first hit returns login page -> re-login (2) -> retry returns content
    session = FakeSession([LOGIN_HTML, DASH_HTML, LOGIN_HTML, LOGIN_HTML, DASH_HTML, "PAYLOAD"])
    client = SchoolAppClient(session=session)
    client.login("me@example.test", "pw")
    assert client._get("/student/notessem") == "PAYLOAD"


def test_min_interval_throttles(monkeypatch):
    sleeps = []
    monkeypatch.setattr("schoolapp.client.time.sleep", lambda s: sleeps.append(s))
    session = FakeSession([LOGIN_HTML, DASH_HTML])
    client = SchoolAppClient(session=session, min_interval=5.0)
    client.login("me@example.test", "pw")
    assert any(s > 0 for s in sleeps)  # throttled between the GET and POST
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.client'`.

- [ ] **Step 3: Write the client**

Create `schoolapp/client.py`:

```python
from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup

SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
LOGIN_PATH = "/login"


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

    def _throttle(self) -> None:
        if self.min_interval > 0:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()

    def login(self, email: str, password: str) -> None:
        self._email, self._password = email, password
        self._do_login()

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
        return resp.text
```

- [ ] **Step 4: Rewire `watcher.py` to source login helpers from `client` (no behavior change)**

In `schoolapp/watcher.py`:
1. Delete the local `def _extract_csrf` and `def _looks_like_login_page` definitions.
2. Add to the imports near the top:

```python
from .client import extract_csrf as _extract_csrf, looks_like_login_page as _looks_like_login_page
```

(Every existing `_extract_csrf(...)` / `_looks_like_login_page(...)` call site — including in `_login`, `_fetch_extras`, `check_once`, and the health check — keeps working unchanged.)

- [ ] **Step 5: Run the client tests + verify the watcher still imports**

Run: `python -m pytest tests/test_client.py -v`
Expected: PASS — all five tests green.

Run: `python -c "import schoolapp.watcher, schoolapp.api; print('imports ok')"`
Expected: prints `imports ok`.

- [ ] **Step 6: Commit**

```bash
git add schoolapp/client.py schoolapp/watcher.py tests/test_client.py
git commit -m "feat(client): add SchoolAppClient with login/CSRF, re-auth, and rate-limiting"
```

---

### Task 5: Public API export (`schoolapp/__init__.py`)

**Files:**
- Modify: `schoolapp/__init__.py`
- Test: `tests/test_public_api.py`

**Interfaces:**
- Consumes: `SchoolAppClient` (Task 4), `models` (Task 2).
- Produces: `from schoolapp import SchoolAppClient` and `schoolapp.models` accessibility, while preserving the existing `schoolapp.__version__`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_public_api.py`:

```python
def test_public_client_export():
    from schoolapp import SchoolAppClient

    assert SchoolAppClient is not None


def test_version_still_exposed():
    import schoolapp

    assert isinstance(schoolapp.__version__, str)


def test_models_module_accessible():
    from schoolapp import models

    assert hasattr(models, "ElementGrade")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_public_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'SchoolAppClient' from 'schoolapp'`.

- [ ] **Step 3: Add the exports (preserve existing content)**

In `schoolapp/__init__.py`, keep the existing `__version__` assignment and everything already there. Append:

```python
from . import models
from .client import SchoolAppClient

__all__ = ["SchoolAppClient", "models", "__version__"]
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS — every test from Tasks 1–5 green.

Run: `python -c "import schoolapp.cli; print('cli ok')"`
Expected: prints `cli ok` (confirms the new `__init__` imports didn't break the CLI's `from . import __version__`).

- [ ] **Step 5: Commit**

```bash
git add schoolapp/__init__.py tests/test_public_api.py
git commit -m "feat: export SchoolAppClient and models from schoolapp package"
```

---

## Self-Review

**Spec coverage (Phase 1 scope only):**
- §4 models → Task 2 (all 14 dataclasses + `StudentData` bundle, each with `raw`). ✅
- §5 client (`__init__`, `login`, `_get`, `_post`, re-auth, `min_interval`) → Task 4. Per-resource methods (`profile()`, `element_grades()`, …) are **Phase 3+**, out of this plan's scope. ✅
- §6 extractors shared helpers (`_normalize_cell`/`_extract_table`/`_table_by_headers`) → Task 3. Per-resource `parse_*` extractors are **Phase 2**. ✅
- §3 package re-export (`from schoolapp import SchoolAppClient`) → Task 5. ✅
- §7 storage / §8 consumers / §9 notifications / §11 catalog → **later phases**, not this plan.

**Placeholder scan:** none — every step has complete code or an exact command with expected output.

**Type consistency:** `PASS_THRESHOLD` defined in Task 2 and used only there; `ElementGrade.validated`/`is_estimated` signatures match their tests. `extract_csrf`/`looks_like_login_page` names are consistent between `client.py` (Task 4) and the `watcher.py` import alias. Migrated helper names (`normalize_cell`/`extract_table`/`table_by_headers`/`fingerprint`) are consistent between `_tables.py` (Task 3) and the `watcher.py` aliases.

**Deferred to later phase plans:** per-resource extractors returning models + `SchoolAppClient` resource methods + wiring `watcher.py`/`api.py` onto the library (Phase 2); new per-student surface (Phase 3); catalog + `catalog_presets` (Phase 4); documents & archive (Phase 5); notifications digest (Phase 6). Sanitized real HTML fixtures + the `_sanitize.py` helper land in Phase 2 (first real captures).
