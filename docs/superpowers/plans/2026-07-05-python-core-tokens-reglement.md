# Python Core: Design Tokens + Règlement Engine + Changes Feed + CLI Betterment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sub-project 1 of the unified-frontends spec — one design-token contract, a règlement engine that computes post-rattrapage moyennes/decisions when the portal lags, a `/api/changes` feed, and CLI dashboard/changes/explain commands.

**Architecture:** The Python library stays the single pipeline (client → extractors → store → watcher/API/CLI). New `schoolapp/academics.py` holds pure règlement functions (Decimal math), invoked at the tail of `client.fetch_all()` so computed fields land in every store envelope additively. `schoolapp/tokens.py` loads `schoolapp/design_tokens.json`, from which `render.py` (CLI theme) and `watcher.py` (email hexes) both derive. `store.read_changes()` reads the existing `changes.jsonl` for the new API endpoint and CLI command.

**Tech Stack:** Python 3.11, dataclasses, `decimal.Decimal`, Flask (existing `api.py`), Typer + rich (existing `cli.py`/`render.py`), pytest.

## Global Constraints

- Frozen API contracts must not change shape: `/api/status`, `/api/grades/<sem>`, `/api/absences`, `/api/modules`, `/api/semesters`, `/api/history`. All additions are additive.
- Computed values only **fill gaps** (official portal values always win) and are always marked with a `*` suffix in display strings.
- All règlement arithmetic uses `decimal.Decimal` with `ROUND_HALF_UP` to 2 decimals — binary floats produce 15.02 where the portal publishes 15.03.
- stdout = data, stderr = chrome: results print via `render.console`, logs/banners via `err_console`; `--json` output must stay parseable.
- Never `git push`. Never stage files outside the ones each task lists (the working tree has the user's untracked dirs: `mobile/`, `node_modules/`, `.agents/`, etc.).
- No new portal endpoints are scraped; never touch `/profil/index`.
- Run tests with `.venv/bin/pytest` from the repo root (`/home/notadil/Projects/ensam_school/schoolapp_watcher`). Baseline before Task 1: 92+ passing.
- Règlement source of truth (CE 2019-10-22 / CU 2019-12-25): Art. 4 element SO = `(C1·(0.3·CC + 0.7·EX) + C2·TP)/(C1+C2)`; Art. 7 element SR = `max(SO, max(0.3·CC + 0.7·Rat, Rat))`; Art. 5 module = `Σ Ci·elem / Σ Ci`; Art. 6 validation prépa (1A/2A): moy ≥ 11 and every element ≥ 7 (ingénieur: 12/8); Art. 9 validated-after-rat module displays exactly the bar (11.00/12.00), decision `VRAT`, else keep best notes, `NV`.

---

### Task 1: Design tokens file + loader + render/watcher color unification

**Files:**
- Create: `schoolapp/design_tokens.json`
- Create: `schoolapp/tokens.py`
- Modify: `schoolapp/render.py:19-33` (THEME derives from tokens)
- Modify: `schoolapp/watcher.py` (hardcoded hexes → token lookups: lines ~342-345, ~579-582, and the `"#6366f1"` info card at ~1178)
- Modify: `pyproject.toml` (package-data for the JSON)
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: `tokens.load_tokens() -> dict` (cached), `tokens.color(name) -> dict` with keys `hex`, `hex_bg`, `rich`; `tokens.STATUS_BADGES: dict[str, dict]`; `tokens.RESOURCES: list[dict]` with keys `id`, `name`, `icon` in canonical section order; `tokens.COMPUTED_MARKER = "*"`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tokens.py
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
    # Tokens codify the exact hexes the emails already use — no visual change.
    assert tokens.color("ok")["hex"] == "#166534" and tokens.color("ok")["hex_bg"] == "#dcfce7"
    assert tokens.color("fail")["hex"] == "#991b1b" and tokens.color("fail")["hex_bg"] == "#fee2e2"
    assert tokens.color("muted")["hex"] == "#374151" and tokens.color("muted")["hex_bg"] == "#f3f4f6"
    assert tokens.color("info")["hex"] == "#6366f1"


def test_watcher_has_no_hardcoded_status_hexes():
    src = Path("schoolapp/watcher.py").read_text(encoding="utf-8")
    for hexcode in ("#166534", "#991b1b", "#374151", "#6366f1"):
        assert hexcode not in src, f"{hexcode} should come from tokens"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tokens.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.tokens'`

- [ ] **Step 3: Create the tokens JSON**

```json
{
  "computed_marker": "*",
  "colors": {
    "ok":      {"hex": "#166534", "hex_bg": "#dcfce7", "rich": "bold green"},
    "fail":    {"hex": "#991b1b", "hex_bg": "#fee2e2", "rich": "bold red"},
    "rat":     {"hex": "#ca8a04", "hex_bg": "#fef9c3", "rich": "bold yellow"},
    "info":    {"hex": "#6366f1", "hex_bg": "#e0e7ff", "rich": "cyan"},
    "success": {"hex": "#16a34a", "hex_bg": "#dcfce7", "rich": "green"},
    "warning": {"hex": "#ca8a04", "hex_bg": "#fef9c3", "rich": "yellow"},
    "error":   {"hex": "#991b1b", "hex_bg": "#fee2e2", "rich": "bold red"},
    "muted":   {"hex": "#374151", "hex_bg": "#f3f4f6", "rich": "dim"},
    "header":  {"hex": "#7c3aed", "hex_bg": "#ede9fe", "rich": "bold magenta"},
    "accent":  {"hex": "#0891b2", "hex_bg": "#cffafe", "rich": "cyan"}
  },
  "statuses": {
    "VORD": {"symbol": "✓", "style": "ok"},
    "VRAT": {"symbol": "✓ᴿ", "style": "ok"},
    "V":    {"symbol": "✓", "style": "ok"},
    "NV":   {"symbol": "✗", "style": "fail"},
    "RAT":  {"symbol": "⚠", "style": "rat"}
  },
  "resources": [
    {"id": "student/profile",         "name": "Profil étudiant",            "icon": "👤"},
    {"id": "student/elements",        "name": "Notes des éléments",         "icon": "📊"},
    {"id": "student/modules",         "name": "Résultats modules",          "icon": "📦"},
    {"id": "student/semesters",       "name": "Résultats semestres",        "icon": "🧾"},
    {"id": "student/years",           "name": "Résultats d'année",          "icon": "📅"},
    {"id": "student/diploma",         "name": "Diplôme",                    "icon": "🎓"},
    {"id": "student/courses",         "name": "Inscriptions aux cours",     "icon": "📚"},
    {"id": "student/absences",        "name": "Absences",                   "icon": "🕐"},
    {"id": "student/absence_summary", "name": "Bilan des absences",         "icon": "🧮"},
    {"id": "student/sanctions",       "name": "Sanctions",                  "icon": "⚖️"},
    {"id": "student/stats",           "name": "Statistiques des notes",     "icon": "📈"},
    {"id": "student/documents",       "name": "Documents",                  "icon": "📄"},
    {"id": "catalog/modules",         "name": "Catalogue des modules",      "icon": "🗂️"},
    {"id": "catalog/filieres",        "name": "Filières",                   "icon": "🏫"}
  ]
}
```

Save as `schoolapp/design_tokens.json` (inside the package so it ships with installs; Android/plasmoid parity tests read it by relative path from the repo).

- [ ] **Step 4: Write `schoolapp/tokens.py`**

```python
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
```

- [ ] **Step 5: Derive render.THEME from tokens**

In `schoolapp/render.py`, replace the static `THEME = Theme({...})` block (lines 19-30) with:

```python
from . import tokens

THEME = Theme({name: c["rich"] for name, c in tokens.load_tokens()["colors"].items()})
```

Do not change `status_badge()` behavior in this task (existing tests in `tests/test_render.py` pin its semantics).

- [ ] **Step 6: Replace watcher hardcoded hexes with token lookups**

In `schoolapp/watcher.py`, add near the top imports:

```python
from .tokens import color as _tok
```

Then replace each status hex pair with token lookups. The three call sites (find them with `grep -n '"#' schoolapp/watcher.py`):

`_status_style` (~line 340):

```python
        if val >= 11.0:
            return _tok("ok")["hex"], _tok("ok")["hex_bg"], "✓ Validé"
        return _tok("fail")["hex"], _tok("fail")["hex_bg"], "✗ Non validé"
    except (ValueError, AttributeError):
        return _tok("muted")["hex"], _tok("muted")["hex_bg"], "En attente"
```

The decision-style helper (~line 579):

```python
        return _tok("ok")["hex"], _tok("ok")["hex_bg"], f"✓ {d}"
...
        return _tok("fail")["hex"], _tok("fail")["hex_bg"], "✗ NV"
    return _tok("muted")["hex"], _tok("muted")["hex_bg"], d if d and d != "--" else "En attente"
```

The absence-card colors (~line 604): `fg = _tok("ok")["hex"] if justified else _tok("fail")["hex"]` and `bg = _tok("ok")["hex_bg"] if justified else _tok("fail")["hex_bg"]`, and the justified card header `_simple_card(_tok("ok")["hex"], ...)`.

The generic-digest card (~line 1178): `_simple_card(_tok("info")["hex"], "SchoolApp", _gtitle, "<br>".join(_glines))`.

Other decorative hexes (`#111827`, `#2563eb`, `#16a34a` inline accents) may stay; the test only bans the four status hexes.

- [ ] **Step 7: Add package-data to pyproject.toml**

Open `pyproject.toml`; under the setuptools config add (create the table if absent):

```toml
[tool.setuptools.package-data]
schoolapp = ["design_tokens.json"]
```

- [ ] **Step 8: Run the new tests + full suite**

Run: `.venv/bin/pytest tests/test_tokens.py tests/test_render.py tests/test_watcher_wiring.py -v` then `.venv/bin/pytest -q`
Expected: all PASS (email HTML bytes unchanged because token hexes equal the old literals).

- [ ] **Step 9: Commit**

```bash
git add schoolapp/design_tokens.json schoolapp/tokens.py schoolapp/render.py schoolapp/watcher.py pyproject.toml tests/test_tokens.py
git commit -m "feat(tokens): design-language contract shared by CLI theme and email palette"
```

---

### Task 2: Règlement engine core — Decimal math, Art. 4/7, computed model fields

**Files:**
- Create: `schoolapp/academics.py`
- Modify: `schoolapp/models.py:30-65` (additive computed fields)
- Test: `tests/test_academics.py`

**Interfaces:**
- Produces:
  - `academics.parse_note(value: str | None) -> Decimal | None` (strips `*`, accepts `,` decimals; `""`/`"--"` → None)
  - `academics.fmt_note(value: Decimal) -> str` (2 decimals, ROUND_HALF_UP: `Decimal("15.025") → "15.03"`)
  - `academics.Bars(module_pass: Decimal, element_floor: Decimal, keep: Decimal)` and `academics.bars_for(niveau: str) -> Bars` (1A/2A → 11/7/11; else 12/8/12)
  - `academics.element_moy_so(cc, ex, tp, c1, c2) -> Decimal` (Art. 4)
  - `academics.element_moy_sr(moy_so, cc, rat) -> Decimal` (Art. 7)
  - `models.ElementGrade` gains `moy_sr_computed: str = ""`, `decision_computed: str = ""`
  - `models.ModuleGrade` gains `moy_computed: str = ""`, `decision_computed: str = ""`, `coeff_assumed: bool = False`
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_academics.py
"""Règlement engine (CE 2019-10-22 / CU 2019-12-25). Real S4 values from the
user's transcript are the fixtures: the portal's own published numbers pin
Art. 4 rounding (9.075 → 9.08 means decimal half-up, not float banker's)."""

from decimal import Decimal

from schoolapp import academics as ac


def test_parse_note():
    assert ac.parse_note("9.08") == Decimal("9.08")
    assert ac.parse_note("15,5") == Decimal("15.5")
    assert ac.parse_note("14.93*") == Decimal("14.93")
    assert ac.parse_note("--") is None and ac.parse_note("") is None and ac.parse_note(None) is None


def test_fmt_note_rounds_half_up_like_the_portal():
    assert ac.fmt_note(Decimal("15.025")) == "15.03"   # float math would give 15.02
    assert ac.fmt_note(Decimal("9.075")) == "9.08"
    assert ac.fmt_note(Decimal("15")) == "15.00"


def test_bars_for_cycle():
    prepa = ac.bars_for("2A")
    assert (prepa.module_pass, prepa.element_floor) == (Decimal("11"), Decimal("7"))
    ing = ac.bars_for("3A")
    assert (ing.module_pass, ing.element_floor) == (Decimal("12"), Decimal("8"))


def test_element_moy_so_art4_matches_portal():
    # API411: 0.3·11.5 + 0.7·14.25 = 13.425 → 13.43 (no TP)
    assert ac.fmt_note(ac.element_moy_so(
        cc=Decimal("11.5"), ex=Decimal("14.25"), tp=None,
        c1=Decimal("5"), c2=Decimal("0"))) == "13.43"
    # API441 with TP: (8·(0.3·17.18 + 0.7·14.0) + 1·15.23)/9 = 14.985… → 14.99±0.01 of portal 14.98
    val = ac.element_moy_so(cc=Decimal("17.18"), ex=Decimal("14.0"), tp=Decimal("15.23"),
                            c1=Decimal("8"), c2=Decimal("1"))
    assert abs(val - Decimal("14.98")) <= Decimal("0.01")


def test_element_moy_sr_art7_real_cases():
    # API421 Algèbre 2: max(9.08, max(0.3·16.25 + 0.7·14.5, 14.5)) = 15.025 → 15.03
    sr = ac.element_moy_sr(moy_so=Decimal("9.08"), cc=Decimal("16.25"), rat=Decimal("14.5"))
    assert ac.fmt_note(sr) == "15.03"
    # API452 Prog Avancée: max(8.6, max(14.55, 15.0)) = 15.00 (Rat alone wins)
    sr = ac.element_moy_sr(moy_so=Decimal("8.6"), cc=Decimal("13.5"), rat=Decimal("15.0"))
    assert ac.fmt_note(sr) == "15.00"
    # No CC → max(SO, Rat)
    assert ac.element_moy_sr(moy_so=Decimal("9.0"), cc=None, rat=Decimal("10.0")) == Decimal("10.0")
    # SO better than rat session → SO stands (Art. 7 Sup)
    assert ac.element_moy_sr(moy_so=Decimal("10.9"), cc=Decimal("5.0"), rat=Decimal("9.0")) == Decimal("10.9")


def test_models_gain_additive_computed_fields():
    from dataclasses import asdict
    from schoolapp.models import ElementGrade, ModuleGrade
    e = asdict(ElementGrade())
    assert e["moy_sr_computed"] == "" and e["decision_computed"] == ""
    m = asdict(ModuleGrade())
    assert m["moy_computed"] == "" and m["decision_computed"] == "" and m["coeff_assumed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_academics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schoolapp.academics'`

- [ ] **Step 3: Add the computed fields to models.py**

In `schoolapp/models.py`, add to `ElementGrade` after `decision: str = ""` (line 41):

```python
    moy_sr_computed: str = ""    # règlement Art. 7 — filled only when the portal lags
    decision_computed: str = ""  # "VRAT"/"NV" from the module rollup (Art. 6/9)
```

Add to `ModuleGrade` after `decision: str = ""` (line 64):

```python
    moy_computed: str = ""       # Art. 9 final (capped at the bar when validated)
    decision_computed: str = ""
    coeff_assumed: bool = False  # True when coefficients were guessed (equal weights)
```

- [ ] **Step 4: Write `schoolapp/academics.py` (core)**

```python
"""Règlement engine — evaluation rules CE 2019-10-22 / CU 2019-12-25.

Pure Decimal functions (the portal rounds half-up: 9.075 → 9.08; binary floats
would give 15.02 where it publishes 15.03). Computed values only ever FILL GAPS
the portal has not published yet, and display strings carry a `*` marker.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PREPA_NIVEAUX = {"1A", "2A"}


def parse_note(value: str | None) -> Decimal | None:
    raw = (value or "").strip().rstrip("*").replace(",", ".")
    if not raw or raw == "--":
        return None
    try:
        return Decimal(raw)
    except ArithmeticError:
        return None


def fmt_note(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Bars:
    """Art. 6/7/9 thresholds. prépa (1A/2A): 11/7/11 — cycle ingénieur: 12/8/12."""
    module_pass: Decimal
    element_floor: Decimal
    keep: Decimal


def bars_for(niveau: str) -> Bars:
    if (niveau or "").strip().upper()[:2] in PREPA_NIVEAUX:
        return Bars(Decimal("11"), Decimal("7"), Decimal("11"))
    return Bars(Decimal("12"), Decimal("8"), Decimal("12"))


def element_moy_so(*, cc: Decimal | None, ex: Decimal | None, tp: Decimal | None,
                   c1: Decimal, c2: Decimal) -> Decimal:
    """Art. 4: (C1·(0.3·CC + 0.7·EX) + C2·TP) / (C1 + C2)."""
    base = Decimal("0.3") * (cc or Decimal(0)) + Decimal("0.7") * (ex or Decimal(0))
    if tp is None or c2 == 0:
        return base
    return (c1 * base + c2 * tp) / (c1 + c2)


def element_moy_sr(*, moy_so: Decimal | None, cc: Decimal | None, rat: Decimal) -> Decimal:
    """Art. 7: Sup[SO ; Sup[(0.3·CC + 0.7·Rat) ; Rat]] — TP never rattrapé (Art. 8)."""
    rat_session = max(Decimal("0.3") * cc + Decimal("0.7") * rat, rat) if cc is not None else rat
    return max(moy_so if moy_so is not None else Decimal(0), rat_session)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_academics.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add schoolapp/academics.py schoolapp/models.py tests/test_academics.py
git commit -m "feat(academics): règlement engine core — Art. 4/7 Decimal math + computed model fields"
```

---

### Task 3: Module rollup (Art. 5/6/9) + StudentData annotation + fetch_all hook

**Files:**
- Modify: `schoolapp/academics.py` (append)
- Modify: `schoolapp/client.py` (tail of `fetch_all`, right before `return data` — currently `schoolapp/client.py:287`)
- Test: `tests/test_academics.py` (append)

**Interfaces:**
- Consumes: `presets.modules_for_semester(semester) -> list[ModuleDef]` (ModuleDef: `code, title, niveau, semestre, coef_mod, seuil, eliminatoire, elements[ElementDef(code, title, coef_cc, coef_ex, coef_ecrit, coef_tp, coef_eelem)]`); `store.load_resource("catalog/modules")`; Task 2 functions.
- Produces:
  - `academics.module_def_for(element_code: str) -> ModuleDef | None` (presets S3+S4 first, then catalog store, else None)
  - `academics.ModuleOutcome` dataclass: `code: str, moy: str, final: str, decision: str, coeff_assumed: bool`
  - `academics.module_after_rat(mdef, notes: dict[str, Decimal], niveau: str) -> ModuleOutcome` — `notes` maps element code → effective moyenne (SR where rattrapé, else SO)
  - `academics.annotate_student_data(data: StudentData) -> list[str]` — fills the `*_computed` fields, returns human digest lines (empty when nothing to compute)
- Later tasks rely on: `annotate_student_data` running inside `client.fetch_all()`, and the digest lines format `"{elem}: RAT {rat} → Moy SR {sr}* → module {mod}: {decision} ({final}*)"`.

- [ ] **Step 1: Write the failing tests (append to tests/test_academics.py)**

```python
def _elem(code, au="24/25", cc="", ex="", moy="", rat="", moy_sr="", decision=""):
    from schoolapp.models import ElementGrade
    return ElementGrade(code=code, au=au, cc=cc, ex=ex, moy=moy, rat=rat,
                        moy_sr=moy_sr, decision=decision)


def test_module_def_for_uses_presets():
    mdef = ac.module_def_for("API421")
    assert mdef is not None and mdef.code.upper() == "API42"
    assert ac.module_def_for("ZZZ999") is None


def test_module_after_rat_validates_and_caps():
    mdef = ac.module_def_for("API452")  # module API45: Méthodes numériques + Prog Avancée
    notes = {e.code: Decimal("15.00") if e.code == "API452" else Decimal("11.14")
             for e in mdef.elements}
    out = ac.module_after_rat(mdef, notes, "2A")
    assert out.decision == "VRAT"
    assert out.final == "11.00"          # Art. 9 cap at the prépa bar
    assert Decimal(out.moy) > Decimal("11")   # true weighted moyenne, pre-cap
    assert out.coeff_assumed is False


def test_module_after_rat_element_floor_blocks_validation():
    mdef = ac.module_def_for("API452")
    notes = {e.code: Decimal("6.5") if e.code == "API451" else Decimal("18.0")
             for e in mdef.elements}
    out = ac.module_after_rat(mdef, notes, "2A")
    assert out.decision == "NV"          # element < 7 kills it (Art. 6)
    assert out.final == out.moy          # no cap when not validated


def test_annotate_fills_gaps_and_respects_official_values():
    from schoolapp.models import ModuleGrade, StudentData, StudentProfile
    data = StudentData(
        profile=StudentProfile(niveau="2A"),
        element_grades=[
            _elem("API421", cc="16.25", ex="6.0", moy="9.08", rat="14.5", decision="RAT"),
            _elem("API451", cc="", ex="6.75", moy="11.14", decision="VORD"),
            _elem("API452", cc="13.5", ex="6.5", moy="8.6", rat="15.0", decision="RAT"),
            # official SR already published → engine must NOT touch it
            _elem("API411", moy="13.43", rat="10.0", moy_sr="13.43", decision="VORD"),
        ],
        module_grades=[ModuleGrade(code="API45", au="24/25", moy="", decision="")],
    )
    lines = ac.annotate_student_data(data)
    by_code = {e.code: e for e in data.element_grades}
    assert by_code["API421"].moy_sr_computed == "15.03"
    assert by_code["API452"].moy_sr_computed == "15.00"
    assert by_code["API452"].decision_computed == "VRAT"
    assert by_code["API411"].moy_sr_computed == ""   # official value won
    assert by_code["API451"].moy_sr_computed == ""   # no RAT taken
    mod = data.module_grades[0]
    assert mod.decision_computed == "VRAT" and mod.moy_computed == "11.00"
    assert any("API421" in ln for ln in lines) and any("API452" in ln for ln in lines)


def test_annotate_is_noop_without_rat_notes():
    from schoolapp.models import StudentData, StudentProfile
    data = StudentData(profile=StudentProfile(niveau="2A"),
                       element_grades=[_elem("API411", moy="13.43", decision="VORD")])
    assert ac.annotate_student_data(data) == []
    assert data.element_grades[0].moy_sr_computed == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_academics.py -v -k "module_def or module_after or annotate"`
Expected: FAIL — `AttributeError: module 'schoolapp.academics' has no attribute 'module_def_for'`

- [ ] **Step 3: Append the rollup + annotation to academics.py**

```python
# ── module resolution (presets → catalog store) ──────────────────────────

def _preset_defs():
    from .presets import modules_for_semester
    out = []
    for sem in ("S3", "S4"):
        out.extend(modules_for_semester(sem))
    return out


def module_def_for(element_code: str):
    """ModuleDef owning an element: presets (S3/S4) first, then the catalog store."""
    code = (element_code or "").strip().upper()
    if not code:
        return None
    for mdef in _preset_defs():
        if any(e.code.upper() == code for e in mdef.elements):
            return mdef
    env_defs = _catalog_defs()
    for mdef in env_defs:
        if any(e.code.upper() == code for e in mdef.elements):
            return mdef
    return None


def _catalog_defs():
    """Catalog envelopes → ModuleDefs (weights captured by the crawl, spec §11.1)."""
    from . import store
    from .presets import ElementDef, ModuleDef

    env = store.load_resource("catalog/modules")
    if not env or not isinstance(env.get("data"), list):
        return []
    out = []
    for m in env["data"]:
        elems = [
            ElementDef(
                code=str(e.get("code", "")),
                title=str(e.get("intitule", "")),
                coef_cc=float(parse_note(e.get("coef_cc")) or 0.3),
                coef_ex=float(parse_note(e.get("coef_ex")) or 0.7),
                coef_ecrit=float(parse_note(e.get("coef_ecrit")) or 1.0),
                coef_tp=float(parse_note(e.get("coef_tp")) or 0.0),
                coef_eelem=float(parse_note(e.get("coef_eelem")) or 1.0),
            )
            for e in (m.get("elements") or [])
        ]
        if elems:
            out.append(ModuleDef(
                code=str(m.get("code_mod", "")), title=str(m.get("intitule", "")),
                niveau=str(m.get("niveau", "")), semestre=str(m.get("semestre", "")),
                coef_mod=float(parse_note(m.get("coef_mod")) or 1.0),
                seuil=float(parse_note(m.get("seuil")) or 11.0),
                eliminatoire=float(parse_note(m.get("eliminatoire")) or 7.0),
                elements=elems,
            ))
    return out


# ── module rollup (Art. 5/6/9) ───────────────────────────────────────────

@dataclass
class ModuleOutcome:
    code: str
    moy: str             # weighted moyenne, pre-cap (Art. 5)
    final: str           # displayed note (Art. 9 cap when validated)
    decision: str        # "VRAT" | "NV"
    coeff_assumed: bool


def module_after_rat(mdef, notes: dict[str, Decimal], niveau: str) -> ModuleOutcome:
    """Art. 5 weighted moyenne over effective notes, Art. 6 validation, Art. 9 cap.

    `notes` maps element code → effective moyenne (SR where rattrapé else SO).
    Elements of the module missing from `notes` are ignored (coeff_assumed=True).
    """
    bars = Bars(Decimal(str(mdef.seuil)), Decimal(str(mdef.eliminatoire)),
                Decimal(str(mdef.seuil))) if mdef is not None else bars_for(niveau)
    assumed = mdef is None
    if mdef is not None:
        weights = {e.code.upper(): Decimal(str(e.coef_eelem)) for e in mdef.elements}
        missing = set(weights) - {c.upper() for c in notes}
        if missing:
            assumed = True
        pairs = [(notes[c], weights.get(c.upper(), Decimal(1))) for c in notes]
        code = mdef.code
    else:
        pairs = [(v, Decimal(1)) for v in notes.values()]
        code = ""
    total_w = sum(w for _, w in pairs) or Decimal(1)
    moy = sum(v * w for v, w in pairs) / total_w
    validated = moy >= bars.module_pass and all(v >= bars.element_floor for v, _ in pairs)
    final = bars.module_pass if validated else moy   # Art. 9
    return ModuleOutcome(code=code, moy=fmt_note(moy), final=fmt_note(final),
                         decision="VRAT" if validated else "NV", coeff_assumed=assumed)


# ── StudentData annotation (gap-fill only; official values always win) ───

def annotate_student_data(data) -> list[str]:
    """Fill *_computed fields for rattrapé elements the portal hasn't rolled up.

    Returns human lines for digests: one per computed element.
    """
    niveau = (data.profile.niveau if data.profile else "") or "2A"
    # group candidates: same AU + same module
    pending: dict[tuple[str, str], list] = {}
    for g in data.element_grades:
        rat = parse_note(g.rat)
        if rat is None or parse_note(g.moy_sr) is not None:
            continue
        mdef = module_def_for(g.code)
        mod_code = mdef.code.upper() if mdef else (g.code.strip().upper()[:-1] or g.code)
        pending.setdefault((mod_code, g.au), []).append(g)

    lines: list[str] = []
    for (mod_code, au), rattrapes in pending.items():
        mdef = module_def_for(rattrapes[0].code)
        # effective notes for every element of this module visible in this AU
        notes: dict[str, Decimal] = {}
        srs: dict[str, Decimal] = {}
        member = ({e.code.upper() for e in mdef.elements} if mdef
                  else {g.code.upper() for g in rattrapes})
        for g in data.element_grades:
            if g.au != au or g.code.upper() not in member:
                continue
            rat = parse_note(g.rat)
            official_sr = parse_note(g.moy_sr)
            so = parse_note(g.moy) or parse_note(g.moy_so)
            if official_sr is not None:
                notes[g.code] = official_sr
            elif rat is not None:
                sr = element_moy_sr(moy_so=so, cc=parse_note(g.cc), rat=rat)
                notes[g.code] = srs[g.code] = sr
            elif so is not None:
                notes[g.code] = so
        if not srs:
            continue
        outcome = module_after_rat(mdef, notes, niveau)
        for g in rattrapes:
            if g.code not in srs:
                continue
            g.moy_sr_computed = fmt_note(srs[g.code])
            g.decision_computed = outcome.decision
            lines.append(
                f"{g.code}: RAT {g.rat} → Moy SR {g.moy_sr_computed}* → "
                f"module {mod_code}: {outcome.decision} ({outcome.final}*)")
        for m in data.module_grades:
            if m.code.upper() == mod_code and m.au == au and parse_note(m.moy) is None \
                    and m.decision.strip() in ("", "--", "RAT"):
                m.moy_computed = outcome.final
                m.decision_computed = outcome.decision
                m.coeff_assumed = outcome.coeff_assumed
    return lines
```

- [ ] **Step 4: Hook into client.fetch_all**

In `schoolapp/client.py`, immediately before `return data` at the end of `fetch_all` (line ~287, after the `include_stats` block):

```python
        try:
            from .academics import annotate_student_data
            annotate_student_data(data)
        except Exception as exc:  # noqa: BLE001 — computed fields are best-effort
            data.errors["academics"] = str(exc)
        return data
```

(Replace the existing bare `return data`.)

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_academics.py -v` then `.venv/bin/pytest -q`
Expected: all PASS. If `tests/test_fetch_all.py` asserts exact `errors` dict contents or envelope keys, adjust ONLY assertions that enumerate dataclass fields exhaustively (the new fields are additive; do not weaken behavioral assertions).

- [ ] **Step 6: Commit**

```bash
git add schoolapp/academics.py schoolapp/client.py tests/test_academics.py
git commit -m "feat(academics): Art. 5/6/9 module rollup + fetch_all gap-fill annotation"
```

---

### Task 4: Consolidated S3/S4 table overlay + watcher rattrapage digest

**Files:**
- Modify: `schoolapp/academics.py` (append `overlay_snapshot_rows`)
- Modify: `schoolapp/watcher.py` (`_render_consolidated_snapshot` ~line 259; `check_once` generic-changes block ~line 1140)
- Test: `tests/test_academics.py` (overlay), `tests/test_generic_diffs.py` (digest entry)

**Interfaces:**
- Consumes: snapshot table headers `["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec", ...]` and rows of strings (the legacy snapshot format); Task 3's `element_moy_sr`, `module_def_for`, `module_after_rat`.
- Produces: `academics.overlay_snapshot_rows(headers: list[str], rows: list[list[str]], semester: str, niveau: str = "2A") -> tuple[list[list[str]], list[str]]` — copy of rows with `MoySR`/`Moy`/`Dec` gap-filled as `"15.03*"`/`"VRAT*"`, plus digest lines. Watcher emits changes.jsonl entries with `"type": "rattrapage"`.

- [ ] **Step 1: Write the failing overlay test (append to tests/test_academics.py)**

```python
def test_overlay_snapshot_rows_fills_computed_cells():
    headers = ["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    rows = [
        ["API411", "11.5", "14.25", "", "13.43", "", "", "13.43", "VORD"],
        ["API421", "16.25", "6.0", "", "9.08", "14.5", "", "9.08", "RAT"],
    ]
    new_rows, lines = ac.overlay_snapshot_rows(headers, rows, "S4")
    assert rows[1][6] == ""                      # input untouched (copy)
    assert new_rows[0] == rows[0]                # VORD row untouched
    idx = {h: i for i, h in enumerate(headers)}
    assert new_rows[1][idx["MoySR"]] == "15.03*"
    assert new_rows[1][idx["Moy"]] == "15.03*"
    assert new_rows[1][idx["Dec"]].endswith("*") and "V" in new_rows[1][idx["Dec"]]
    assert lines and "API421" in lines[0]


def test_overlay_leaves_published_sr_alone():
    headers = ["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    rows = [["API421", "16.25", "6.0", "", "9.08", "14.5", "12.00", "12.00", "VRAT"]]
    new_rows, lines = ac.overlay_snapshot_rows(headers, rows, "S4")
    assert new_rows == rows and lines == []
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_academics.py -k overlay -v`
Expected: FAIL — no attribute `overlay_snapshot_rows`

- [ ] **Step 3: Append overlay to academics.py**

```python
# ── legacy snapshot-table overlay (s3/s4 consolidated table) ─────────────

def overlay_snapshot_rows(headers: list[str], rows: list[list[str]],
                          semester: str, niveau: str = "2A") -> tuple[list[list[str]], list[str]]:
    """Gap-fill MoySR/Moy/Dec cells (as "15.03*" / "VRAT*") on a copy of the rows."""
    idx = {h: i for i, h in enumerate(headers)}
    needed = {"CodeElem", "CC", "MoySO", "RAT", "MoySR", "Moy", "Dec"}
    if not needed <= set(idx):
        return rows, []

    def cell(row, key):
        i = idx[key]
        return row[i].strip() if i < len(row) else ""

    out = [list(r) for r in rows]
    # candidate elements grouped by module
    pending: dict[str, list[int]] = {}
    for n, r in enumerate(out):
        if parse_note(cell(r, "RAT")) is None or parse_note(cell(r, "MoySR")) is not None:
            continue
        code = cell(r, "CodeElem").upper()
        if not code:
            continue
        mdef = module_def_for(code)
        pending.setdefault(mdef.code.upper() if mdef else code[:-1], []).append(n)

    lines: list[str] = []
    for mod_code, row_idx in pending.items():
        mdef = module_def_for(cell(out[row_idx[0]], "CodeElem"))
        member = ({e.code.upper() for e in mdef.elements} if mdef
                  else {cell(out[n], "CodeElem").upper() for n in row_idx})
        notes: dict[str, Decimal] = {}
        srs: dict[int, Decimal] = {}
        for n, r in enumerate(out):
            code = cell(r, "CodeElem").upper()
            if code not in member:
                continue
            official_sr, rat = parse_note(cell(r, "MoySR")), parse_note(cell(r, "RAT"))
            so = parse_note(cell(r, "MoySO")) or parse_note(cell(r, "Moy"))
            if official_sr is not None:
                notes[code] = official_sr
            elif rat is not None:
                sr = element_moy_sr(moy_so=so, cc=parse_note(cell(r, "CC")), rat=rat)
                notes[code] = sr
                srs[n] = sr
            elif so is not None:
                notes[code] = so
        if not srs:
            continue
        outcome = module_after_rat(mdef, notes, niveau)
        for n, sr in srs.items():
            marked = fmt_note(sr) + "*"
            out[n][idx["MoySR"]] = marked
            out[n][idx["Moy"]] = marked
            out[n][idx["Dec"]] = outcome.decision + "*"
            lines.append(
                f"{cell(out[n], 'CodeElem')}: RAT {cell(out[n], 'RAT')} → Moy SR {marked} → "
                f"module {mod_code}: {outcome.decision} ({outcome.final}*)")
    return out, lines
```

- [ ] **Step 4: Wire into `_render_consolidated_snapshot`**

In `schoolapp/watcher.py`, at the top of `_render_consolidated_snapshot` (after the `if "CodeElem" not in headers: return` guard, line ~262), insert:

```python
    from .academics import overlay_snapshot_rows
    rows, computed_lines = overlay_snapshot_rows(headers, rows, semester)
```

In the same function's decision styling block (~line 316), add a branch **before** the `dec == "VORD"` case:

```python
        if dec.endswith("*"):
            dec_styled = f"[italic green]{dec}[/italic green]" if dec.startswith("V") \
                else f"[italic red]{dec}[/italic red]"
        elif dec == "VORD":
```

(keep the existing `elif` chain), and after `console.print(table)` add:

```python
    if computed_lines:
        console.print("[dim]* calculé selon le règlement (Art. 7/9) — en attente de publication[/dim]")
```

- [ ] **Step 5: Write the failing digest test (append to tests/test_generic_diffs.py)**

Look at the existing tests in `tests/test_generic_diffs.py` for the established pattern (they run `watcher.check_once` twice over `FakeSession` fixtures with `XDG_STATE_HOME` monkeypatched and inspect `changes.jsonl` / sent emails). Add:

```python
def test_rattrapage_computed_lands_in_digest_and_changes(tmp_path, monkeypatch):
    """A RAT note appearing (with no published Moy SR) must produce a
    'rattrapage' changes.jsonl entry and a digest section on the SECOND run
    (first run = baseline, no alert)."""
    import json
    from schoolapp import watcher
    from tests.test_fetch_all import FakeSession

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    kw = dict(email="e@x.t", password="p", timeout=5, semester="S4",
              state_file=None, notify_email=False, config=None)

    watcher.check_once(session=FakeSession(), **kw)          # baseline

    # second run: fixture already contains RAT rows without Moy SR, so the
    # computed values exist in both runs → no diff. Simulate the RAT note
    # APPEARING by wiping the stored computed value from the baseline envelope.
    from schoolapp import store
    env = store.load_resource("student/elements")
    for g in env["data"]:
        g["rat"], g["moy_sr_computed"], g["decision_computed"] = "", "", ""
    store.save_resource("student/elements", env["data"], source="test")

    watcher.check_once(session=FakeSession(), **kw)

    hist = (tmp_path / "schoolapp" / "changes.jsonl").read_text(encoding="utf-8")
    entries = [json.loads(l) for l in hist.splitlines()]
    assert any(e["type"] == "rattrapage" for e in entries)
```

NOTE: if the S4 fixtures contain no element with a RAT note and empty Moy SR (they were captured before the rattrapage session), the wipe trick above has nothing to diff. In that case keep the baseline run as-is and monkeypatch the second run's fetch instead:

```python
    from schoolapp.client import SchoolAppClient

    real_fetch_all = SchoolAppClient.fetch_all

    def rat_fetch_all(self, *a, **k):
        data = real_fetch_all(self, *a, **k)
        for g in data.element_grades:
            if g.code == "API421" and not g.rat:
                g.rat, g.moy_sr, g.moy_sr_computed = "14.5", "", ""
        from schoolapp.academics import annotate_student_data
        annotate_student_data(data)   # re-annotate with the injected RAT note
        return data

    monkeypatch.setattr(SchoolAppClient, "fetch_all", rat_fetch_all)
    watcher.check_once(session=FakeSession(), **kw)
```

Assertion stays identical. Do not capture new portal fixtures for this.

- [ ] **Step 6: Add the digest hook in check_once**

In `schoolapp/watcher.py` inside `check_once`, find the line that builds the generic diffs (search `generic_changes = _generic_resource_diffs(data)`), and insert right after it:

```python
    rat_lines = _rattrapage_diff(data)
    if rat_lines:
        generic_changes.append(
            ("rattrapage", "Rattrapage — résultats calculés (règlement)", rat_lines))
```

Then add the helper next to `_generic_resource_diffs`:

```python
def _rattrapage_diff(data) -> list[str]:
    """New/changed computed rattrapage outcomes vs the stored baseline.
    No baseline envelope → no alert (mirrors _generic_resource_diffs)."""
    env = store.load_resource("student/elements")
    if not env or not isinstance(env.get("data"), list):
        return []
    old = {(g.get("code"), g.get("au")): g.get("moy_sr_computed") or ""
           for g in env["data"]}
    lines: list[str] = []
    for g in data.element_grades:
        if g.moy_sr_computed and old.get((g.code, g.au), "") != g.moy_sr_computed:
            lines.append(f"{g.code}: RAT {g.rat} → Moy SR {g.moy_sr_computed}* "
                         f"({g.decision_computed})")
    return lines
```

The tuple flows automatically into the email sections, Telegram parts, `changed` flag, and the `changes.jsonl` writer (all iterate `generic_changes`).

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/test_academics.py tests/test_generic_diffs.py tests/test_watcher_wiring.py -v` then `.venv/bin/pytest -q`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add schoolapp/academics.py schoolapp/watcher.py tests/test_academics.py tests/test_generic_diffs.py
git commit -m "feat(rattrapage): computed Moy SR/decision in consolidated tables + watcher digest"
```

---

### Task 5: `store.read_changes` + `GET /api/changes`

**Files:**
- Modify: `schoolapp/store.py` (append)
- Modify: `schoolapp/api.py` (append endpoint; verify `request` is imported from flask — add it to the existing `from flask import ...` line if missing)
- Test: `tests/test_store_changes.py`, `tests/test_api.py` (append)

**Interfaces:**
- Consumes: `changes.jsonl` lines like `{"ts": "2026-07-05T15:12:18", "type": "grades", "semester": "S4", "summary": "..."}` (written by `watcher._append_history`).
- Produces: `store.changes_path(directory=None) -> Path`; `store.read_changes(*, limit=50, since=None, type=None, directory=None) -> list[dict]` newest-first; `GET /api/changes?limit=&since=&type=` → `{"changes": [...], "count": N}` (200 even when empty; 401 without key).

- [ ] **Step 1: Write the failing store test**

```python
# tests/test_store_changes.py
import json

from schoolapp import store


def _write(tmp_path, entries):
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def test_read_changes_newest_first_with_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    _write(tmp_path, [
        {"ts": "2026-07-01T10:00:00", "type": "grades", "semester": "S4", "summary": "a"},
        {"ts": "2026-07-02T10:00:00", "type": "absences", "semester": "S4", "summary": "b"},
        {"ts": "2026-07-03T10:00:00", "type": "grades", "semester": "S4", "summary": "c"},
    ])
    items = store.read_changes()
    assert [i["summary"] for i in items] == ["c", "b", "a"]
    assert [i["summary"] for i in store.read_changes(limit=1)] == ["c"]
    assert [i["summary"] for i in store.read_changes(type="grades")] == ["c", "a"]
    assert [i["summary"] for i in store.read_changes(since="2026-07-01T23:59:59")] == ["c", "b"]


def test_read_changes_absent_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert store.read_changes() == []
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"ts": "2026-07-01", "type": "x", "summary": "ok"}\nnot-json\n', encoding="utf-8")
    assert [i["summary"] for i in store.read_changes()] == ["ok"]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_store_changes.py -v`
Expected: FAIL — `AttributeError: module 'schoolapp.store' has no attribute 'read_changes'`

- [ ] **Step 3: Append to store.py**

```python
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
```

- [ ] **Step 4: Write the failing API test (append to tests/test_api.py)**

Follow the file's existing client/auth fixture pattern (it already tests `_auth` guarded endpoints with `X-API-Key`). Add:

```python
def test_changes_endpoint(tmp_path, monkeypatch, client):
    # adapt fixture names to this file's conventions; API_KEY env + test client
    import json
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ts": "2026-07-05T15:00:00", "type": "rattrapage",
                             "semester": "S4", "summary": "API421 → 15.03*"}) + "\n",
                 encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert client.get("/api/changes").status_code == 401   # no key

    r = client.get("/api/changes", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1 and body["changes"][0]["type"] == "rattrapage"

    r = client.get("/api/changes?type=grades", headers={"X-API-Key": "k"})
    assert r.get_json() == {"changes": [], "count": 0}
```

- [ ] **Step 5: Append endpoint to api.py (after the `/api/filieres` route)**

```python
@app.get("/api/changes")
def changes():
    """The watcher's change history — the same feed the email digests narrate."""
    err = _auth()
    if err:
        return err
    try:
        limit = max(0, int(request.args.get("limit", 50)))
    except ValueError:
        limit = 50
    items = store.read_changes(limit=limit, since=request.args.get("since") or None,
                               type=request.args.get("type") or None)
    return jsonify({"changes": items, "count": len(items)})
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_store_changes.py tests/test_api.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add schoolapp/store.py schoolapp/api.py tests/test_store_changes.py tests/test_api.py
git commit -m "feat(api): /api/changes — change history feed from changes.jsonl"
```

---

### Task 6: `schoolapp changes` + `schoolapp dashboard` + bare-invocation dashboard

**Files:**
- Modify: `schoolapp/render.py` (append `changes_table`, `dashboard_view`)
- Modify: `schoolapp/cli.py` (app config line ~43, `main` callback ~91, two new commands)
- Test: `tests/test_render.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `store.read_changes` (Task 5), `store.freshness`, `store.RESOURCE_FILES`, `tokens.RESOURCES` (Task 1), existing renderers `semesters_table`, `freshness_table`, `empty_hint`.
- Produces: `render.changes_table(items: list[dict]) -> Table`; `render.dashboard_view(profile: dict | None, semesters: list[dict], freshness: dict, changes: list[dict], store_dir: str) -> Group`; CLI commands `changes`, `dashboard`; bare `schoolapp` renders the dashboard when the store has data, help otherwise.

- [ ] **Step 1: Write the failing render tests (append to tests/test_render.py)**

```python
def test_changes_table_and_dashboard_view():
    changes = [{"ts": "2026-07-05T15:00:00", "type": "rattrapage",
                "semester": "S4", "summary": "API421 → 15.03*"}]
    assert "rattrapage" in _render(render.changes_table(changes))
    out = _render(render.dashboard_view(
        {"prenom": "A", "nom": "B", "filiere": "API", "niveau": "2A"},
        [{"niveau": "2A", "semestre": "S4", "au": "24", "moy_sem": "12", "decision": "V"}],
        {"student/all": "2026-07-05"}, changes, "/tmp/store"))
    assert "A B" in out and "S4" in out and "rattrapage" in out and "/tmp/store" in out
    # empty-safe
    assert _render(render.dashboard_view(None, [], {}, [], "/tmp/store"))
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_render.py -k "changes_table" -v`
Expected: FAIL — no attribute `changes_table`

- [ ] **Step 3: Append renderers to render.py**

```python
def changes_table(items: list[dict]) -> Table:
    rows = [[c.get("ts", ""), c.get("type", ""), c.get("semester", ""), c.get("summary", "")]
            for c in items]
    return data_table(f"Changes ({len(items)})", ["When", "Type", "Sem", "Summary"], rows)


def dashboard_view(profile: dict | None, semesters: list[dict],
                   freshness: dict[str, str | None], changes: list[dict],
                   store_dir: str) -> Group:
    parts: list[Any] = []
    if profile:
        who = " ".join(x for x in (profile.get("prenom"), profile.get("nom")) if x)
        line = Text(who or "Étudiant", style="header")
        meta = " · ".join(x for x in (profile.get("filiere"), profile.get("niveau")) if x)
        if meta:
            line.append(f"  {meta}", style="muted")
        parts.append(line)
    if semesters:
        parts.append(semesters_table(semesters[-4:]))
    if changes:
        parts.append(changes_table(changes[:8]))
    parts.append(freshness_table(store_dir, freshness))
    return Group(*parts)
```

- [ ] **Step 4: Write the failing CLI tests (append to tests/test_cli.py)**

```python
def test_changes_command_reads_history(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ts": "2026-07-05T15:00:00", "type": "rattrapage",
                             "semester": "S4", "summary": "API421 → 15.03*"}) + "\n",
                 encoding="utf-8")
    human = runner.invoke(app, ["changes"])
    assert human.exit_code == 0 and "rattrapage" in human.output
    data = json.loads(runner.invoke(app, ["-q", "changes", "--json"]).output)
    assert data[0]["type"] == "rattrapage"


def test_bare_invocation_shows_dashboard_or_help(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    empty = runner.invoke(app, [])
    assert empty.exit_code == 0
    assert "fetch-all" in empty.output          # empty store → guidance/help

    _seed_store(tmp_path, monkeypatch)
    dash = runner.invoke(app, [])
    assert dash.exit_code == 0
    assert "State store" in dash.output         # freshness table = dashboard marker

    explicit = runner.invoke(app, ["dashboard"])
    assert explicit.exit_code == 0 and "State store" in explicit.output
```

- [ ] **Step 5: Run to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py -k "changes_command or bare_invocation" -v`
Expected: FAIL (`No such command 'changes'` / bare invocation prints help without store awareness — the first assertion may pass, the seeded-store one must fail)

- [ ] **Step 6: Implement in cli.py**

6a. App config (line ~41): change `no_args_is_help=True` to `no_args_is_help=False` in the main `typer.Typer(...)` (sub-apps keep theirs).

6b. Callback: change the decorator to `@app.callback(invoke_without_command=True)` and add at the END of `main(...)` (after the `if config:` block):

```python
    if ctx.invoked_subcommand is None:
        _dashboard_impl(json_out=False)
```

6c. Add the shared implementation + commands (place near the `status` command, ~line 275):

```python
def _dashboard_impl(json_out: bool) -> None:
    names = list(RESOURCE_FILES.values()) + ["catalog/modules", "catalog/filieres"]
    fresh = store.freshness(names)
    if not any(fresh.values()):
        render.console.print(render.empty_hint("data"))
        render.console.print("Run [accent]schoolapp --help[/accent] to see all commands.")
        return
    profile_env = store.load_resource("student/profile")
    sems_env = store.load_resource("student/semesters")
    changes = store.read_changes(limit=8)
    if json_out:
        _emit_json({"profile": (profile_env or {}).get("data"),
                    "semesters": (sems_env or {}).get("data") or [],
                    "resources": fresh, "changes": changes})
        return
    render.console.print(render.dashboard_view(
        (profile_env or {}).get("data"), (sems_env or {}).get("data") or [],
        fresh, changes, str(store.state_dir())))


@app.command("dashboard")
def dashboard(json_out: bool = JSON_OPT) -> None:
    """Overview: who you are, latest results, store freshness, recent changes."""
    _dashboard_impl(json_out=json_out)


@app.command("changes")
def changes_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries (newest first)"),
    type: str | None = typer.Option(None, "--type", help="Filter by change type (grades, rattrapage, absences…)"),
    json_out: bool = JSON_OPT,
) -> None:
    """Change history — the same feed the email digests narrate."""
    items = store.read_changes(limit=limit, type=type)
    if json_out:
        _emit_json(items)
        return
    if not items:
        render.console.print(render.empty_hint("changes"))
        return
    render.console.print(render.changes_table(items))
