# SchoolApp — Comprehensive Extraction Library Design

- **Date:** 2026-06-28 (revised 2026-07-01)
- **Branch:** `android-native-app`
- **Status:** Approved design, ready for implementation planning
- **Scope chosen by user:** Extract **every** data source SchoolApp exposes, behind a reusable Python library that powers the CLI, the Flask API, the watcher, archive/export, and analytics. Watcher caches; API serves cache. Institution-wide curriculum catalog included. Documents downloadable. Notify on every change.

---

## 1. Context

The watcher (`schoolapp/watcher.py`, ~1,500 lines) logs into `https://schoolapp.ensam-umi.ac.ma`
and currently scrapes **5 of ~16** data sources, heavily focused on S4 grades:

- `/student/noteselem-encours` (element marks, current)
- `/student/notesmod-encours` (module results, current)
- `/student/notessem` (semester results)
- `/student/absence/bilan` (absences)
- `/student/absence/sanctions` (sanctions)

The Flask API (`schoolapp/api.py`) serves these from cached snapshots written by the watcher.
`watcher.py` is a monolith mixing HTTP/login, HTML parsing, snapshot persistence, change-diffing,
and email/Telegram rendering. There is no importable extraction library: parsing logic is buried in
private functions and `check_once`.

**Goal:** make the system able to extract *every* piece of information the student-facing SchoolApp
exposes, exposed as a clean, typed, reusable library that the CLI/API/watcher/export all consume.

### 1.1 Live surface map (verified in-browser 2026-06-28)

| Section | Route | Method | Currently scraped |
|---|---|---|---|
| Home: admin + civil-status data | `/index` | GET | ❌ |
| Élements en cours | `/student/noteselem-encours` | GET | ✅ |
| Modules en cours | `/student/notesmod-encours` | GET | ✅ |
| Éléments (full history, all years) | `/student/noteselem` | GET | ❌ |
| Modules (full history, all years) | `/student/notesmod` | GET | ❌ |
| Années (annual results + rank) | `/student/notesannee` | GET | ❌ |
| Semestres | `/student/notessem` | GET | ✅ |
| Diplôme | `/student/notesdiplome` | GET | ❌ (empty for 2A) |
| Mark statistics popup | `/notes-stat/elemevalsat` | GET (params) | ⚠️ partial (`fetch_element_details`) |
| Bilan absences | `/student/absence/bilan` | GET | ✅ |
| Sanctions | `/student/absence/sanctions` | GET | ✅ |
| Mes cours (enrollment) | `/student/inscriptioncours` | GET | ❌ |
| Catalog: modules | `/plan-etudes-view/modules` | **POST** `{niveau,filiere,semestre}` | ❌ |
| Catalog: filières | `/plan-etudes-view/filieres` | GET/POST | ❌ |
| Attestation scolarité | `/student/documents/attestation-scolarite` | GET (PDF) | ❌ |
| Relevé de notes (per year) | linked from `/student/notesannee` | GET (PDF) | ❌ |

**Excluded by design:**
- `/profil/index` — settings page only (profile-photo upload + password change). **The library never
  reads or writes the password fields.** The actual personal data lives on `/index`.
- `/choixform/form/choixfiliere3a`, `/choixform/form/mobilite4a` — time-gated *submission* forms
  (currently "délai dépassé"). Capture the status string only; never submit choices.
- `/files/reglement/*.pdf` — static règlement PDFs (constant links).

### 1.2 Verified shapes

- `/student/noteselem` columns: `CodeElem AU CC EX TP MoySO RAT MoySR Moy Decision` — full history across
  every academic year (e.g. 2024-2025 = 1A: API1xx/API2xx). Superset of `-encours`.
- `/student/notesannee` columns: `Niveau Filière AU Statut "Moy Année" PJ Decesion Classement "Relevé de Notes"`
  (note the site typo `Decesion`; `Classement` like `98 / 419`; `Relevé de Notes` is a PDF link).
  Clicking the average opens a statistics popup (rank/distribution), analogous to element stats.
- `/student/notesdiplome`: renders `"Vous n'avez pas de note de diplome pour le moment !"` when empty —
  must be handled as a non-error empty state.
- `/student/inscriptioncours` columns: `CodeElem Statut Section Groupe S.Groupe Num`.
- `/plan-etudes-view/modules`: three jQuery-driven `<select>`s — `niveau` (7 options: 1A…), `filiere`
  (37 options: API-MPT, GC24, …), `semestre` (`S1`/`S2`) — plus an `input#valid` button that issues a
  **`POST` to the same URL** with those three field names; the server returns the page with a rendered
  HTML table: `CodeMod Intitule Descriptif Niveau Semestre VHMOD CoefMod Seuil Eliminatoire`. The full
  enumeration is 7×37×2 = **518 combinations** (most empty). The page is AdminLTE3 + DataTables; a CSRF
  token is present on the page and must be posted.

