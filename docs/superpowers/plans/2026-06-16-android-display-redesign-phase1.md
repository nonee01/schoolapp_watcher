# SchoolApp Android — Phase 1 (Affichage Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rough, untested grade/results display with a tested presentation layer plus redesigned Notes & Résultats screens, dark mode, and Material icons — without touching scraping, the watcher, or change-detection.

**Architecture:** Introduce `ma.ensam.schoolapp.ui.present` — pure functions that map `(Snapshot, Extras, Calculator output, Presets)` into display-ready view models (`NotesView`, `ResultsView`). The `@Composable` screens become thin renderers; the `AppViewModel` computes the view models and exposes them. An "official-vs-estimated" rule guarantees computed numbers are never shown as portal-official.

**Tech Stack:** Kotlin 2.0.21, Jetpack Compose (BOM 2024.12.01, Material3), Hilt, Room 2.6.1, JUnit4. Build with `ANDROID_HOME=/opt/android-sdk ./gradlew …` from the `android/` directory.

**Spec:** `docs/superpowers/specs/2026-06-16-schoolapp-android-display-redesign-design.md`

**Conventions for every task:**
- All commands run from `/home/notadil/Projects/schoolapp_watcher/android`.
- Unit test (one class): `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.<ClassName>"`
- Full unit suite: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest`
- Compile/build: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
- In Kotlin, a "failing test" first fails by **not compiling** (unresolved reference) — that is the expected red state.

---

## File Structure

**New files**
- `app/src/main/java/ma/ensam/schoolapp/ui/present/Models.kt` — display view models (data classes/enums only)
- `app/src/main/java/ma/ensam/schoolapp/domain/SnapshotMarks.kt` — shared marks extractor (moved out of the ViewModel)
- `app/src/main/java/ma/ensam/schoolapp/ui/present/NotesMapper.kt` — Snapshot+Extras → `NotesView`
- `app/src/main/java/ma/ensam/schoolapp/ui/present/ResultsMapper.kt` — Extras → `ResultsView`
- `app/src/main/java/ma/ensam/schoolapp/ui/components/States.kt` — shared empty/loading/error composables
- `app/src/test/java/ma/ensam/schoolapp/PresetsTitleTest.kt`
- `app/src/test/java/ma/ensam/schoolapp/SnapshotMarksTest.kt`
- `app/src/test/java/ma/ensam/schoolapp/NotesMapperTest.kt`
- `app/src/test/java/ma/ensam/schoolapp/ResultsMapperTest.kt`

**Modified files**
- `app/src/main/java/ma/ensam/schoolapp/domain/Presets.kt` — add `moduleTitle()`
- `app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt` — use `SnapshotMarks`, expose `notesView`/`resultsView`
- `app/src/main/java/ma/ensam/schoolapp/ui/theme/Theme.kt` — light **and** dark schemes
- `app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt` — dark-aware palette + new `ModuleCard`
- `app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt` — Notes & Résultats render view models
- `app/src/main/java/ma/ensam/schoolapp/MainActivity.kt` — Material icons for tabs

**Untouched:** all `data/remote/*`, `service/*`, `domain/Diff*.kt`, `domain/Calculator.kt`, `data/repository/*`, `data/db/*`.

---

## Task 1: `Presets.moduleTitle()` helper

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/domain/Presets.kt`
- Test: `app/src/test/java/ma/ensam/schoolapp/PresetsTitleTest.kt`

- [ ] **Step 1: Write the failing test**

Create `app/src/test/java/ma/ensam/schoolapp/PresetsTitleTest.kt`:

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PresetsTitleTest {
    @Test fun resolves_known_titles_case_insensitive() {
        assertEquals("Eléments de machine", Presets.moduleTitle("API43"))
        assertEquals("Analyse 3", Presets.moduleTitle("api31"))
    }

    @Test fun unknown_code_returns_null() {
        assertNull(Presets.moduleTitle("ZZZ99"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.PresetsTitleTest"`
Expected: FAIL — compilation error `unresolved reference: moduleTitle`.

- [ ] **Step 3: Implement the helper**

In `Presets.kt`, add this function inside `object Presets` (e.g. just below `modulesForSemester`):

```kotlin
    /** Human title for a module code across known presets, or null if unknown. */
    fun moduleTitle(code: String): String? {
        val c = code.trim().uppercase()
        return (PRESET_2A_S3 + PRESET_2A_S4).firstOrNull { it.code.uppercase() == c }?.title
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.PresetsTitleTest"`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/domain/Presets.kt app/src/test/java/ma/ensam/schoolapp/PresetsTitleTest.kt
git commit -m "feat(android): Presets.moduleTitle() code→title lookup"
```

---

## Task 2: Presentation view models

**Files:**
- Create: `app/src/main/java/ma/ensam/schoolapp/ui/present/Models.kt`

These are pure declarations (no behavior), so they are verified by compiling — no separate unit test.

- [ ] **Step 1: Create the models file**

```kotlin
package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.ModuleStatus

/** Where a displayed number comes from. ESTIMATED must never be styled as OFFICIAL. */
enum class GradeSource { OFFICIAL, ESTIMATED, MISSING }

/** One displayable grade cell (CC/EX/TP/Moy). value is null when not numeric. */
data class Cell(
    val label: String,
    val value: Double?,
    val display: String,
    val source: GradeSource,
)

data class ElementView(
    val code: String,
    val title: String,
    val cc: Cell?,   // null when the element does not use this column
    val ex: Cell?,
    val tp: Cell?,
    val moy: Cell,
    val decision: String,
    val fullyGraded: Boolean,
)

data class ModuleView(
    val code: String,
    val title: String,
    val average: Double?,
    val seuil: Double,
    val progressToSeuil: Float,
    val status: ModuleStatus,
    val source: GradeSource,
    val elements: List<ElementView>,
)

data class NotesView(
    val semester: String,
    val semesterAverage: Double?,
    val validatedCount: Int,
    val totalCount: Int,
    val anyEstimated: Boolean,
    val modules: List<ModuleView>,
)

data class SemesterRowView(
    val niveau: String,
    val sem: String,
    val au: String,
    val moy: String,
    val dec: String,
    val rankText: String,
    val rankPosition: Int?,
    val rankTotal: Int?,
)

data class OfficialModuleView(
    val code: String,
    val title: String,
    val au: String,
    val moy: String,
    val dec: String,
)

data class ResultsView(
    val semesters: List<SemesterRowView>,
    val officialModules: List<OfficialModuleView>,
)
```

- [ ] **Step 2: Verify it compiles**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew compileDebugKotlin`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/present/Models.kt
git commit -m "feat(android): presentation view models (NotesView/ResultsView)"
```

---

## Task 3: Shared `SnapshotMarks` helper (moved out of the ViewModel)

**Files:**
- Create: `app/src/main/java/ma/ensam/schoolapp/domain/SnapshotMarks.kt`
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt:157-177`
- Test: `app/src/test/java/ma/ensam/schoolapp/SnapshotMarksTest.kt`

- [ ] **Step 1: Write the failing test**

Create `app/src/test/java/ma/ensam/schoolapp/SnapshotMarksTest.kt`:

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.SnapshotMarks
import ma.ensam.schoolapp.domain.model.Snapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SnapshotMarksTest {
    @Test fun maps_cc_ex_tp_rat_and_aliases_ex_to_ecrit() {
        val snap = Snapshot(
            headers = listOf("CodeElem", "CC", "EX", "TP", "RAT"),
            rows = listOf(
                listOf("API411", "14", "8", "--", "--"),
                listOf("API421", "12.5", "--", "--", "16"),
            ),
            fingerprint = "fp",
        )
        val m = SnapshotMarks.fromSnapshot(snap)
        assertEquals(14.0, m["API411.cc"]!!, 0.0001)
        assertEquals(8.0, m["API411.ex"]!!, 0.0001)
        assertEquals(8.0, m["API411.ecrit"]!!, 0.0001)
        assertEquals(16.0, m["API421.rat"]!!, 0.0001)
        assertNull(m["API421.ex"])   // "--" is not numeric
    }

    @Test fun no_code_column_yields_empty() {
        val snap = Snapshot(listOf("CC", "EX"), listOf(listOf("10", "12")), "fp")
        assertEquals(emptyMap<String, Double>(), SnapshotMarks.fromSnapshot(snap))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SnapshotMarksTest"`
Expected: FAIL — `unresolved reference: SnapshotMarks`.

- [ ] **Step 3: Create the helper**

Create `app/src/main/java/ma/ensam/schoolapp/domain/SnapshotMarks.kt`:

```kotlin
package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Snapshot

/** Extracts a marks map ("CODE.cc"/".ex"/".ecrit"/".tp"/".rat" -> Double) from a scraped snapshot. */
object SnapshotMarks {
    fun fromSnapshot(snap: Snapshot): Map<String, Double> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val marks = HashMap<String, Double>()
        fun get(row: List<String>, key: String): Double? {
            val i = idx[key] ?: return null
            if (i >= row.size) return null
            return Calculator.parseMarkString(row[i])
        }
        for (row in snap.rows) {
            if (codeIdx >= row.size) continue
            val code = row[codeIdx].trim()
            if (code.isEmpty()) continue
            get(row, "CC")?.let { marks["$code.cc"] = it }
            get(row, "EX")?.let { marks["$code.ecrit"] = it; marks["$code.ex"] = it }
            get(row, "TP")?.let { marks["$code.tp"] = it }
            get(row, "RAT")?.let { marks["$code.rat"] = it }
        }
        return marks
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SnapshotMarksTest"`
Expected: PASS (2 tests).

- [ ] **Step 5: Refactor the ViewModel to use it**

In `app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt`, delete the private `marksFromSnapshot` function (currently lines ~157-177) and change `computeCalc` to call the shared helper:

```kotlin
    private fun computeCalc(snap: Snapshot, semester: String): SemesterResult =
        Calculator.computeSemester(Presets.modulesForSemester(semester), SnapshotMarks.fromSnapshot(snap))
```

Add the import near the other domain imports:

```kotlin
import ma.ensam.schoolapp.domain.SnapshotMarks
```

- [ ] **Step 6: Verify the full suite still passes**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest`
Expected: BUILD SUCCESSFUL, all existing tests + the 2 new ones pass.

- [ ] **Step 7: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/domain/SnapshotMarks.kt \
        app/src/test/java/ma/ensam/schoolapp/SnapshotMarksTest.kt \
        app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt
git commit -m "refactor(android): extract SnapshotMarks from ViewModel (tested)"
```

---

## Task 4: `NotesMapper` (official-vs-estimated rule)

**Files:**
- Create: `app/src/main/java/ma/ensam/schoolapp/ui/present/NotesMapper.kt`
- Test: `app/src/test/java/ma/ensam/schoolapp/NotesMapperTest.kt`

- [ ] **Step 1: Write the failing test**

Create `app/src/test/java/ma/ensam/schoolapp/NotesMapperTest.kt`. Fixtures use module **API42** (single element API421: coefCc 0.3, coefEx 0.7, coefEelem 5, coefMod 5, seuil 11). With CC=10, EX=20 the element grade is `10*0.3 + 20*0.7 = 17.0`, so `averageFinal = 17.0`.

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.ModuleStatus
import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.Snapshot
import ma.ensam.schoolapp.ui.present.GradeSource
import ma.ensam.schoolapp.ui.present.NotesMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NotesMapperTest {

    private val api42 = listOf(Presets.PRESET_2A_S4.first { it.code == "API42" })
    private val headers = listOf("CodeElem", "CC", "EX", "TP", "Moy", "Dec", "RAT")
    private fun snap(vararg rows: List<String>) = Snapshot(headers, rows.toList(), "fp")

    @Test fun null_snapshot_is_all_missing() {
        val v = NotesMapper.toNotesView(null, Extras(), api42, "S4")
        assertEquals(GradeSource.MISSING, v.modules.single().source)
        assertNull(v.semesterAverage)
        assertEquals(0, v.validatedCount)
        assertEquals(1, v.totalCount)
    }

    @Test fun scraped_marks_without_official_is_estimated() {
        val v = NotesMapper.toNotesView(
            snap(listOf("API421", "10", "20", "--", "--", "", "--")),
            Extras(), api42, "S4",
        )
        val m = v.modules.single()
        assertEquals(GradeSource.ESTIMATED, m.source)
        assertEquals(17.0, m.average!!, 0.0001)
        assertEquals(ModuleStatus.VORD, m.status)
        assertEquals(1.0f, m.progressToSeuil, 0.0001f) // 17/11 clamped to 1.0
        assertTrue(v.anyEstimated)
        assertEquals(1, v.validatedCount)
        // The single element uses CC and EX but not TP (coefTp == 0) -> tp cell hidden.
        val el = m.elements.single()
        assertEquals(10.0, el.cc!!.value!!, 0.0001)
        assertNull(el.tp)
    }

    @Test fun official_module_overrides_with_portal_value() {
        val extras = Extras(
            modules = mapOf("API42|2024/2025" to OfficialModule("API42", "2024/2025", "9.90", "NV")),
        )
        val v = NotesMapper.toNotesView(
            snap(listOf("API421", "10", "20", "--", "--", "", "--")),
            extras, api42, "S4",
        )
        val m = v.modules.single()
        assertEquals(GradeSource.OFFICIAL, m.source)
        assertEquals(9.90, m.average!!, 0.0001)        // portal moy, not the computed 17.0
        assertEquals(ModuleStatus.NV, m.status)
        assertEquals(0.9f, m.progressToSeuil, 0.0001f) // 9.9/11
        assertEquals(false, v.anyEstimated)
        assertEquals(0, v.validatedCount)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.NotesMapperTest"`
Expected: FAIL — `unresolved reference: NotesMapper`.

- [ ] **Step 3: Implement the mapper**

Create `app/src/main/java/ma/ensam/schoolapp/ui/present/NotesMapper.kt`:

```kotlin
package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.ModuleStatus
import ma.ensam.schoolapp.domain.SnapshotMarks
import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.ModuleDef
import ma.ensam.schoolapp.domain.model.Snapshot

object NotesMapper {

    fun toNotesView(
        snapshot: Snapshot?,
        extras: Extras,
        modules: List<ModuleDef>,
        semester: String,
    ): NotesView {
        if (snapshot == null) {
            return NotesView(
                semester = semester,
                semesterAverage = null,
                validatedCount = 0,
                totalCount = modules.size,
                anyEstimated = false,
                modules = modules.map(::missingModule),
            )
        }

        val idx = snapshot.headers.withIndex().associate { (i, h) -> h to i }
        val codeIdx = idx["CodeElem"] ?: -1
        val byCode: Map<String, List<String>> =
            if (codeIdx >= 0)
                snapshot.rows.filter { it.size > codeIdx && it[codeIdx].isNotBlank() }
                    .associateBy { it[codeIdx].trim() }
            else emptyMap()

        val calc = Calculator.computeSemester(modules, SnapshotMarks.fromSnapshot(snapshot))
        val resultByCode = calc.modules.associateBy { it.code }

        val moduleViews = modules.map { mod ->
            val elements = mod.elements.map { el -> elementView(el, byCode[el.code], idx) }
            val official = extras.modules.values.firstOrNull { it.code == mod.code }
            val hasMarks = elements.any { e ->
                e.cc?.source == GradeSource.OFFICIAL || e.ex?.source == GradeSource.OFFICIAL ||
                    e.tp?.source == GradeSource.OFFICIAL || e.moy.source == GradeSource.OFFICIAL
            }
            val computed = resultByCode[mod.code]

            val source: GradeSource
            val average: Double?
            val status: ModuleStatus
            when {
                official != null -> {
                    source = GradeSource.OFFICIAL
                    average = Calculator.parseMarkString(official.moy)
                    status = statusFromDecision(official.dec)
                }
                hasMarks && computed != null -> {
                    source = GradeSource.ESTIMATED
                    average = computed.averageFinal
                    status = computed.status
                }
                else -> {
                    source = GradeSource.MISSING
                    average = null
                    status = ModuleStatus.NV
                }
            }
            val progress =
                if (average != null && mod.seuil > 0) (average / mod.seuil).toFloat().coerceIn(0f, 1f) else 0f

            ModuleView(
                code = mod.code, title = mod.title, average = average, seuil = mod.seuil,
                progressToSeuil = progress, status = status, source = source, elements = elements,
            )
        }

        val anyGraded = moduleViews.any { it.source != GradeSource.MISSING }
        return NotesView(
            semester = semester,
            semesterAverage = if (anyGraded) calc.semesterAverageFinal else null,
            validatedCount = moduleViews.count { it.source != GradeSource.MISSING && it.status != ModuleStatus.NV },
            totalCount = modules.size,
            anyEstimated = moduleViews.any { it.source == GradeSource.ESTIMATED },
            modules = moduleViews,
        )
    }

    private fun missingModule(mod: ModuleDef) = ModuleView(
        code = mod.code, title = mod.title, average = null, seuil = mod.seuil,
        progressToSeuil = 0f, status = ModuleStatus.NV, source = GradeSource.MISSING,
        elements = mod.elements.map {
            ElementView(it.code, it.title, null, null, null, Cell("Moy", null, "—", GradeSource.MISSING), "", false)
        },
    )

    private fun elementView(el: ElementDef, row: List<String>?, idx: Map<String, Int>): ElementView {
        fun raw(key: String): String =
            row?.let { r -> idx[key]?.let { if (it < r.size) r[it].trim() else "" } } ?: ""
        fun cell(label: String, key: String, used: Boolean): Cell? {
            if (!used) return null
            val r = raw(key)
            return Cell(label, Calculator.parseMarkString(r), r.ifBlank { "—" },
                if (r.isNotBlank()) GradeSource.OFFICIAL else GradeSource.MISSING)
        }
        val moyRaw = raw("Moy")
        return ElementView(
            code = el.code, title = el.title,
            cc = cell("CC", "CC", el.coefCc > 0),
            ex = cell("EX", "EX", el.coefEx > 0),
            tp = cell("TP", "TP", el.coefTp > 0),
            moy = Cell("Moy", Calculator.parseMarkString(moyRaw), moyRaw.ifBlank { "—" },
                if (moyRaw.isNotBlank()) GradeSource.OFFICIAL else GradeSource.MISSING),
            decision = raw("Dec"),
            fullyGraded = moyRaw.isNotBlank(),
        )
    }

    private fun statusFromDecision(dec: String): ModuleStatus {
        val d = dec.trim().uppercase()
        return when {
            d.startsWith("VRAT") || d.startsWith("RAT") -> ModuleStatus.RAT
            d.startsWith("V") -> ModuleStatus.VORD
            else -> ModuleStatus.NV
        }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.NotesMapperTest"`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/present/NotesMapper.kt \
        app/src/test/java/ma/ensam/schoolapp/NotesMapperTest.kt
git commit -m "feat(android): NotesMapper with official-vs-estimated rule (tested)"
```

---

## Task 5: `ResultsMapper` (titles + rank parsing)

**Files:**
- Create: `app/src/main/java/ma/ensam/schoolapp/ui/present/ResultsMapper.kt`
- Test: `app/src/test/java/ma/ensam/schoolapp/ResultsMapperTest.kt`

- [ ] **Step 1: Write the failing test**

Create `app/src/test/java/ma/ensam/schoolapp/ResultsMapperTest.kt`:

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import ma.ensam.schoolapp.ui.present.ResultsMapper
import org.junit.Assert.assertEquals
import org.junit.Test

class ResultsMapperTest {

    @Test fun maps_titles_and_rank() {
        val extras = Extras(
            modules = mapOf("API43|2024/2025" to OfficialModule("API43", "2024/2025", "13.40", "VRAC")),
            semesters = mapOf("2A|S3|2023/2024" to SemesterResultRow("2A", "S3", "2023/2024", "12.50", "V", "15/120", "--")),
        )
        val v = ResultsMapper.toResultsView(extras)
        assertEquals("Eléments de machine", v.officialModules.single().title)
        val s = v.semesters.single()
        assertEquals("15ᵉ / 120", s.rankText)
        assertEquals(15, s.rankPosition)
        assertEquals(120, s.rankTotal)
    }

    @Test fun unknown_module_falls_back_to_code() {
        val extras = Extras(modules = mapOf("XYZ99|2020/2021" to OfficialModule("XYZ99", "2020/2021", "10.0", "V")))
        assertEquals("XYZ99", ResultsMapper.toResultsView(extras).officialModules.single().title)
    }

    @Test fun rank_parsing_is_graceful() {
        assertEquals(15 to 120, ResultsMapper.parseRank("15/120"))
        assertEquals(null to null, ResultsMapper.parseRank(""))
        assertEquals(null to null, ResultsMapper.parseRank("N/A/x"))
    }

    @Test fun first_place_uses_premier_ordinal() {
        val extras = Extras(semesters = mapOf("2A|S4|2024/2025" to SemesterResultRow("2A", "S4", "2024/2025", "14.0", "V", "1/300", "--")))
        assertEquals("1ᵉʳ / 300", ResultsMapper.toResultsView(extras).semesters.single().rankText)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.ResultsMapperTest"`
Expected: FAIL — `unresolved reference: ResultsMapper`.

- [ ] **Step 3: Implement the mapper**

Create `app/src/main/java/ma/ensam/schoolapp/ui/present/ResultsMapper.kt`:

```kotlin
package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow

object ResultsMapper {

    fun toResultsView(extras: Extras): ResultsView {
        val semesters = extras.semesters.values
            .sortedWith(compareByDescending<SemesterResultRow> { it.au }.thenByDescending { it.sem })
            .map { s ->
                val (pos, total) = parseRank(s.rank)
                SemesterRowView(
                    niveau = s.niveau, sem = s.sem, au = s.au, moy = s.moy, dec = s.dec,
                    rankText = rankText(pos, total, s.rank), rankPosition = pos, rankTotal = total,
                )
            }
        val modules = extras.modules.values
            .sortedWith(compareByDescending<OfficialModule> { it.au }.thenBy { it.code })
            .map { m ->
                OfficialModuleView(
                    code = m.code, title = Presets.moduleTitle(m.code) ?: m.code,
                    au = m.au, moy = m.moy, dec = m.dec,
                )
            }
        return ResultsView(semesters, modules)
    }

    /** "15/120" -> (15, 120); blank/malformed -> (null, null). */
    fun parseRank(rank: String): Pair<Int?, Int?> {
        val parts = rank.trim().split("/")
        if (parts.size != 2) return null to null
        return parts[0].trim().toIntOrNull() to parts[1].trim().toIntOrNull()
    }

    private fun rankText(pos: Int?, total: Int?, raw: String): String {
        if (pos == null || total == null) return raw.ifBlank { "—" }
        val ord = if (pos == 1) "1ᵉʳ" else "${pos}ᵉ"
        return "$ord / $total"
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.ResultsMapperTest"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/present/ResultsMapper.kt \
        app/src/test/java/ma/ensam/schoolapp/ResultsMapperTest.kt
git commit -m "feat(android): ResultsMapper — official titles + rank parsing (tested)"
```

---

## Task 6: Expose view models from the ViewModel

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt`

- [ ] **Step 1: Add view-model fields to `AppUiState`**

Add these imports near the other `ui.present` / domain imports:

```kotlin
import ma.ensam.schoolapp.ui.present.NotesMapper
import ma.ensam.schoolapp.ui.present.NotesView
import ma.ensam.schoolapp.ui.present.ResultsMapper
import ma.ensam.schoolapp.ui.present.ResultsView
```

Add two fields to `data class AppUiState` (after `extras`):

```kotlin
    val notesView: NotesView? = null,
    val resultsView: ResultsView = ResultsView(emptyList(), emptyList()),
```

- [ ] **Step 2: Add a builder helper and use it in `loadPersisted` and `checkNow`**

Add this private helper to the `AppViewModel` class:

```kotlin
    private fun buildNotes(snap: Snapshot?, extras: Extras, sem: String): NotesView {
        val modules = runCatching { Presets.modulesForSemester(sem) }.getOrDefault(emptyList())
        return NotesMapper.toNotesView(snap, extras, modules, sem)
    }
```

In `loadPersisted()`, extend the `copy(...)` to also set the views:

```kotlin
        _state.value = _state.value.copy(
            snapshot = snap,
            extras = extras,
            calc = snap?.let { computeCalc(it, sem) },
            notesView = buildNotes(snap, extras, sem),
            resultsView = ResultsMapper.toResultsView(extras),
            lastCheckEpoch = prefs.lastHeartbeat,
            nextCheckEpoch = if (prefs.lastHeartbeat > 0) prefs.lastHeartbeat + _state.value.pollIntervalSeconds * 1000L else 0L,
        )
```

In `checkNow()`'s success `copy(...)` (the block after a successful `runCheck`, which already has `snap`, `extras`, and `sem` in scope), add these two lines:

```kotlin
                    notesView = buildNotes(snap, extras, sem),
                    resultsView = ResultsMapper.toResultsView(extras),
```

- [ ] **Step 3: Verify build + full suite**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest`
Expected: BUILD SUCCESSFUL, all tests pass (the screens still read the old fields, so nothing breaks yet).

- [ ] **Step 4: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt
git commit -m "feat(android): ViewModel computes & exposes NotesView/ResultsView"
```

---

## Task 7: Dark + light theme

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/theme/Theme.kt`

UI change — verified by build + manual toggle of system dark mode.

- [ ] **Step 1: Replace `Theme.kt`**

```kotlin
package ma.ensam.schoolapp.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

@Composable
fun SchoolAppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val ctx = LocalContext.current
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        darkTheme -> darkColorScheme()
        else -> lightColorScheme()
    }
    MaterialTheme(colorScheme = colors, content = content)
}
```

- [ ] **Step 2: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/theme/Theme.kt
git commit -m "feat(android): dark + light Material You theme"
```

---

## Task 8: Dark-aware status palette

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt:20-43`

Make `statusColors`/`decisionColors` pick legible variants in dark mode. They become `@Composable` (all call sites are already in composable scope).

- [ ] **Step 1: Replace the color block and the two color functions**

Replace lines 20-43 of `Cards.kt` (the `val Green … decisionColors(...)` block) with:

```kotlin
// Light variants
val Green = Color(0xFF166534); val GreenBg = Color(0xFFDCFCE7)
val Amber = Color(0xFF92400E); val AmberBg = Color(0xFFFEF3C7)
val Red = Color(0xFF991B1B);   val RedBg = Color(0xFFFEE2E2)
val Gray = Color(0xFF374151);  val GrayBg = Color(0xFFF3F4F6)
// Dark variants (lighter foreground, deep background)
val GreenD = Color(0xFF86EFAC); val GreenBgD = Color(0xFF14532D)
val AmberD = Color(0xFFFCD34D); val AmberBgD = Color(0xFF78350F)
val RedD = Color(0xFFFCA5A5);   val RedBgD = Color(0xFF7F1D1D)
val GrayD = Color(0xFFD1D5DB);  val GrayBgD = Color(0xFF374151)

@Composable
fun statusColors(status: ma.ensam.schoolapp.domain.ModuleStatus): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    return when (status) {
        ma.ensam.schoolapp.domain.ModuleStatus.VORD -> if (dark) GreenD to GreenBgD else Green to GreenBg
        ma.ensam.schoolapp.domain.ModuleStatus.RAT -> if (dark) AmberD to AmberBgD else Amber to AmberBg
        ma.ensam.schoolapp.domain.ModuleStatus.NV -> if (dark) RedD to RedBgD else Red to RedBg
    }
}

@Composable
fun decisionColors(dec: String): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    val d = dec.trim().uppercase()
    return when {
        d.startsWith("V") -> if (dark) GreenD to GreenBgD else Green to GreenBg
        d == "NV" -> if (dark) RedD to RedBgD else Red to RedBg
        else -> if (dark) GrayD to GrayBgD else Gray to GrayBg
    }
}
```

Add these imports to `Cards.kt` if not present:

```kotlin
import androidx.compose.foundation.isSystemInDarkTheme
```

(`androidx.compose.runtime.Composable` and `androidx.compose.ui.graphics.Color` are already imported.)

- [ ] **Step 2: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL. (The old `ModuleCard` in this file still compiles; it is replaced in Task 10.)

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt
git commit -m "feat(android): dark-aware status/decision palette"
```

---

## Task 9: Shared empty/loading/error components

**Files:**
- Create: `app/src/main/java/ma/ensam/schoolapp/ui/components/States.kt`

- [ ] **Step 1: Create the components**

```kotlin
package ma.ensam.schoolapp.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun EmptyState(message: String, emoji: String = "📭") {
    Column(
        Modifier.fillMaxWidth().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(emoji, style = MaterialTheme.typography.headlineMedium)
        Text(message, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
    }
}
```

- [ ] **Step 2: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/components/States.kt
git commit -m "feat(android): shared EmptyState component"
```

---

## Task 10: New `ModuleCard` + Notes screen

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt` (replace `ElementRow` + `ModuleCard`)
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt` (`GradesScreen`, remove `elementRowsFor`)

- [ ] **Step 1: Replace `ElementRow` data class and `ModuleCard` in `Cards.kt`**

Delete the `data class ElementRow(...)` (lines ~57-66) and the entire `@Composable fun ModuleCard(...)` (lines ~68-101), and add:

```kotlin
@Composable
fun ModuleCard(module: ma.ensam.schoolapp.ui.present.ModuleView) {
    val (fg, bg) = statusColors(module.status)
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(module.code, style = MaterialTheme.typography.labelSmall)
                    Text(module.title, style = MaterialTheme.typography.titleMedium)
                }
                Column(horizontalAlignment = Alignment.End) {
                    val label = if (module.average != null) "%.2f".format(module.average) else "—"
                    StatusChip(label, fg, bg)
                    if (module.source == ma.ensam.schoolapp.ui.present.GradeSource.ESTIMATED) {
                        Text("estimé", style = MaterialTheme.typography.labelSmall, color = Amber)
                    }
                }
            }
            ValidationBar(module, fg)
            module.elements.forEach { ElementBlock(it, module.seuil) }
        }
    }
}

@Composable
private fun ValidationBar(m: ma.ensam.schoolapp.ui.present.ModuleView, fg: Color) {
    if (m.source == ma.ensam.schoolapp.ui.present.GradeSource.MISSING) {
        Text("pas encore noté", style = MaterialTheme.typography.bodySmall); return
    }
    LinearProgressIndicator(
        progress = { m.progressToSeuil },
        color = fg,
        modifier = Modifier.fillMaxWidth(),
    )
    val label = if (m.status != ma.ensam.schoolapp.domain.ModuleStatus.NV) "validé"
        else "${(m.progressToSeuil * 100).toInt()}% du seuil ${m.seuil.toInt()}"
    Text(label, style = MaterialTheme.typography.labelSmall)
}

@Composable
private fun ElementBlock(e: ma.ensam.schoolapp.ui.present.ElementView, seuil: Double) {
    Column {
        Text("${e.code} — ${e.title}", style = MaterialTheme.typography.bodySmall)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            e.cc?.let { CellText(it, seuil) }
            e.ex?.let { CellText(it, seuil) }
            e.tp?.let { CellText(it, seuil) }
            if (e.moy.source != ma.ensam.schoolapp.ui.present.GradeSource.MISSING) CellText(e.moy, seuil)
        }
    }
}

@Composable
private fun CellText(c: ma.ensam.schoolapp.ui.present.Cell, seuil: Double) {
    val color = when {
        c.value == null -> MaterialTheme.colorScheme.onSurfaceVariant
        c.value >= seuil -> if (isSystemInDarkTheme()) GreenD else Green
        else -> if (isSystemInDarkTheme()) RedD else Red
    }
    Text("${c.label} ${c.display}", style = MaterialTheme.typography.bodySmall, color = color)
}
```

Add the needed imports to `Cards.kt`:

```kotlin
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.LinearProgressIndicator
```

(`Arrangement`, `Column`, `padding`, `Card`, `MaterialTheme`, `Text`, `Alignment`, `Modifier`, `Color`, `dp`, `Composable` are already imported in this file.)

- [ ] **Step 2: Rewrite `GradesScreen` in `Screens.kt`**

Delete the private `elementRowsFor(...)` function (lines ~63-82) and replace `GradesScreen` (lines ~120-150) with:

```kotlin
@Composable
fun GradesScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val notes = state.notesView
    if (notes == null || notes.modules.all { it.source == ma.ensam.schoolapp.ui.present.GradeSource.MISSING }) {
        ma.ensam.schoolapp.ui.components.EmptyState("Aucune note — touchez « Check Now » sur le tableau de bord.", "📚")
        return
    }
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "Semestre ${notes.semester}",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            notes.semesterAverage?.let { "%.2f / 20".format(it) } ?: "— / 20",
                            style = MaterialTheme.typography.titleLarge,
                        )
                    }
                    Text("Validés ${notes.validatedCount}/${notes.totalCount}" + if (notes.anyEstimated) " · estimé" else "")
                }
            }
        }
        items(notes.modules) { ModuleCard(it) }
    }
}
```

Remove the now-unused imports in `Screens.kt`: `ElementRow`, `ModuleStatus` (if only used by the old code), `Snapshot`, `ModuleDef`, `Presets`, and the `LinearProgressIndicator` import only if `DashboardScreen` no longer needs it — **keep** `LinearProgressIndicator` (DashboardScreen uses it). Let the compiler guide which imports are unused.

- [ ] **Step 3: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL. Fix any unused-import or missing-import errors the compiler reports.

- [ ] **Step 4: Manual smoke (optional but recommended)**

Install and open: `ANDROID_HOME=/opt/android-sdk ./gradlew installDebug` then open the app → Notes tab. Verify: per-module average chip, progress bar, "estimé" tag on computed modules, CC/EX shown without TP clutter, dark mode legible.

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt \
        app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt
git commit -m "feat(android): redesigned Notes — progress bars, color cells, estimé badge"
```

---

## Task 11: Résultats screen

**Files:**
- Modify: `app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt` (`ResultsScreen`)

- [ ] **Step 1: Replace `ResultsScreen` (lines ~187-222)**

```kotlin
@Composable
fun ResultsScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val results = state.resultsView
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Text("🎓 Semestres", style = MaterialTheme.typography.titleMedium) }
        items(results.semesters) { s ->
            val (fg, bg) = decisionColors(s.dec)
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column {
                            Text("${s.niveau} ${s.sem}", style = MaterialTheme.typography.titleSmall)
                            Text(s.au, style = MaterialTheme.typography.labelSmall)
                        }
                        Text(s.moy, style = MaterialTheme.typography.headlineSmall)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("Rang ${s.rankText}", style = MaterialTheme.typography.bodyMedium)
                        StatusChip(s.dec.ifBlank { "--" }, fg, bg)
                    }
                    if (s.rankPosition != null && s.rankTotal != null && s.rankTotal > 0) {
                        LinearProgressIndicator(
                            progress = { 1f - (s.rankPosition - 1).toFloat() / s.rankTotal },
                            color = fg,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
        if (results.semesters.isEmpty()) item { Text("Aucun résultat de semestre publié.") }

        item { Text("📋 Modules officiels", style = MaterialTheme.typography.titleMedium) }
        items(results.officialModules) { m ->
            val (fg, bg) = decisionColors(m.dec)
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(m.title, style = MaterialTheme.typography.titleSmall)
                            Text("${m.code} · ${m.au}", style = MaterialTheme.typography.labelSmall)
                        }
                        StatusChip("${m.moy}  ${m.dec}", fg, bg)
                    }
                }
            }
        }
        if (results.officialModules.isEmpty()) item { Text("Aucun résultat officiel publié.") }
    }
}
```

`LinearProgressIndicator` is already imported in `Screens.kt`. Remove the now-unused `state.extras`-based `mods`/`sems` locals (they were in the old `ResultsScreen`).

- [ ] **Step 2: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt
git commit -m "feat(android): redesigned Résultats — module names, rank bar, hero average"
```

---

## Task 12: Material icons for tabs

**Files:**
- Modify: `app/build.gradle.kts` (dependencies block)
- Modify: `app/src/main/java/ma/ensam/schoolapp/MainActivity.kt:60-84`

Uses only the **core** Material icon set. `material-icons-core` may already be on the classpath transitively via Material3, but declare it explicitly so this task is deterministic (it's a small artifact, version-managed by the Compose BOM).

- [ ] **Step 1: Declare the icons-core dependency**

In `app/build.gradle.kts`, add to the `dependencies { … }` block, next to the other Compose lines (`implementation(libs.androidx.material3)`):

```kotlin
    implementation("androidx.compose.material:material-icons-core")
```

No version is needed — `platform(libs.androidx.compose.bom)` pins it. (If you prefer the version catalog, add `androidx-material-icons-core = { group = "androidx.compose.material", name = "material-icons-core" }` to `gradle/libs.versions.toml` and reference `libs.androidx.material.icons.core` instead.)

- [ ] **Step 2: Change `TabItem` to carry an `ImageVector` and update the tab list + rendering**

Replace `private data class TabItem(val label: String, val icon: String)` with:

```kotlin
private data class TabItem(val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)
```

Replace the `tabs` list inside `AppScaffold` with:

```kotlin
    val tabs = listOf(
        TabItem("Statut", androidx.compose.material.icons.Icons.Default.Home),
        TabItem("Notes", androidx.compose.material.icons.Icons.Default.Star),
        TabItem("Absences", androidx.compose.material.icons.Icons.Default.Warning),
        TabItem("Résultats", androidx.compose.material.icons.Icons.Default.CheckCircle),
        TabItem("Historique", androidx.compose.material.icons.Icons.Default.DateRange),
        TabItem("Réglages", androidx.compose.material.icons.Icons.Default.Settings),
    )
```

Replace the `icon = { Text(t.icon) }` line in `NavigationBarItem` with:

```kotlin
                        icon = { androidx.compose.material3.Icon(t.icon, contentDescription = t.label) },
```

- [ ] **Step 3: Build**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleDebug`
Expected: BUILD SUCCESSFUL. (If any icon is reported missing from the core set, substitute another core icon — e.g. `Icons.Default.Info`, `Icons.Default.List`, `Icons.Default.Notifications`, `Icons.Default.Refresh` — rather than adding `material-icons-extended`.)

- [ ] **Step 4: Commit**

```bash
git add app/build.gradle.kts app/src/main/java/ma/ensam/schoolapp/MainActivity.kt
git commit -m "feat(android): Material icons for bottom navigation"
```

---

## Task 13: Phase 1 verification gate

**Files:** none (verification + release build).

- [ ] **Step 1: Run the entire unit suite**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew testDebugUnitTest`
Expected: BUILD SUCCESSFUL. Confirm the original 40 tests plus the new ones (PresetsTitle 2, SnapshotMarks 2, NotesMapper 3, ResultsMapper 4) all pass.

- [ ] **Step 2: Build the release APK (R8) to confirm keep-rules still hold**

Run: `ANDROID_HOME=/opt/android-sdk ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a`
Expected: BUILD SUCCESSFUL; APK at `app/build/outputs/apk/release/app-release.apk`.

- [ ] **Step 3: Manual smoke on device (per existing practice)**

Install: `ANDROID_HOME=/opt/android-sdk ./gradlew installRelease` (or `adb install -r app/build/outputs/apk/release/app-release.apk`). Verify on the Redmi: Notes (progress bars, estimé badges, no TP clutter), Résultats (module names, rank bar), dark mode (toggle system theme), Material tab icons, empty states before first check.

- [ ] **Step 4: Tag the phase commit**

```bash
git commit --allow-empty -m "test(android): Phase 1 affichage core verified — full suite green, release APK builds"
```

---

## Self-review notes (already reconciled against the spec)

- **Spec §4 presentation layer** → Tasks 2-6. **§5 Notes** → Task 10. **§6 Résultats** → Task 11.
  **§8 theming/icons/states** → Tasks 7, 8, 9, 12. **§10 tests** (Notes/Results mappers) → Tasks 4, 5.
- **§7 grade tools**, **§9 analytics + widget** are **Phase 2 / Phase 3** — planned separately (below).
- Type names are consistent across tasks: `NotesView`, `ResultsView`, `ModuleView`, `ElementView`,
  `Cell`, `GradeSource`, `SnapshotMarks.fromSnapshot`, `Presets.moduleTitle`, `ResultsMapper.parseRank`.

## Phase 2 / Phase 3 (to be planned in detail after Phase 1 ships)

- **Phase 2 — Grade tools:** `WhatIf` recompute (override marks → `Calculator`), `ModalBottomSheet`
  simulator entry on each module card, validation tracker ("needed average on remaining"). New tests:
  `WhatIfTest`, `ValidationTrackerTest`.
- **Phase 3 — Analytics & widget:** `AverageSampleEntity` + `MIGRATION_1_2` (Room v2), capture hook in
  `WatcherRepository.runCheck`, Compose-`Canvas` sparklines + heatmap, Glance home-screen widget
  (`androidx.glance:glance-appwidget` — one new dependency). New tests: `AverageSampleTest`, migration test.