```

NOTE: `_dashboard_impl` must be defined before `main` references it at import time only if called — Python resolves it at call time, so placement after `main` is fine.

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/test_cli.py tests/test_render.py -v` then `.venv/bin/pytest -q`
Expected: all PASS. Watch for regressions in tests that invoked `runner.invoke(app, [])` expecting help text — update only if their intent was "no crash".

- [ ] **Step 8: Commit**

```bash
git add schoolapp/render.py schoolapp/cli.py tests/test_render.py tests/test_cli.py
git commit -m "feat(cli): dashboard (bare invocation) + changes feed command"
```

---

### Task 7: `schoolapp explain <CODE>` — règlement breakdown

**Files:**
- Modify: `schoolapp/academics.py` (append `explain_element`)
- Modify: `schoolapp/cli.py` (new command)
- Test: `tests/test_academics.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: store envelope `student/elements` (list of element dicts incl. computed fields), Task 2/3 functions.
- Produces: `academics.explain_element(code: str, items: list[dict]) -> dict | None` returning:

```python
{"code": "API421", "au": "24/25",
 "inputs": {"cc": "16.25", "ex": "6.0", "tp": "", "moy_so": "9.08",
            "rat": "14.5", "moy_sr": "", "decision": "RAT"},
 "steps": [
   {"article": "Art. 4", "label": "Moyenne session ordinaire",
    "formula": "0.3·CC + 0.7·EX", "value": "9.08", "official": True},
   {"article": "Art. 7", "label": "Moyenne après rattrapage",
    "formula": "max(SO, max(0.3·CC + 0.7·Rat, Rat))", "value": "15.03", "official": False},
   {"article": "Art. 5/6/9", "label": "Module API42",
    "formula": "Σ Ci·élément / Σ Ci ≥ 11 → plafonné à 11.00", "value": "VRAT (11.00*)",
    "official": False},
 ]}
