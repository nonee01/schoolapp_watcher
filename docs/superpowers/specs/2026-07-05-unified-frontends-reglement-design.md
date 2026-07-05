# One SchoolApp — Unified Frontends + Règlement Engine

Date: 2026-07-05 · Status: approved-pending-review · Branch: `android-native-app`

## 1. Goal

Every surface (email digest, CLI, Android app, KDE plasmoid) presents the **same
complete data** with the **same presentation language**, fed by one pipeline:

```
portal → Python client/extractors → store ──→ watcher → email/Telegram + changes.jsonl
                                        ├──→ Flask API (read-through)
                                        │      ├→ Android app (sync + render)
                                        │      └→ KDE plasmoid
                                        └──→ CLI `show` (reads store directly)
```

Site coverage is already complete (user-confirmed): grades (current + history),
modules, semesters, years, diploma, courses, absences, sanctions, stats,
documents PDFs, catalog + filières. Off-limits stays off-limits: `/profil/index`
and any choix-filière/mobilité form submission.

## 2. Decisions (user-approved 2026-07-05)

1. **Android = API-first hybrid.** Screens render exclusively from the Flask
   API/store. The existing Kotlin scraper survives *only* as the
   away-from-laptop background watchdog (local notifications); it never feeds
   the screens.
2. **Unification = design tokens + changes feed.** One committed contract that
   all four frontends implement, plus `/api/changes` so Android and the
   plasmoid show the exact change history the emails narrate.
3. **No Rust rewrite** (delegated decision). The API serves small cached JSON
   over LAN to ≤3 clients; waitress idles at this load. A rewrite would fork
   the codebase into two languages, discard the frozen-contract implementation
   and its passing test suite, and the CLI/store/render share the same Python
   modules the API uses. Bottleneck is the portal itself.
4. **Règlement engine** (new requirement): compute post-rattrapage moyennes and
   decisions ourselves when the portal lags, per the official règlement
   (CE 2019-10-22 / CU 2019-12-25), clearly marked as computed.

## 3. Design-language contract

`design/tokens.json` — single source for:

- **Semantic colors**: `ok` (validated green), `fail` (NV red), `rat`
  (rattrapage yellow), `info` (indigo, current email card color), `muted`,
  `accent`.