---

## 2. Decisions (locked with user)

1. **Reusable library is the primary deliverable.** The CLI, Flask API, watcher, and export/analytics
   are thin consumers of it. (Approach A.)
2. **Architecture:** the watcher fetches and caches; the API serves reads from cache (no per-request
   scraping for GET endpoints). The existing authenticated force-check (`POST /api/check`, which uses
   env credentials) stays as the only API action that triggers a live fetch.
3. **Catalog scope:** the **entire institution** curriculum (all niveaux × filières × semestres).
4. **Documents:** the library exposes descriptors and a `download()`. The watcher/`export` download the
   PDFs into the store; the API lists documents and serves the **cached** PDF copies (it does not log
   into SchoolApp to proxy a live download).
5. **Notifications:** notify on **every change** to per-student resources, delivered as one digest per
   check cycle (catalog handling and delivery details: §9).
6. **Goals served:** archive/export, analytics/calculator, feeding the native Android app, and a
   library to program against.
7. **Catalog feeds the calculator (v1):** module-level definitions (coef, seuil, eliminatoire, VH,
   official title) are derived from the crawled catalog and used by the calculator/validation for any
   filière. Element-level CC/EX/TP weights are **not** exposed by the catalog module endpoint and stay
   sourced from `presets.py` (see §11.1).

---

## 3. Architecture

```
 Consumers │  CLI  ·  Flask API  ·  Watcher  ·  export / archive  ·  analytics
           ▼ (import)
 Library   │  SchoolAppClient  (facade)
           │    ├─ client.py       session · login (CSRF) · _get/_post · auto re-auth · rate-limit
           │    ├─ extractors/     one PURE parser per resource  (HTML → models)
           │    │     ├─ _tables.py   shared table helpers + resource REGISTRY
           │    │     ├─ grades.py · results.py · profile.py · absences.py
           │    │     ├─ courses.py · stats.py · catalog.py · documents.py
           │    ├─ models.py       typed dataclasses (+ `raw` escape hatch)
           │    └─ store.py        persistence (per-resource cache + archive)
           ▼ (HTTP)
           schoolapp.ensam-umi.ac.ma
```

**Boundaries / contracts:**
- **Extractors** are pure functions `parse_X(html: str) -> Model | list[Model]`. No I/O. Fully testable
  from saved HTML fixtures. Internals can change freely as long as the model output is stable.
- **Client** owns all I/O: a `requests.Session`, login/CSRF, re-auth on session expiry, polite
  `min_interval` rate-limiting. Exposes one method per resource returning models, plus aggregates.
- **Store** owns persistence and back-compat. Knows file layout; knows nothing about HTTP/HTML.
- **Consumers** orchestrate library calls; they hold no parsing or HTTP logic of their own.

Package: the library lives under the existing `schoolapp/` package and is re-exported from
`schoolapp/__init__.py` so consumers do `from schoolapp import SchoolAppClient`.

---

## 4. Data models (`schoolapp/models.py`)

Frozen-ish dataclasses, all JSON-serializable via `dataclasses.asdict`. **Every model carries a `raw`
field** capturing the source cells/headers (or key/value pairs), so "every single information" is
preserved even when a column is not explicitly modelled and survives future site changes.

- `StudentProfile`: `code, cne_masar, nom, prenom, nom_ar, prenom_ar, cin, sexe, date_naissance,
  email, filiere, niveau, statut, section, groupe, sous_groupe, photo_url, raw: dict[str,str]`
  (`raw` holds the complete Situation-Administrative + Données-personnelles key/value set).
- `ElementGrade`: `code, au, cc, ex, tp, moy_so, rat, moy_sr, moy, decision, raw`;
  helpers `is_estimated`, `validated`.
- `ModuleGrade`: `code, au, moy, decision, raw`.
- `SemesterResult`: `niveau, semestre, au, moy_sem, pj, decision, classement, releve_url, raw`.
- `YearResult`: `niveau, filiere, au, statut, moy_annee, pj, decision, classement, releve_url, raw`.
- `DiplomaResult`: `empty: bool, message: str | None, rows: list[dict], raw`.
- `Absence`: `element, date, seance, justified: bool, remarks, raw`.
- `Sanction`: `key, value, raw` (the page is a loose key/value table).
- `CourseEnrollment`: `code_elem, statut, section, groupe, sous_groupe, num, raw`.
- `MarkStatistics`: `element, eval_kind, au, note, title, rows: list[list[str]], raw`.
- `CatalogModule`: `code_mod, intitule, descriptif, niveau, semestre, vh_mod, coef_mod, seuil,
  eliminatoire, filiere, raw`.