```

(`None` when the code has no row; rows without RAT get only the Art. 4 step; the module step is present only when a rollup was computable.)

- [ ] **Step 1: Write the failing engine test (append to tests/test_academics.py)**

```python
def test_explain_element_full_rattrapage_story():
    items = [
        {"code": "API421", "au": "24/25", "cc": "16.25", "ex": "6.0", "tp": "",
         "moy": "9.08", "rat": "14.5", "moy_sr": "", "decision": "RAT",
         "moy_sr_computed": "15.03", "decision_computed": "VRAT"},
    ]
    exp = ac.explain_element("api421", items)
    assert exp["code"] == "API421"
    arts = [s["article"] for s in exp["steps"]]
    assert "Art. 4" in arts[0] and any("Art. 7" in a for a in arts)
    art7 = next(s for s in exp["steps"] if "Art. 7" in s["article"])
    assert art7["value"] == "15.03" and art7["official"] is False
    assert ac.explain_element("NOPE", items) is None


def test_explain_element_without_rat_is_art4_only():
    items = [{"code": "API411", "au": "24/25", "cc": "11.5", "ex": "14.25", "tp": "",
              "moy": "13.43", "rat": "", "moy_sr": "", "decision": "VORD",
              "moy_sr_computed": "", "decision_computed": ""}]
    exp = ac.explain_element("API411", items)
    assert len(exp["steps"]) == 1 and "Art. 4" in exp["steps"][0]["article"]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_academics.py -k explain -v`
Expected: FAIL — no attribute `explain_element`

- [ ] **Step 3: Append to academics.py**

```python
# ── explanation (schoolapp explain CODE) ─────────────────────────────────

