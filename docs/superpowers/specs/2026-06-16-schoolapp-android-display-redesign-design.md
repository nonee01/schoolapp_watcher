# SchoolApp Android — Display Redesign & Grade Tools

- **Date:** 2026-06-16
- **Branch:** `android-native-app`
- **Status:** Approved design, ready for implementation planning
- **Scope chosen by user:** Full — display polish + interactive grade tools + analytics

## 1. Context

The native Kotlin/Jetpack Compose app at `android/` is complete and **standalone**: it scrapes the
ENSAM portal directly from the phone (`SchoolAppClient.kt`), runs a foreground watcher service with
WorkManager recovery, persists to Room, and ships as a 1.97 MB R8 release APK verified on the user's
Redmi (commit `012eb9f`). 40 unit tests pass. Six tabs: Statut, Notes, Absences, Résultats,
Historique, Réglages.

The scraping/watcher/diff/service/Telegram core works well. What is rough is **how academic data is
presented**. This redesign reworks the presentation layer only — it does **not** touch scraping,
auth, the watcher service, change-detection, or Telegram, except for one additive hook to capture an
average time-series for trends (§9).

## 2. Goals / Non-goals

**Goals**
- Make Notes and Résultats clear, color-coded, and honest about what is official vs estimated.
- Add interactive grade tools (what-if simulator, validation tracker) that emails cannot provide.
- Add lightweight analytics (average trend, strength/weakness heatmap) and a home-screen widget.
- Dark mode, Material icons, consistent empty/loading/error states.
- Move display-mapping logic out of composables into a **pure, tested** presentation layer.

**Non-goals**
- No change to scraping, login, watcher scheduling, diff logic, or notification content.
- No new backend / API / Firebase / FCM. The app stays standalone.
- No new semesters beyond the existing S3/S4 presets.
- No multi-user / social features.

## 3. Problems in the current display (grounded)

1. Element grades render as a single run-on string `"CC .. · EX .. · TP .. · Moy .. · Dec"`
   (`ui/components/Cards.kt:93`) — no hierarchy, no color, and shows `EX —`/`TP —` clutter for
   elements that don't use those columns.
2. The validation threshold (`seuil = 11`, present in `domain/Presets.kt`) is **never shown** on
   Notes — there is no sense of "how close to passing."
3. The module chip shows the **computed** `averageFinal` (`Calculator`) while the element row shows
   the **scraped** `Moy` cell — two different numbers, neither labeled official vs estimated.
4. Résultats official modules show only `code · au` + `moy dec` (`ui/Screens.kt:214`) — e.g. "API43"
   instead of "Eléments de machine".
5. Semester average is plain text; rank is a raw `"Rang 165/419"` string with no emphasis.
6. No dark mode (`ui/theme/Theme.kt` is light-only); tabs use emoji icons (`MainActivity.kt:64`).
7. Display-mapping (`elementRowsFor`, `ui/Screens.kt:64`; `marksFromSnapshot`,
   `ui/AppViewModel.kt:157`) lives inside UI/VM code and is untested.

## 4. Architecture — a tested presentation layer

Introduce package `ma.ensam.schoolapp.ui.present` containing **pure functions** (no Android, no
Compose, no I/O) that turn raw inputs into display-ready models:

```
(Snapshot, Extras, SemesterResult from Calculator, List<ModuleDef> from Presets)
        -> NotesView, ResultsView
```

- Move `elementRowsFor` and `marksFromSnapshot` here as tested functions.
- `AppViewModel` calls these mappers and exposes the resulting view models in `AppUiState`; the
  `@Composable` screens become thin renderers with no business logic.

### Display models (new)

```kotlin
enum class GradeSource { OFFICIAL, ESTIMATED, MISSING }

data class Cell(val label: String, val value: Double?, val display: String, val source: GradeSource)

data class ElementView(
    val code: String, val title: String,
    val cc: Cell?, val ex: Cell?, val tp: Cell?, // null when the element doesn't use that column
    val moy: Cell, val decision: String,
    val fullyGraded: Boolean,
)

data class ModuleView(
    val code: String, val title: String,
    val average: Double?,             // computed (Calculator) or official, see rule below
    val seuil: Double,                // 11.0
    val progressToSeuil: Float,       // (average / seuil).coerceIn(0,1); 0 when not graded
    val status: ModuleStatus,         // VORD / RAT / NV
    val source: GradeSource,          // OFFICIAL vs ESTIMATED vs MISSING
    val elements: List<ElementView>,
)

data class NotesView(
    val semester: String,
    val semesterAverage: Double?,
    val validatedCount: Int, val totalCount: Int,
    val anyEstimated: Boolean,
    val modules: List<ModuleView>,
)
```