- **Status badges**: `VORD → ✓`, `VRAT → ✓ᴿ` (portal's own label), `NV → ✗`,
  `RAT → ⚠`, empty → `–`. Computed (non-official) values get a `*` marker.
- **Resource registry**: canonical id → display name, icon, section order.
  Digest sections, CLI dashboard, Android nav, and plasmoid expanded view all
  iterate this order.

Consumers + parity tests (drift breaks CI, not sameness):

- `schoolapp/render.py` THEME derives from it (Python test).
- `schoolapp/watcher.py` email card colors import it (drop hardcoded hexes).
- Android `ui/theme/Theme.kt` mirrors constants; JVM test reads the JSON via
  relative path and asserts equality.
- Plasmoid `Theme.qml`; asserted in `plasmoid/tests/`.

## 4. Règlement engine — `schoolapp/academics.py`

Pure functions encoding the règlement (verified against live portal values:
Art. 4 reproduces Moy SO to the centime, incl. TP-weighted elements).

- **Art. 4** element SO moyenne: `(C1·(0.3·CC + 0.7·EX) + C2·TP) / (C1 + C2)`
  (no TP → `0.3·CC + 0.7·EX`). Used for verification and what-ifs, not to
  override the portal.
- **Art. 7** element after rattrapage: `max(moy_SO, max(0.3·CC + 0.7·Rat, Rat))`.
  TP/projets/stages are never rattrapés (Art. 8). Elements ≥ 11 (prépa) /
  12 (ing.) are conserved.
- **Art. 5** module moyenne: `Σ Ci·élément_i / Σ Ci`. Coefficient provenance
  chain: catalog store (element weights from crawl) → `presets.py` → equal
  weights + `coeff_assumed: true` caveat surfaced in output.
- **Art. 6** module validation: prépa `moy ≥ 11` and every element ≥ 7;
  cycle ingénieur `moy ≥ 12` and every element ≥ 8.
- **Art. 9** after rattrapage: module validated → final module note is
  **exactly 11.00 / 12.00** (capped) and decision `VRAT`; not validated →
  keep highest note per element, decision `NV`.
- **Art. 11/12/16** year & S5 validation: year moy ≥ 11/12, non-validated
  modules ≤ 2 (prépa) / 3 (ing. years) / 1 (S5), module floor 7/8.
- **Cycle detection**: niveau 1A/2A → prépa; 3A+ → ingénieur (from
  profile/years), overridable constant.

**Computed-fields policy** (runs at store-save time in `fetch_all`
post-processing, so every consumer gets it free):

- Only fills gaps: when `rat` is present and portal's `moy_sr`/decision are
  empty. Official portal values always win; computed fields disappear once the
  portal publishes.
- Additive envelope fields: `moy_sr_computed`, `decision_computed` on elements;
  `moy_computed`, `decision_computed`, `coeff_assumed` on modules; year-level
  `decision_computed`. Frozen API shapes unchanged (additive only).
- Every surface renders computed values visually distinct: CLI dim-italic with
  `*` + caption; email `(computed — portal pending)` suffix; Android outlined
  badge; plasmoid same marker.

Worked example (user's real S4, prépa):
API421 Algèbre 2: CC 16.25, EX 6.0, SO 9.08, Rat 14.5 →
SR = max(9.08, max(0.3·16.25 + 0.7·14.5 = 15.03, 14.5)) = **15.03**;
API452 Prog. Avancée: SO 8.6, Rat 15.0 → SR = **15.00**. Each module then
recomputed per Art. 5/6; if validated → displayed **11.00 / VRAT** (Art. 9 cap).

**Watcher integration**: when a RAT note appears or a computed decision flips,
the digest line narrates it: `Algèbre 2: RAT 14.5 → 15.03* → module API42
VRAT (11.00 final, computed)`.

## 5. API — additive only

- `GET /api/changes?limit=&since=&type=` → tail of `changes.jsonl` via new
  `store.read_changes()`. Missing file → `[]`.
- Computed fields ride along inside existing envelopes (additive).
- Frozen contracts (`/api/status`, `/api/grades/<sem>`, `/api/absences`,
  `/api/modules`, `/api/semesters`, `/api/history`) untouched.

## 6. CLI betterment

- Bare `schoolapp` → **dashboard** when the store has data (profile line,
  latest moyennes incl. computed VRAT outcomes, per-resource freshness, recent
  changes); help otherwise. Explicit `schoolapp dashboard` alias.
- `schoolapp changes [--limit N] [--json]` — the email feed in the terminal.
- `schoolapp explain <ELEMENT_CODE>` — full règlement computation breakdown
  with article citations (CC/EX/TP/Rat, formula application, module rollup,
  decision), `--json` supported.
- S3/S4 consolidated tables fill `Moy SR`/`Moy`/`Status` with computed values
  (styled as computed) when the portal lags.
- Rich help: commands grouped into panels (Read, Live, Server, Catalog),
  examples in help text; `--install-completion` documented in README.

## 7. Android overhaul (API-first hybrid)

- **Data layer**: `data/remote/ApiClient.kt` (OkHttp, `X-API-Key`; base URL +
  key in EncryptedPrefs via Settings). Generic Room `envelope` table
  (resource → JSON, fetched_at) replaces per-type screen entities; existing
  snapshot tables stay for the watchdog. `WatcherRepository.syncFromApi()`
  (GET `/api/all` + `/api/status` + `/api/changes`), pull-to-refresh +
  periodic `ApiSyncWorker` (separate from the scraper watchdog).
- **Screens to email parity** (nav order = token registry order): Dashboard
  (freshness, latest changes, headline moyennes), Grades (current AU /
  history / modules toggles), Results (semesters + years + diploma), Absences
  + Sanctions, Profile, Courses, Stats per element, Documents (list, download
  via `/api/documents/<name>`, open intent), Catalog browser (niveau/filière/
  semestre filters), Changes timeline.
- **Theme**: token colors; one `StatusBadge` composable mirroring
  `render.status_badge` incl. computed marker.
- **Errors**: offline → Room cache + "stale since …" banner; server 404
  (resource not cached) → same empty-hint wording as the CLI.
- Existing `SchoolAppClient.kt` scraper: watchdog-only, labeled "watch mode".

## 8. Plasmoid alignment

Token colors via `Theme.qml`; expanded view adds per-resource freshness and
last-changes list from `/api/changes`; check/pause/resume actions unchanged.

## 9. Out of scope / constraints

- `mobile/` (untracked Expo experiment) untouched.
- No new portal endpoints scraped; never touch `/profil/index` or submit forms.
- Commits per sub-project; never push. PII rules unchanged (règlement-engine
  fixtures are grade numbers + codes only).

## 10. Delivery order

1. **Core** (Python): tokens + règlement engine + `/api/changes` + CLI
   betterment (dashboard/changes/explain/help/S-table computed columns) +
   watcher digest lines + email token colors.
2. **Android** overhaul.
3. **Plasmoid** alignment.

One implementation plan per sub-project.

## 11. Testing

- **Python**: per-article unit tests using the real S4 numbers above as
  fixtures; parity test recomputing portal-published Moy SO (±0.005);
  computed-fields gap-fill policy (official wins, computed disappears);
  `/api/changes` auth + filters; CLI dashboard/changes/explain; token↔THEME
  parity.
- **Android**: JVM tests for ApiClient parsing against envelope fixtures;
  CalculatorTest.kt parity with `academics.py` formulas; token parity.
- **Plasmoid**: extend existing pytest for changes action + theme parity.