def explain_element(code: str, items: list[dict]) -> dict | None:
    """Règlement walkthrough for one element, built from store envelope dicts.
    Picks the latest AU row for the code (prefers one with a RAT note)."""
    code_up = (code or "").strip().upper()
    rows = [g for g in items if str(g.get("code", "")).upper() == code_up]
    if not rows:
        return None
    rows.sort(key=lambda g: (bool(parse_note(g.get("rat"))), str(g.get("au", ""))))
    g = rows[-1]

    so = parse_note(g.get("moy")) or parse_note(g.get("moy_so"))
    steps = [{
        "article": "Art. 4", "label": "Moyenne session ordinaire",
        "formula": "0.3·CC + 0.7·EX (pondérée TP le cas échéant)",
        "value": fmt_note(so) if so is not None else "--", "official": True,
    }]
    rat = parse_note(g.get("rat"))
    if rat is not None:
        official_sr = parse_note(g.get("moy_sr"))
        if official_sr is not None:
            sr_val, official = fmt_note(official_sr), True
        else:
            sr_val = g.get("moy_sr_computed") or fmt_note(
                element_moy_sr(moy_so=so, cc=parse_note(g.get("cc")), rat=rat))
            official = False
        steps.append({
            "article": "Art. 7", "label": "Moyenne après rattrapage",
            "formula": "max(SO, max(0.3·CC + 0.7·Rat, Rat))",
            "value": sr_val, "official": official,
        })
        mdef = module_def_for(code_up)
        if mdef is not None and g.get("decision_computed"):
            bar = fmt_note(Decimal(str(mdef.seuil)))
            steps.append({
                "article": "Art. 5/6/9", "label": f"Module {mdef.code}",
                "formula": (f"Σ Ci·élément / Σ Ci ≥ {bar} et chaque élément ≥ "
                            f"{fmt_note(Decimal(str(mdef.eliminatoire)))} → "
                            f"validé plafonné à {bar}"),
                "value": f"{g['decision_computed']} ({bar}*)"
                         if g["decision_computed"] == "VRAT" else g["decision_computed"],
                "official": False,
            })
    return {
        "code": code_up, "au": str(g.get("au", "")),
        "inputs": {k: str(g.get(k) or "") for k in
                   ("cc", "ex", "tp", "moy_so", "rat", "moy_sr", "decision")},
        "steps": steps,
    }