- `Filiere`: `code, label, raw`.
- `Document`: `kind, url, params: dict, filename, content_type`.
- `StudentData`: aggregate bundle of all per-student resources + `documents: list[Document]`
  (descriptors only — not downloaded bytes) + `fetched_at` + `errors: dict[str,str]` (per-resource
  failures). This is what the watcher caches and `/api/all` and `export` serve.

---

## 5. Client facade (`schoolapp/client.py`)

```python
class SchoolAppClient:
    def __init__(self, base_url=SCHOOLAPP_BASE, session=None, timeout=20, min_interval=0.0): ...
    def login(self, email, password) -> None              # GET login, extract CSRF, POST creds
    def _get(self, path, **params) -> str                 # re-auth once if redirected to /login
    def _post(self, path, data) -> str                    # re-auth once; posts CSRF when required

    # per-student resources
    def profile(self) -> StudentProfile
    def element_grades(self, history=False) -> list[ElementGrade]   # history → /noteselem
    def module_grades(self, history=False) -> list[ModuleGrade]
    def semester_results(self) -> list[SemesterResult]
    def year_results(self) -> list[YearResult]
    def diploma(self) -> DiplomaResult
    def absences(self) -> list[Absence]
    def sanctions(self) -> list[Sanction]
    def courses(self) -> list[CourseEnrollment]
    def mark_statistics(self, code, eval_kind="all") -> list[MarkStatistics]
    def documents(self) -> list[Document]
    def download(self, doc: Document) -> bytes

    # institution-wide catalog
    def catalog_options(self) -> dict          # {niveau:[...], filiere:[...], semestre:[...], csrf:str}
    def catalog_modules(self, niveau, filiere, semestre) -> list[CatalogModule]
    def filieres(self) -> list[Filiere]

    # aggregate
    def fetch_all(self, include_history=True, include_stats=False) -> StudentData
```

`fetch_all` fetches each per-student resource, isolating failures: a resource that raises is recorded
in `StudentData.errors` and skipped; the rest still return. It includes the `Document` **descriptors**
(`documents()`) but never downloads PDF bytes — downloading is an explicit, separate step
(`download(doc)`) driven by the watcher/`export`, so a routine fetch stays lightweight. Re-auth mirrors
the current `check_once` logic (detect `_looks_like_login_page`, re-login once, retry).

---

## 6. Extractors (`schoolapp/extractors/`)