### The official-vs-estimated rule

A module/element is **OFFICIAL** only when the portal published it:
- the official module result exists in `Extras.modules` for that module code, **or**
- every element of the module has a non-blank scraped `Moy` **and** `Dec` cell.

When OFFICIAL via `Extras.modules`, the **displayed number is the portal's published `moy`**; when
OFFICIAL via fully-scraped elements, it is the scraped module `Moy`; only when ESTIMATED is the
`Calculator` value shown. Otherwise the average is a **local `Calculator` estimate** and is tagged `ESTIMATED` → shown with an
"estimé" badge. `MISSING` = no marks at all → "pas encore noté". An estimate is **never** styled the
same as an official grade. This directly prevents presenting computed numbers as if the portal
returned them.

## 5. Notes screen redesign

- **Summary header card**: large `semesterAverage / 20`, `"Validés X/7"`, an "estimé" badge when
  `anyEstimated`. "Aucune note" empty state when no snapshot.
- **Per-module card** (`ModuleCard` rewrite):
  - Title row: `code` + `title` + status-colored average chip
    (green VORD / amber RAT / red NV / gray MISSING), with a small "estimé" tag when
    `source == ESTIMATED`.
  - **Validation progress bar** toward `seuil`: filled proportion = `progressToSeuil`, colored by
    status, labeled `"79% du seuil 11"` or `"validé"`.
  - **Elements**: one block per element showing only the columns it uses (CC/EX/TP non-null),
    missing cells greyed as `—`, each numeric grade colored vs `seuil` where meaningful, plus
    `Moy` + `Dec`. Per-element "pas encore noté" when `!fullyGraded` and no marks.

## 6. Résultats screen redesign

- **Semestres**: hero card per `SemesterResultRow` — large `moy`, decision chip (`decisionColors`),
  rank rendered as `"165ᵉ / 419"` with a thin position bar (parse `rank` of form `a/b`), AU + niveau
  header. Keep existing empty state.
- **Modules officiels**: map `OfficialModule.code` → module title via a `Presets` lookup across
  S3+S4 (fallback to the raw code for unknown semesters), group cards by `au`, emphasize `moy`, color
  by `dec`. Known limitation: modules from semesters not in `Presets` (e.g. S1/S2) show the code only.

## 7. Grade tools

### What-if simulator
- Entry point: a "Simuler" affordance on each Notes module card → `ModalBottomSheet`.
- For each element, fields/sliders for the pending marks it uses (CC/EX/TP), pre-filled with current
  scraped values where present.
- On change, build an overridden `marks: Map<String, Double>` and call
  `Calculator.computeSemester(...)` to live-recompute: element grade, module average + status, and
  the **delta to the semester average**. Reset button. Purely local, no network.
- Tested via `Calculator` with override maps.

### Validation tracker
- A summary (on Statut or the Notes header): `"X/7 validés · semestre Y.YY/20"` and, when some
  modules are non-validés, the **minimum average needed on the remaining modules** to reach the
  semester seuil — derived from `SemesterResult` + module coefs. Tested.

## 8. Theming, chrome & icons

- **Dark mode**: provide light **and** dark schemes; use `dynamicLightColorScheme` /
  `dynamicDarkColorScheme` on API 31+, static `lightColorScheme()` / `darkColorScheme()` below, keyed
  on `isSystemInDarkTheme()`. Replace the light-only `Theme.kt`.
- **Status palette**: the hardcoded colors in `Cards.kt` (Green/Amber/Red/Gray + Bg) get dark-mode
  variants resolved from the theme so chips stay legible in dark.
- **Tabs**: replace emoji (`MainActivity.kt:64`) with Material icons (e.g. Dashboard, Grade/Star,
  EventBusy, WorkspacePremium/School, History, Settings). Prefer the core icon set; add
  `material-icons-extended` only if a chosen icon is missing (R8 strips unused).
- Consistent empty/loading/error components shared across screens.

## 9. Analytics + widget

### Average time-series (new persistence)
Room currently keeps only the latest snapshot per semester (`Entities.kt` PK = semester, REPLACE) and
text-only history — so **trends cannot be reconstructed from the past**. Add capture going forward:

- New entity `AverageSampleEntity(id, timestamp, semester, moduleCode: String?, value: Double)`
  (`moduleCode == null` ⇒ semester-level average).
- New DAO reads: `samplesForSemester(semester)`, `samplesForModule(semester, code)`.
- **`MIGRATION_1_2`** bumps `AppDatabase` to version 2 and `CREATE TABLE average_samples(...)` (no
  destructive fallback — preserves existing history).
- Capture hook in `WatcherRepository.runCheck()`: when `gradesChanged`, compute semester + per-module
  averages via `Calculator` and insert sample rows. Requires moving `marksFromSnapshot` into a shared
  domain helper (`domain` or `ui/present`) so the repository can use it too. Seed one sample point
  from current data on first run after upgrade so charts aren't empty.

### Trend sparklines & heatmap
- **Sparklines** drawn with Compose `Canvas` (no chart dependency): semester average over time on the
  Notes header; per-module mini-sparkline on module cards. Show "données insuffisantes" until ≥2
  points.
- **Heatmap**: grid of modules colored by `averageFinal` vs `seuil` (current data, no history),
  surfaced on Statut or Résultats.

### Home-screen widget
- Glance app widget (`androidx.glance:glance-appwidget` — the **one new dependency**) showing semester
  average, `"Validés X/7"`, and next-check countdown; tap opens the app. Reads from `EncryptedPrefs`
  (heartbeat/interval) + latest snapshot.

## 10. Testing

New unit tests (existing 40 stay green):
- `present/NotesMapperTest` — official-vs-estimated resolution, progress, per-element cell resolution,
  missing/partial states.
- `present/ResultsMapperTest` — official-module title mapping + rank parsing.
- `WhatIfTest` — override-map recompute correctness and semester-delta.
- `ValidationTrackerTest` — "needed average on remaining" math.
- `AverageSampleTest` / migration test — sampling values + `MIGRATION_1_2` creates the table.

UI is verified manually on the Redmi per existing practice; logic is covered by the mappers' tests.

## 11. Phasing (each phase builds, tests green, optionally a release APK)

1. **Affichage core** — presentation layer + display models + Notes redesign + Résultats redesign +
   dark mode + Material icons + shared empty/loading states + mapper tests. *(The user's literal ask;
   a complete standalone visual upgrade.)*
2. **Grade tools** — what-if simulator + validation tracker + their tests.
3. **Analytics & widget** — `average_samples` table + `MIGRATION_1_2` + capture hook + sparklines +
   heatmap + Glance widget + tests.

## 12. Risks & limitations

- **Trends start sparse**: only accrue from this upgrade onward (seeded with one point). Communicated
  in-UI via the "données insuffisantes" state.
- **Official module titles** only resolve for S3/S4 (the `Presets` coverage); older semesters show
  codes.
- **Widget** adds a dependency and a small battery/update cost; kept read-only and update-driven
  (refreshed after checks, not continuously polling).
- **Dark-mode contrast**: the hardcoded status palette needs dark variants to stay legible.
- Room migration must be correct (version 2 + `MIGRATION_1_2`) to avoid wiping the user's history.

## 13. File-level change map

- **New:** `ui/present/Models.kt`, `ui/present/NotesMapper.kt`, `ui/present/ResultsMapper.kt`,
  `ui/components/Sparkline.kt`, `ui/components/Heatmap.kt`, `ui/WhatIfSheet.kt`,
  `data/db/AverageSampleEntity.kt`, `widget/AverageWidget.kt`, mapper/what-if/migration tests.
- **Modified:** `ui/Screens.kt` (thin renderers), `ui/components/Cards.kt` (new `ModuleCard` +
  dark-aware palette), `ui/AppViewModel.kt` (expose view models, drop inline mapping),
  `ui/theme/Theme.kt` (light+dark), `MainActivity.kt` (Material icons),
  `data/db/AppDatabase.kt` (+entity, version 2, migration), `data/db/WatcherDao.kt` (+sample reads),
  `data/repository/WatcherRepository.kt` (sample-capture hook),
  `domain/` (shared `marksFromSnapshot`), `app/build.gradle.kts` + version catalog (Glance, maybe
  material-icons-extended).
- **Untouched:** scraping/parsing, auth, watcher service, WorkManager, diff/extras-diff, Telegram,
  onboarding, MIUI utils.