```

Note: `explain_element` needs `moy_so` fallback — envelope rows built from `ElementGrade` carry both `moy` and `moy_so` keys.

- [ ] **Step 4: Write the failing CLI test (append to tests/test_cli.py)**

```python
def test_explain_command(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch)
    result = runner.invoke(app, ["explain", "API311"])
    assert result.exit_code == 0 and "Art. 4" in result.output
    data = json.loads(runner.invoke(app, ["-q", "explain", "API311", "--json"]).output)
    assert data["code"] == "API311" and data["steps"]
    missing = runner.invoke(app, ["explain", "ZZZ999"])
    assert missing.exit_code == 1
```

- [ ] **Step 5: Add the CLI command (cli.py, next to `dashboard`)**

```python
@app.command("explain")
def explain(
    code: str = typer.Argument(..., help="Element code, e.g. API421"),
    json_out: bool = JSON_OPT,
) -> None:
    """Règlement walkthrough for one element: how SO/SR/decision are computed."""
    from .academics import explain_element

    env = store.load_resource("student/elements")
    items = (env or {}).get("data") or []
    exp = explain_element(code, items)
    if exp is None:
        if json_out:
            _emit_json(None)
        else:
            render.console.print(render.error_panel(
                f"No cached grades for {code.upper()}.",
                hint="Run `schoolapp fetch-all` first, or check the code."))
        raise typer.Exit(code=1)
    if json_out:
        _emit_json(exp)
        return
    inp = exp["inputs"]
    render.console.print(render.data_table(
        f"{exp['code']} · AU {exp['au']}", ["CC", "EX", "TP", "Moy SO", "RAT", "Moy SR", "Décision"],
        [[inp["cc"] or "--", inp["ex"] or "--", inp["tp"] or "--", inp["moy_so"] or "--",
          inp["rat"] or "--", inp["moy_sr"] or "--", inp["decision"] or "--"]]))
    rows = [[s["article"], s["label"], s["formula"], s["value"],
             "officiel" if s["official"] else "calculé*"] for s in exp["steps"]]
    render.console.print(render.data_table(
        "Règlement (CE 2019-10-22 / CU 2019-12-25)",
        ["Article", "Étape", "Formule", "Valeur", "Source"], rows,
        caption="* calculé par l'outil — en attente de publication par le portail"))
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_academics.py tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add schoolapp/academics.py schoolapp/cli.py tests/test_academics.py tests/test_cli.py
git commit -m "feat(cli): explain — règlement walkthrough per element with article citations"
```

---

### Task 8: Year/semester validation rules (Art. 11/12/16)

**Files:**
- Modify: `schoolapp/academics.py` (append `year_outcome`)
- Test: `tests/test_academics.py` (append)

**Interfaces:**
- Consumes: module rows as dicts `{"code": str, "moy": str, "decision": str, "moy_computed": str, "decision_computed": str}` (store envelope shape, computed fields from Task 3).
- Produces: `academics.year_outcome(modules: list[dict], niveau: str) -> dict` — pure rule check, no gap-fill wiring (jury publishes year decisions; Android/CLI surfaces consume this later):

```python
{"moy": "12.10",              # coef_mod-weighted moyenne over effective module notes
 "non_valides": ["API45"],    # modules whose effective decision is NV
 "floor_breach": [],          # modules with effective moyenne < 7 (prépa) / 8 (ing.)
 "conditions": {"moyenne": True, "nv_count": True, "floor": True},
 "would_validate": True, "computed": True}   # computed=True when any *_computed was used