One module per resource group; each exposes pure `parse_*` functions returning models.
`extractors/_tables.py` holds the shared, generalized helpers migrated from `watcher.py`
(`_normalize_cell`, `_extract_table`, `_table_by_headers`) plus a small `REGISTRY` mapping each
table-shaped resource to `(header_signature, row→model factory)` so the many grade/result tables share
one code path. Non-table resources get dedicated handlers:
- `profile.py` — parses the two key/value tables on `/index` into `StudentProfile` (+ full `raw`).
- `stats.py` — the statistics popup (migrate `fetch_element_details`'s popup parsing).
- `catalog.py` — reads the three `<select>` option sets + CSRF (`catalog_options`) and parses the
  POST-response module table.
- `documents.py` — builds `Document` descriptors (attestation, per-year relevés).

**Migration rule:** the existing parsers (`_parse_absence_log`, `_parse_sanctions`,
`_parse_modules_encours`, `_parse_semester_results`, `_extract_table`) move into extractors **with
identical behavior**, so the current watcher/diff tests stay green. The watcher then calls the library
instead of its private functions.

---

## 7. Storage & back-compat (`schoolapp/store.py`)

Layout under `$XDG_STATE_HOME/schoolapp/` (default `~/.local/state/schoolapp/`):

```
schoolapp/
├── s4_snapshot.json           # EXISTING — keep working, untouched format
├── changes.jsonl              # EXISTING — change history
├── student/
│   ├── profile.json  elements.json  modules.json  years.json
│   ├── semesters.json  absences.json  sanctions.json  courses.json
│   └── all.json               # the StudentData bundle
├── catalog/
│   ├── modules.json           # institution-wide; separate refresh cadence
│   └── filieres.json
└── archive/<ISO-timestamp>/   # optional point-in-time full dumps (export/backup)
```

**File envelope & freshness.** Every new per-resource file (everything except the untouched
`s4_snapshot.json` and `changes.jsonl`) is written as `{"fetched_at": <ISO-8601>, "source":
"<route>", "data": <model|list>}` — recording per-resource provenance and staleness (the catalog needs
this for its separate refresh cadence). All store writes use the same atomic `tmp`+`os.replace` pattern
as `_save_snapshot`, so a concurrent API read never sees a half-written file.

**Back-compat is a hard requirement.** The existing `s4_snapshot.json` format and
`_load_snapshot`/`_snapshot_path` keep functioning so today's `/api/grades`, `/api/absences`,
`/api/modules`, `/api/semesters`, `/api/history` endpoints — consumed by the KDE widget and the
Android app — do not break. The new per-resource store is **additive**. Endpoints may be migrated to
the new store later, but only without changing their response contracts.

---

## 8. Consumers

### 8.1 Flask API (`schoolapp/api.py`)
New endpoints, all behind the existing `_auth()` key check, serving from the cache/store:
`/api/profile`, `/api/grades/elements?history=`, `/api/grades/modules?history=`, `/api/years`,
`/api/courses`, `/api/stats/<code>`, `/api/catalog?niveau=&filiere=&semestre=`, `/api/filieres`,
`/api/documents` (listing), `/api/documents/<kind>` (serves the **cached** PDF from the store; 404 if
not yet downloaded by the watcher/export), **`/api/all`** (the `StudentData` bundle), **`/api/export`**
(zip or JSON). Existing endpoints keep their response contracts; `/api/status` additionally gains a
`resources: {name: fetched_at}` freshness map (additive — no existing key changes).

### 8.2 CLI (`schoolapp/cli.py` + namespaces)
New top-level commands alongside `s3`/`s4`: `schoolapp profile`, `schoolapp fetch-all`,
`schoolapp export --out DIR [--format json] [--with-documents]`,
`schoolapp catalog crawl [--filiere ...] [--niveau ...]`, `schoolapp catalog show`. Credentials via
the existing `resolve_credentials`.

### 8.3 Watcher (`schoolapp/watcher.py`)
`check_once` refactored to call `client.fetch_all()`, persist via `store`, then run change-detection
and notifications (see §9). The 2-minute loop fetches per-student resources only. The institution
catalog is **not** in the loop — it is crawled by the separate `catalog crawl` task (manual / weekly
timer).

### 8.4 Export / archive
`schoolapp export` writes the full `StudentData` (+ downloaded PDFs when `--with-documents`) to a
directory or `archive/<ts>/`, satisfying the backup goal.

### 8.5 Native Android app
The Kotlin app at `android/` is standalone (its own `SchoolAppClient.kt`). The Python library is the
reference/parity implementation and can feed the app over the API when the server is reachable; this
spec does not modify the Kotlin app.

---

## 9. Change detection & notifications

User choice: **notify on every change.**

- **Per-student resources** (profile, elements current+history, modules current+history, years,
  semesters, diploma, absences, sanctions, courses): the watcher diffs each cached resource against the
  new fetch and reports every change, via the existing email + Telegram channels. Grades and absences
  keep their current rich card/section rendering; new resource types (profile, years, diploma, courses)
  get a concise generic "what changed" card/section built from the model diff.
  **Delivery is one notification per check cycle:** every changed resource's cards from a single
  `check_once` are bundled into one multi-section email and one Telegram message (matching the current
  watcher, which sends once per cycle) — never one message per changed resource or cell.
- **Institution catalog:** because it is a 518-combination batch crawled on a separate cadence,
  reporting every catalog cell as a grade-style alert would be noise. Instead, `catalog crawl` produces
  a **change summary** (modules added / removed / modified since last crawl) emitted once per crawl.
  This honors "notify on every change" while keeping per-run output sane. *(Flagged for confirmation in
  review.)*

Change history (`changes.jsonl`) gains one entry per detected change, typed by resource.

---

## 10. Error handling

- Login failure → raise a clear `RuntimeError("Login failed: verify email/password")`.
- Session expiry mid-session → `_get/_post` detect the login page and re-authenticate once, then retry;
  a second failure raises.
- Parser finds nothing / structure changed → return empty result + `log("WARNING", …)`; the watcher
  carries the previously cached value forward (generalize the existing `_fetch_extras` None-means-fail
  pattern).
- Empty pages (e.g. diploma) → `DiplomaResult(empty=True, message=…)`, not an error.
- Network errors → propagate to the watcher's existing retry/backoff and failure-alert logic.
- `fetch_all` isolates per-resource failures: one resource raising never aborts the others; failures
  are collected into `StudentData.errors`.
- Catalog crawl → skip empty combos; on a combo error, log and continue; writes are incremental so a
  crash is resumable.

---

## 11. Catalog crawler

`schoolapp/extractors/catalog.py` + a `crawl_catalog(client, niveaux=None, filieres=None)` helper:
1. `catalog_options()` — GET `/plan-etudes-view/modules`, read the three `<select>` option sets and the
   CSRF token.
2. Iterate the (niveau, filiere, semestre) product (default all 518), POST each with the CSRF, parse
   the returned module table into `CatalogModule`s.
3. Dedupe by `(code_mod, niveau, semestre, filiere)`; skip empty responses; respect `min_interval`
   rate-limiting; write `catalog/modules.json` incrementally (resumable).

### 11.1 Catalog-derived module definitions (v1)

`extractors/catalog_presets.py` maps crawled `CatalogModule`s → **module-level** definitions keyed by
`(niveau, filiere, semestre, code_mod)`: official `intitule`, `coef_mod`, `seuil`, `eliminatoire`,
`vh_mod`. A helper `module_defs(niveau, filiere, semestre) -> list[ModuleDef]` (reusing
`presets.ModuleDef` with `elements=[]`, since the catalog carries no element breakdown) reads these from
the cached `catalog/modules.json`, letting the calculator/validation use authoritative module
coefficients and thresholds for **any** filière — not just the hard-coded set.

**Scope boundary (important):** the catalog module endpoint exposes module-level data only. It does
**not** expose element-level CC/EX/TP weights or an element's weight within its module; those stay
sourced from `presets.py` (currently the 2A set). So v1 delivers institution-wide *module* metadata and
module-level validation, while *element-level estimation* (`_compute_moy`) remains limited to filières
that have element presets. On crawl, catalog `coef_mod`/`seuil` are reconciled against `presets.py` and
any mismatch is logged. Deriving element weights (needs a source the catalog doesn't expose) stays out
of scope.

`presets.py` itself is **kept as-is** (not deleted or rewritten); the catalog-derived defs sit
alongside it and the calculator prefers catalog values where available, falling back to presets.

---

## 12. Testing

- **Fixtures:** capture real, **sanitized** HTML per page into `tests/fixtures/` — scrub the student's
  CIN, CNE/Masar, email, photo URL, and name before committing. Include an empty-diploma fixture and at
  least one empty catalog-combo response.
- **Extractor unit tests** (the bulk): `parse_X(fixture_html) == expected_models`, including the site
  typo `Decesion`, the `Classement` "x / y" format, and the `raw` escape hatch.
- **Model tests:** `asdict` round-trips; helper properties (`validated`, `is_estimated`).
- **Client tests:** mocked `requests.Session` — login/CSRF flow, re-auth on login-page redirect,
  `fetch_all` partial-failure isolation, rate-limiting.
- **Catalog crawler test:** over fixture combos incl. an empty one; dedup + resume.
- **Regression:** keep the existing watcher/diff/notification tests green by preserving behavior during
  the parser migration.

---

## 13. Phasing (for the implementation plan)

1. **Library foundation** — `models.py`, `client.py`, `extractors/` (migrate existing parsers
   unchanged) + tests. No behavior change to watcher/API.
2. **Wire existing consumers** — watcher + current API call the library; all current tests still pass.
3. **New per-student surface** — profile/history/years/courses/stats extractors + endpoints
   (`/api/profile`, `/api/years`, `/api/courses`, `/api/stats`, `/api/all`) + CLI `profile`/`fetch-all`.
4. **Catalog** — crawler + `catalog_options`/`catalog_modules` + `catalog_presets` module-def
   derivation (§11.1) + `/api/catalog`, `/api/filieres` + CLI `catalog crawl|show`.
5. **Documents & archive** — `documents()`/`download()` + `/api/documents[/<kind>]` + CLI `export`.
6. **Notifications** — extend change-detection to every per-student resource (one digest per check
   cycle) + catalog change summary.

Each phase is independently shippable and leaves the suite green.

---

## 14. Out of scope (v1)

- Deriving **element-level** CC/EX/TP weights from the catalog (module-level metadata *is* derived in
  v1 — see §11.1; element weights need a source the catalog doesn't expose).
- Submitting choix-filière / mobilité forms (read status only).
- Migrating existing API endpoints off `s4_snapshot.json` (they keep working as-is).
- Changes to the Kotlin Android app's on-device scraper.
- Scraping `/profil/index` settings or any password/photo write actions.