```

Rules: prépa (Art. 11) — year moy ≥ 11, NV count ≤ 2, every module moy ≥ 7. Cycle ingénieur years (Art. 12) — 12 / ≤ 3 / 8. (S5's ≤ 1 rule, Art. 16, is out of scope here — S5 rows aren't distinguishable in the module envelope; document this in the docstring.)

- [ ] **Step 1: Write the failing tests (append to tests/test_academics.py)**

```python
def _mod(code, moy="", decision="", moy_c="", dec_c=""):
    return {"code": code, "moy": moy, "decision": decision,
            "moy_computed": moy_c, "decision_computed": dec_c}


def test_year_outcome_art11_conditions():
    mods = [_mod("API41", "13.43", "VORD"),
            _mod("API42", "", "RAT", moy_c="11.00", dec_c="VRAT"),   # computed VRAT counts
            _mod("API44", "14.98", "VORD"),
            _mod("API45", "8.60", "NV")]
    out = ac.year_outcome(mods, "2A")
    assert out["non_valides"] == ["API45"]
    assert out["conditions"]["nv_count"] is True        # 1 NV ≤ 2
    assert out["conditions"]["floor"] is True           # all ≥ 7
    assert out["computed"] is True                      # used a *_computed value
    assert isinstance(out["would_validate"], bool)


def test_year_outcome_floor_and_count_breaches():
    mods = [_mod("API41", "6.50", "NV"), _mod("API42", "10.00", "NV"),
            _mod("API44", "10.50", "NV"), _mod("API45", "15.00", "VORD")]
    out = ac.year_outcome(mods, "2A")
    assert out["conditions"]["nv_count"] is False       # 3 NV > 2
    assert "API41" in out["floor_breach"]               # 6.50 < 7
    assert out["would_validate"] is False
    assert out["computed"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_academics.py -k year_outcome -v`
Expected: FAIL — no attribute `year_outcome`

- [ ] **Step 3: Append to academics.py**

```python
# ── year validation (Art. 11/12; Art. 16 S5 not distinguishable here) ────

def year_outcome(modules: list[dict], niveau: str) -> dict:
    """Art. 11 (prépa) / Art. 12 (cycle ingénieur years) condition check over
    module envelope rows. Uses *_computed values when official ones are absent
    (and flags `computed: True`). Purely informative — the jury decides."""
    bars = bars_for(niveau)
    nv_max = 2 if (niveau or "").strip().upper()[:2] in PREPA_NIVEAUX else 3

    used_computed = False
    weighted: list[tuple[Decimal, Decimal]] = []
    non_valides: list[str] = []
    floor_breach: list[str] = []
    for m in modules:
        moy = parse_note(m.get("moy"))
        dec = (m.get("decision") or "").strip()
        if moy is None and m.get("moy_computed"):
            moy, used_computed = parse_note(m.get("moy_computed")), True
        if not dec and m.get("decision_computed"):
            dec, used_computed = m["decision_computed"], True
        if moy is None:
            continue
        mdef = None
        for md in _preset_defs() + _catalog_defs():
            if md.code.upper() == str(m.get("code", "")).upper():
                mdef = md
                break
        coef = Decimal(str(mdef.coef_mod)) if mdef else Decimal(1)
        weighted.append((moy, coef))
        if dec.upper().startswith("NV"):
            non_valides.append(str(m.get("code", "")))
        if moy < bars.element_floor:
            floor_breach.append(str(m.get("code", "")))

    total = sum(w for _, w in weighted) or Decimal(1)
    year_moy = sum(v * w for v, w in weighted) / total
    conditions = {
        "moyenne": year_moy >= bars.module_pass,
        "nv_count": len(non_valides) <= nv_max,
        "floor": not floor_breach,
    }
    return {"moy": fmt_note(year_moy), "non_valides": non_valides,
            "floor_breach": floor_breach, "conditions": conditions,
            "would_validate": all(conditions.values()), "computed": used_computed}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_academics.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add schoolapp/academics.py tests/test_academics.py
git commit -m "feat(academics): Art. 11/12 year validation rule check"
```

---

### Task 9: Help polish (panels + examples) + README + full verification

**Files:**
- Modify: `schoolapp/cli.py` (add `rich_help_panel=` to commands, refresh epilog)
- Modify: `README.md` (CLI section: new commands, completion note)
- Test: existing suite (no new tests; help output asserted by existing `test_cli_help_lists_library_commands`)

**Interfaces:** none new.

- [ ] **Step 1: Group commands into help panels**

Add `rich_help_panel=...` to each `@app.command(...)` decorator in `cli.py`:

- `"Read (offline, from the store)"`: `dashboard`, `changes`, `explain`, `status`, `export`
- `"Live (logs into the portal)"`: `profile`, `fetch-all`, `doctor`
- `"Server"`: `serve`
- and to each `app.add_typer(...)` call add the same keyword: `s3`/`s4` → `"Semesters"`, `catalog` → `"Catalog"`, `show` → `"Read (offline, from the store)"`, `documents` → `"Live (logs into the portal)"`.

Example: `@app.command("dashboard", rich_help_panel="Read (offline, from the store)")`.

Update the app epilog (line ~51) to:

```python
    epilog=("Examples: schoolapp             (dashboard)  |  schoolapp changes\n"
            "          schoolapp explain API421  |  schoolapp s4 table  |  schoolapp serve\n"
            "Shell completion: schoolapp --install-completion"),
```

- [ ] **Step 2: Update README CLI section**

Find the CLI usage section in `README.md` (search for `schoolapp `) and add a short block documenting: bare `schoolapp` dashboard, `changes`, `explain CODE` (règlement walkthrough incl. computed rattrapage results marked `*`), and `schoolapp --install-completion` for shell completion. Keep the existing content style; a few lines, not an essay.

- [ ] **Step 3: Run the full suite + smoke the help**

Run: `.venv/bin/pytest -q` — Expected: all PASS (baseline 92 + ~25 new).
Run: `.venv/bin/schoolapp --help` — Expected: commands grouped under the panels above.
Run: `.venv/bin/schoolapp` — Expected: dashboard (store already populated on this machine) with the S4 rattrapage rows visible as `15.03*` / `VRAT*` once `fetch-all` has run under the new code.

- [ ] **Step 4: Commit**

```bash
git add schoolapp/cli.py README.md
git commit -m "feat(cli): grouped rich help panels + README for dashboard/changes/explain"
```
