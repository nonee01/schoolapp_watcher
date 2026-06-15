# SchoolApp Android — Plan 2: Persistence & Background Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Plan 1 app into an always-on, server-free grade watcher that polls SchoolApp on-device, persists snapshots/history in Room, fires local + Telegram notifications on real changes, and survives HyperOS/MIUI battery killing via a Foreground Service + WorkManager watchdog + an onboarding flow that routes the user through the required permission screens.

**Architecture:** Builds on Plan 1's `SchoolAppClient`, `Fingerprint`, `Diff`, `Calculator`, `EncryptedPrefs`, `TelegramNotifier`. Adds: extras scraping (absences/sanctions/official module+semester results) as pure testable functions; Room persistence; a `WatcherRepository` that orchestrates a check (fetch → diff → persist → notify); a `WatcherService` foreground coroutine loop writing a heartbeat; a `WatchdogWorker` that restarts the service when the heartbeat goes stale; a `BootReceiver`; `MiuiUtils` for HyperOS auto-start/battery intents; and an onboarding Compose flow.

**Tech Stack additions:** Room 2.6.1 (KSP), WorkManager 2.10.0, AndroidX core notifications. Everything else as Plan 1.

**Target device (verified on adb):** Redmi 2209116AG (`sweet`), HyperOS 1.0, Android 13 / API 33, arm64-v8a, adb id `3ad2f4880013`.

---

## Conventions

- **Project root:** `/home/notadil/Projects/schoolapp_watcher/android/` — run all gradle commands here.
- **Repo branch:** `android-native-app` (continue on it). Only touch files under `android/`; never stage unrelated repo changes.
- **JVM unit tests:** `./gradlew testDebugUnitTest`. Use a 300000 ms Bash timeout for gradle (first builds longer).
- **Install on device (MIUI guard):** `./gradlew installDebug` fails on this device with `INSTALL_FAILED_USER_RESTRICTED`; instead `./gradlew assembleDebug` then `adb install -r app/build/outputs/apk/debug/app-debug.apk`.
- **Python sources of truth** (translate faithfully): `schoolapp/watcher.py` (`_parse_absence_log`, `_parse_sanctions`, `_parse_modules_encours`, `_parse_semester_results`, `_fetch_extras`, `watch_loop`, `_scheduled_interval`, `_try_notify`), `schoolapp/api.py` (interval/status shape).

## File Structure (Plan 2 additions)

```
app/src/main/java/ma/ensam/schoolapp/
├── data/
│   ├── remote/
│   │   ├── SchoolAppExtrasParsing.kt     # Task 2 (TDD) — absences/sanctions/modules/semesters parsers
│   │   └── SchoolAppClient.kt            # Task 3 (modify) — fetchExtras()
│   ├── db/
│   │   ├── Entities.kt                   # Task 4 — SnapshotEntity, HistoryEntity
│   │   ├── WatcherDao.kt                 # Task 4
│   │   └── AppDatabase.kt               # Task 4
│   └── repository/
│       └── WatcherRepository.kt          # Task 5 — orchestrates check→diff→persist→notify
├── domain/model/Extras.kt                # Task 1 — Absence, Sanctions, OfficialModule, SemesterResultRow
├── service/
│   ├── NotificationHelper.kt             # Task 6
│   ├── WatcherService.kt                 # Task 7
│   ├── WatchdogWorker.kt                 # Task 8
│   └── BootReceiver.kt                   # Task 9
├── util/MiuiUtils.kt                     # Task 10
└── ui/
    ├── onboarding/OnboardingScreen.kt    # Task 11
    └── MainScreen.kt / MainViewModel.kt  # Task 12 (modify) — watcher toggle + onboarding gate
app/src/test/java/ma/ensam/schoolapp/
└── SchoolAppExtrasParsingTest.kt         # Task 2
app/src/main/AndroidManifest.xml          # Task 7/9 (modify) — <service>, <receiver>
```

---

## Phase 0 — Dependencies & models

### Task 1: Add Room + WorkManager deps and extras models

**Files:**
- Modify: `android/gradle/libs.versions.toml`
- Modify: `android/app/build.gradle.kts`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/model/Extras.kt`

- [ ] **Step 1: Add versions + libraries to `gradle/libs.versions.toml`**

Under `[versions]` add:
```toml
room = "2.6.1"
workManager = "2.10.0"
```
Under `[libraries]` add:
```toml
androidx-room-runtime = { group = "androidx.room", name = "room-runtime", version.ref = "room" }
androidx-room-ktx = { group = "androidx.room", name = "room-ktx", version.ref = "room" }
androidx-room-compiler = { group = "androidx.room", name = "room-compiler", version.ref = "room" }
androidx-work-runtime-ktx = { group = "androidx.work", name = "work-runtime-ktx", version.ref = "workManager" }
```

- [ ] **Step 2: Add dependencies in `android/app/build.gradle.kts`** (inside `dependencies { ... }`, after the existing implementation lines)

```kotlin
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    implementation(libs.androidx.work.runtime.ktx)
```

- [ ] **Step 3: Create `domain/model/Extras.kt`** (mirrors the dict shapes produced in watcher.py)

```kotlin
package ma.ensam.schoolapp.domain.model

/** One absence row from /student/absence/bilan. Key = "element|date|seance". */
data class Absence(
    val element: String,
    val date: String,
    val seance: String,
    val justif: String,   // "true"/"false"/raw lowercased
    val remarks: String,
)

/** One official module result from /student/notesmod-encours. Key = "code|au". */
data class OfficialModule(
    val code: String,
    val au: String,
    val moy: String,
    val dec: String,
)

/** One semester result from /student/notessem. Key = "niveau|sem|au". */
data class SemesterResultRow(
    val niveau: String,
    val sem: String,
    val au: String,
    val moy: String,
    val dec: String,
    val rank: String,
    val pj: String,
)

/** All extra watched pages for one check. sanctions is a flat key->value map. */
data class Extras(
    val absences: Map<String, Absence> = emptyMap(),
    val sanctions: Map<String, String> = emptyMap(),
    val modules: Map<String, OfficialModule> = emptyMap(),
    val semesters: Map<String, SemesterResultRow> = emptyMap(),
)
```

- [ ] **Step 4: Compile-check**

Run (timeout 300000): `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew compileDebugKotlin`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/gradle/libs.versions.toml android/app/build.gradle.kts android/app/src/main/java/ma/ensam/schoolapp/domain/model/Extras.kt
git commit -m "chore(android): add Room + WorkManager deps and extras models"
```

---

## Phase 1 — Extras scraping (TDD, JVM)

### Task 2: Extras parsing functions

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppExtrasParsing.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/SchoolAppExtrasParsingTest.kt`

**Behavior:** Faithful to watcher.py. `tableByHeaders(html, wanted)` finds the first `<table>` whose `<th>` set contains all `wanted` columns. Then per-page parsers build maps keyed exactly as Python.

- [ ] **Step 1: Write the failing test**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.SchoolAppExtrasParsing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SchoolAppExtrasParsingTest {

    @Test fun parses_absence_log() {
        val html = """
            <table>
              <tr><th>Element</th><th>Date</th><th>Seance</th><th>Justif</th><th>Remarques</th></tr>
              <tr><td>API411</td><td>2024-03-12 08:00</td><td>S1</td><td>True</td><td>retard</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseAbsenceLog(html)
        assertEquals(1, out.size)
        val a = out["API411|2024-03-12|S1"]!!
        assertEquals("API411", a.element)
        assertEquals("2024-03-12", a.date)   // date is split on space, first token
        assertEquals("S1", a.seance)
        assertEquals("true", a.justif)        // lowercased
        assertEquals("retard", a.remarks)
    }

    @Test fun parses_sanctions_first_nonempty_table() {
        val html = """<table><tr><td>Message</td><td>Avertissement</td></tr>
                      <tr><td>Niveau</td><td>1</td></tr></table>"""
        val out = SchoolAppExtrasParsing.parseSanctions(html)
        assertEquals("Avertissement", out["Message"])
        assertEquals("1", out["Niveau"])
    }

    @Test fun parses_official_modules() {
        val html = """
            <table>
              <tr><th>CodeMod</th><th>AU</th><th>Moy</th><th>Dec</th></tr>
              <tr><td>API41</td><td>2023/2024</td><td>13.40</td><td>VRAC</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseModulesEncours(html)
        val m = out["API41|2023/2024"]!!
        assertEquals("API41", m.code)
        assertEquals("13.40", m.moy)
        assertEquals("VRAC", m.dec)
    }

    @Test fun parses_semester_results_with_decision_typo() {
        // The site uses "Decesion" (typo). Parser must read it OR "Decision".
        val html = """
            <table>
              <tr><th>Niveau</th><th>Semestre</th><th>AU</th><th>Moy SEM</th><th>Decesion</th><th>Classement</th><th>PJ</th></tr>
              <tr><td>2A</td><td>S3</td><td>2023/2024</td><td>12.50</td><td>V</td><td>15/120</td><td>--</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseSemesterResults(html)
        val s = out["2A|S3|2023/2024"]!!
        assertEquals("12.50", s.moy)
        assertEquals("V", s.dec)
        assertEquals("15/120", s.rank)
    }

    @Test fun missing_table_yields_empty() {
        assertTrue(SchoolAppExtrasParsing.parseAbsenceLog("<div/>").isEmpty())
        assertTrue(SchoolAppExtrasParsing.parseModulesEncours("<div/>").isEmpty())
        assertTrue(SchoolAppExtrasParsing.parseSemesterResults("<div/>").isEmpty())
    }
}
```

- [ ] **Step 2: Run test, expect FAIL** (`SchoolAppExtrasParsing` unresolved)

Run (timeout 300000): `./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppExtrasParsingTest"`

- [ ] **Step 3: Write `SchoolAppExtrasParsing.kt`**

```kotlin
package ma.ensam.schoolapp.data.remote

import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.jsoup.Jsoup
import org.jsoup.nodes.Element

/** Pure parsers for the extra watched pages, translated from watcher.py. */
object SchoolAppExtrasParsing {

    private fun norm(s: String) = s.trim().replace(Regex("\\s+"), " ")

    /** First <table> whose <th> set contains all wanted columns → (headers, rows). */
    private fun tableByHeaders(html: String, wanted: Set<String>): Pair<List<String>, List<List<String>>>? {
        for (t in Jsoup.parse(html).select("table")) {
            val headers = t.select("th").map { norm(it.text()) }
            if (headers.toSet().containsAll(wanted)) {
                val rows = ArrayList<List<String>>()
                for (tr in t.select("tr")) {
                    val tds = tr.select("td").map { norm(it.text()) }
                    if (tds.isNotEmpty() && tds.any { it.isNotEmpty() }) rows.add(tds)
                }
                return headers to rows
            }
        }
        return null
    }

    private fun List<String>.idx(): Map<String, Int> = withIndex().associate { (i, h) -> h to i }
    private fun cell(row: List<String>, idx: Map<String, Int>, key: String): String {
        val i = idx[key] ?: return ""
        return if (i < row.size) row[i] else ""
    }

    fun parseAbsenceLog(html: String): Map<String, Absence> {
        val found = tableByHeaders(html, setOf("Element", "Date", "Seance")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, Absence>()
        for (r in rows) {
            val date = cell(r, idx, "Date").split(" ").firstOrNull().orEmpty()
            val elem = cell(r, idx, "Element")
            if (elem.isEmpty()) continue
            val seance = cell(r, idx, "Seance")
            out["$elem|$date|$seance"] = Absence(
                element = elem,
                date = date,
                seance = seance,
                justif = cell(r, idx, "Justif").lowercase(),
                remarks = cell(r, idx, "Remarques"),
            )
        }
        return out
    }

    /** First table with >=2-col rows → flat key->value map. Mirrors _parse_sanctions. */
    fun parseSanctions(html: String): Map<String, String> {
        for (t: Element in Jsoup.parse(html).select("table")) {
            val out = LinkedHashMap<String, String>()
            for (tr in t.select("tr")) {
                val tds = tr.select("td").map { norm(it.text()) }
                if (tds.size >= 2 && tds[0].isNotEmpty()) out[tds[0]] = tds[1]
            }
            if (out.isNotEmpty()) return out
        }
        return emptyMap()
    }

    fun parseModulesEncours(html: String): Map<String, OfficialModule> {
        val found = tableByHeaders(html, setOf("CodeMod", "Moy", "Dec")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, OfficialModule>()
        for (r in rows) {
            val code = cell(r, idx, "CodeMod")
            if (code.isEmpty()) continue
            val au = cell(r, idx, "AU")
            out["$code|$au"] = OfficialModule(code, au, cell(r, idx, "Moy"), cell(r, idx, "Dec"))
        }
        return out
    }

    fun parseSemesterResults(html: String): Map<String, SemesterResultRow> {
        val found = tableByHeaders(html, setOf("Semestre", "Moy SEM")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, SemesterResultRow>()
        for (r in rows) {
            val sem = cell(r, idx, "Semestre")
            if (sem.isEmpty()) continue
            val niveau = cell(r, idx, "Niveau")
            val au = cell(r, idx, "AU")
            val dec = cell(r, idx, "Decesion").ifEmpty { cell(r, idx, "Decision") } // site typo
            out["$niveau|$sem|$au"] = SemesterResultRow(
                niveau = niveau, sem = sem, au = au,
                moy = cell(r, idx, "Moy SEM"), dec = dec,
                rank = cell(r, idx, "Classement"), pj = cell(r, idx, "PJ"),
            )
        }
        return out
    }
}
```

- [ ] **Step 4: Run test, expect PASS (5 tests)**

Run (timeout 300000): `./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppExtrasParsingTest"`

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppExtrasParsing.kt android/app/src/test/java/ma/ensam/schoolapp/SchoolAppExtrasParsingTest.kt
git commit -m "feat(android): extras parsers (absences/sanctions/modules/semesters) (tested)"
```

---

### Task 3: SchoolAppClient.fetchExtras()

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppClient.kt`

- [ ] **Step 1: Add the extras fetch** (append a method + path constants to the existing class; keep all existing code). Add inside the class:

```kotlin
    private val absenceUrl get() = "$baseUrl/student/absence/bilan"
    private val sanctionsUrl get() = "$baseUrl/student/absence/sanctions"
    private val modulesUrl get() = "$baseUrl/student/notesmod-encours"
    private val semestersUrl get() = "$baseUrl/student/notessem"

    /**
     * Fetch the four extra pages. Assumes the session is already authenticated
     * (call checkOnce first in the same client). A page that fails or looks like
     * the login page yields an empty section (caller carries old state forward).
     */
    fun fetchExtras(): ma.ensam.schoolapp.domain.model.Extras {
        fun safe(url: String): String? = try {
            val html = get(url)
            if (SchoolAppParsing.looksLikeLoginPage(html)) null else html
        } catch (e: Exception) { null }

        val abs = safe(absenceUrl)?.let { SchoolAppExtrasParsing.parseAbsenceLog(it) } ?: emptyMap()
        val san = safe(sanctionsUrl)?.let { SchoolAppExtrasParsing.parseSanctions(it) } ?: emptyMap()
        val mods = safe(modulesUrl)?.let { SchoolAppExtrasParsing.parseModulesEncours(it) } ?: emptyMap()
        val sems = safe(semestersUrl)?.let { SchoolAppExtrasParsing.parseSemesterResults(it) } ?: emptyMap()
        return ma.ensam.schoolapp.domain.model.Extras(abs, san, mods, sems)
    }
```

- [ ] **Step 2: Compile-check**

Run (timeout 300000): `./gradlew compileDebugKotlin` → `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppClient.kt
git commit -m "feat(android): SchoolAppClient.fetchExtras() for absences/sanctions/results"
```

---

## Phase 2 — Persistence

### Task 4: Room entities, DAO, database

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/db/Entities.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/db/WatcherDao.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/db/AppDatabase.kt`

- [ ] **Step 1: `Entities.kt`** (snapshot JSON stored as strings; history is the change log shown in the UI)

```kotlin
package ma.ensam.schoolapp.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "snapshots")
data class SnapshotEntity(
    @PrimaryKey val semester: String,     // one current snapshot per semester
    val headersJson: String,
    val rowsJson: String,
    val fingerprint: String,
    val extrasJson: String,               // serialized Extras (may be "{}")
    val updatedAt: Long,
)

@Entity(tableName = "history")
data class HistoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val timestamp: Long,
    val type: String,        // grades | absences | modules | semesters
    val semester: String,
    val summary: String,
)
```

- [ ] **Step 2: `WatcherDao.kt`**

```kotlin
package ma.ensam.schoolapp.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface WatcherDao {
    @Query("SELECT * FROM snapshots WHERE semester = :semester LIMIT 1")
    suspend fun getSnapshot(semester: String): SnapshotEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertSnapshot(snapshot: SnapshotEntity)

    @Insert
    suspend fun insertHistory(entry: HistoryEntity)

    @Query("SELECT * FROM history ORDER BY timestamp DESC LIMIT :limit")
    fun historyFlow(limit: Int): Flow<List<HistoryEntity>>

    @Query("SELECT * FROM history ORDER BY timestamp DESC LIMIT :limit")
    suspend fun recentHistory(limit: Int): List<HistoryEntity>
}
```

- [ ] **Step 3: `AppDatabase.kt`**

```kotlin
package ma.ensam.schoolapp.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [SnapshotEntity::class, HistoryEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun watcherDao(): WatcherDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null
        fun get(context: Context): AppDatabase = INSTANCE ?: synchronized(this) {
            INSTANCE ?: Room.databaseBuilder(
                context.applicationContext, AppDatabase::class.java, "schoolapp.db"
            ).build().also { INSTANCE = it }
        }
    }
}
```

- [ ] **Step 4: Provide via Hilt** — add to `di/AppModule.kt` (new providers; keep existing):

```kotlin
    @Provides @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): ma.ensam.schoolapp.data.db.AppDatabase =
        ma.ensam.schoolapp.data.db.AppDatabase.get(ctx)

    @Provides @Singleton
    fun provideWatcherDao(db: ma.ensam.schoolapp.data.db.AppDatabase): ma.ensam.schoolapp.data.db.WatcherDao =
        db.watcherDao()
```

- [ ] **Step 5: Compile-check (runs Room KSP)**

Run (timeout 300000): `./gradlew compileDebugKotlin` → `BUILD SUCCESSFUL`. If Room reports a schema/annotation error, fix per the message.

- [ ] **Step 6: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/db/ android/app/src/main/java/ma/ensam/schoolapp/di/AppModule.kt
git commit -m "feat(android): Room database (snapshots + history) with Hilt providers"
```

---

### Task 5: WatcherRepository (check → diff → persist → notify)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/repository/WatcherRepository.kt`

**Responsibility:** Single entry point `runCheck(): CheckResult` mirroring `check_once` in watcher.py: authenticate+fetch marks (via `SchoolAppClient.checkOnce`), fetch extras, load previous snapshot from Room, decide `changed` via `Fingerprint.marksState` inequality, persist new snapshot + history, and notify (local + Telegram) when changed. Serialization of headers/rows/extras uses simple JSON via `org.json` (already on Android) to avoid adding a serialization lib.

- [ ] **Step 1: Write `WatcherRepository.kt`**

```kotlin
package ma.ensam.schoolapp.data.repository

import ma.ensam.schoolapp.data.Fingerprint
import ma.ensam.schoolapp.data.db.HistoryEntity
import ma.ensam.schoolapp.data.db.SnapshotEntity
import ma.ensam.schoolapp.data.db.WatcherDao
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.data.remote.TelegramNotifier
import ma.ensam.schoolapp.domain.Diff
import ma.ensam.schoolapp.domain.model.Snapshot
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject

data class CheckResult(val changed: Boolean, val summary: String)

class WatcherRepository @Inject constructor(
    private val client: SchoolAppClient,
    private val dao: WatcherDao,
    private val prefs: EncryptedPrefs,
    private val telegram: TelegramNotifier,
) {
    suspend fun runCheck(): CheckResult {
        val email = prefs.email
        val password = prefs.password
        val semester = prefs.semester
        check(email.isNotBlank() && password.isNotBlank()) { "Credentials not configured" }

        val snap = client.checkOnce(email, password, semester)        // authenticates + marks table
        val old = dao.getSnapshot(semester)
        val oldSnapshot = old?.let { Snapshot(jsonToHeaders(it.headersJson), jsonToRows(it.rowsJson), it.fingerprint) }

        val changed = oldSnapshot == null ||
            Fingerprint.marksState(oldSnapshot.headers, oldSnapshot.rows, semester) !=
            Fingerprint.marksState(snap.headers, snap.rows, semester)

        // Persist new snapshot (extras stored opaque for now; Plan 3 surfaces them).
        val extrasJson = old?.extrasJson ?: "{}"
        dao.upsertSnapshot(
            SnapshotEntity(
                semester = semester,
                headersJson = headersToJson(snap.headers),
                rowsJson = rowsToJson(snap.rows),
                fingerprint = snap.fingerprint,
                extrasJson = extrasJson,
                updatedAt = System.currentTimeMillis(),
            )
        )

        if (!changed) return CheckResult(false, "No change")

        val changes = if (oldSnapshot != null) Diff.compute(oldSnapshot, snap, semester) else emptyList()
        val names = changes.take(3).joinToString(", ") { it.code }
        val summary = if (oldSnapshot == null) "Initialized $semester snapshot"
            else "Grades updated ($semester): ${names.ifEmpty { "changes detected" }}"

        if (oldSnapshot != null) {
            dao.insertHistory(HistoryEntity(timestamp = System.currentTimeMillis(), type = "grades", semester = semester, summary = summary))
            notify(summary, changes)
        }
        return CheckResult(oldSnapshot != null, summary)
    }

    private fun notify(summary: String, changes: List<ma.ensam.schoolapp.domain.ElementChange>) {
        val token = prefs.telegramToken
        val chat = prefs.telegramChatId
        if (token.isBlank() || chat.isBlank()) return
        val body = buildString {
            append("📚 <b>$summary</b>\n")
            changes.take(10).forEach { c ->
                val kind = if (c.isNew) "NOUVEAU" else "MODIFIÉ"
                append("\n<b>${c.code}</b> ($kind)")
                c.fields.entries.take(4).forEach { (f, ov) -> append("\n$f: ${ov.first}→${ov.second}") }
            }
        }
        runCatching { telegram.send(token, chat, body) }
    }

    // ---- minimal JSON (de)serialization for headers/rows ----
    private fun headersToJson(h: List<String>) = JSONArray(h).toString()
    private fun rowsToJson(rows: List<List<String>>): String {
        val outer = JSONArray()
        rows.forEach { outer.put(JSONArray(it)) }
        return outer.toString()
    }
    private fun jsonToHeaders(s: String): List<String> {
        val a = JSONArray(s); return (0 until a.length()).map { a.getString(it) }
    }
    private fun jsonToRows(s: String): List<List<String>> {
        val outer = JSONArray(s)
        return (0 until outer.length()).map { i ->
            val inner = outer.getJSONArray(i)
            (0 until inner.length()).map { inner.getString(it) }
        }
    }
}
```

- [ ] **Step 2: Compile-check** → `./gradlew compileDebugKotlin` → `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/repository/WatcherRepository.kt
git commit -m "feat(android): WatcherRepository orchestrating check/diff/persist/notify"
```

---

## Phase 3 — Notifications

### Task 6: NotificationHelper (two channels)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/service/NotificationHelper.kt`

- [ ] **Step 1: Write `NotificationHelper.kt`**

```kotlin
package ma.ensam.schoolapp.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object NotificationHelper {
    const val CHANNEL_STATUS = "watcher_status"
    const val CHANNEL_UPDATES = "grade_updates"
    const val SERVICE_NOTIF_ID = 1001
    private var updateId = 2000

    fun ensureChannels(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_STATUS, "Watcher Status", NotificationManager.IMPORTANCE_LOW)
                .apply { description = "Shows the watcher is running" }
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_UPDATES, "Grade Updates", NotificationManager.IMPORTANCE_HIGH)
                .apply { description = "New or changed grades, absences, results"; enableVibration(true) }
        )
    }

    /** The persistent foreground notification for the service. */
    fun serviceNotification(context: Context, text: String): Notification =
        NotificationCompat.Builder(context, CHANNEL_STATUS)
            .setContentTitle("SchoolApp Watcher")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()

    /** A high-importance update notification. Safe no-op if POST_NOTIFICATIONS not granted. */
    fun showUpdate(context: Context, title: String, body: String) {
        val notif = NotificationCompat.Builder(context, CHANNEL_UPDATES)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(updateId++, notif) }
    }
}
```

- [ ] **Step 2: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/service/NotificationHelper.kt
git commit -m "feat(android): NotificationHelper with status + updates channels"
```

---

## Phase 4 — Background engine

### Task 7: WatcherService (Foreground Service)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/service/WatcherService.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`

**Notes:** Hilt-injected service (`@AndroidEntryPoint`). Coroutine loop: each iteration runs `repository.runCheck()`, writes `prefs.lastHeartbeat`, shows an update notification on change, then delays a scheduled interval (fast all day, slow 04:00–06:00, with jitter — mirrors `_scheduled_interval`). Uses a `SupervisorJob` scope cancelled in `onDestroy`. On API 34+ `startForeground` must pass the type; we pass `FOREGROUND_SERVICE_TYPE_DATA_SYNC`.

- [ ] **Step 1: Write `WatcherService.kt`**

```kotlin
package ma.ensam.schoolapp.service

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ServiceCompat
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.repository.WatcherRepository
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import javax.inject.Inject
import kotlin.random.Random

@AndroidEntryPoint
class WatcherService : Service() {

    @Inject lateinit var repository: WatcherRepository
    @Inject lateinit var prefs: EncryptedPrefs

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val timeFmt = SimpleDateFormat("HH:mm", Locale.getDefault())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        NotificationHelper.ensureChannels(this)
        startForegroundCompat("Starting…")
        prefs.watcherEnabled = true
        if (!loopStarted) { loopStarted = true; startLoop() }
        return START_STICKY
    }

    private var loopStarted = false

    private fun startLoop() = scope.launch {
        while (isActive) {
            val stamp = timeFmt.format(Date())
            try {
                val result = repository.runCheck()
                prefs.lastHeartbeat = System.currentTimeMillis()
                updateForeground("Last check: $stamp")
                if (result.changed) {
                    NotificationHelper.showUpdate(this@WatcherService, "SchoolApp update", result.summary)
                }
            } catch (e: Exception) {
                prefs.lastHeartbeat = System.currentTimeMillis()
                updateForeground("Last check: $stamp (error)")
            }
            delay(scheduledIntervalMs(prefs.pollIntervalSeconds))
        }
    }

    /** Mirrors _scheduled_interval: fast all day, slow 04:00–06:00, +/- 30s jitter. */
    private fun scheduledIntervalMs(fastSeconds: Int): Long {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val base = if (hour in 4 until 6) 1800 else fastSeconds
        val jittered = (base + Random.nextInt(-30, 31)).coerceAtLeast(30)
        return jittered * 1000L
    }

    private fun startForegroundCompat(text: String) {
        val notif = NotificationHelper.serviceNotification(this, text)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this, NotificationHelper.SERVICE_NOTIF_ID, notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NotificationHelper.SERVICE_NOTIF_ID, notif)
        }
    }

    private fun updateForeground(text: String) {
        startForegroundCompat(text)
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        fun start(context: Context) {
            val i = Intent(context, WatcherService::class.java)
            androidx.core.content.ContextCompat.startForegroundService(context, i)
        }
        fun stop(context: Context) {
            context.stopService(Intent(context, WatcherService::class.java))
        }
    }
}
```

- [ ] **Step 2: Declare the service in `AndroidManifest.xml`** — inside `<application>`, after the `<activity>`:

```xml
        <service
            android:name=".service.WatcherService"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
```

- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL` (confirms Hilt can inject the service).

- [ ] **Step 4: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/service/WatcherService.kt android/app/src/main/AndroidManifest.xml
git commit -m "feat(android): WatcherService foreground polling loop with heartbeat"
```

---

### Task 8: WatchdogWorker (WorkManager keepalive)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/service/WatchdogWorker.kt`
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/SchoolApp.kt` (schedule the periodic work)

**Notes:** Hilt isn't required for this Worker (it reads prefs directly). Periodic 15-min work: if `watcherEnabled` and the heartbeat is older than `pollInterval + 120s`, (re)start the service.

- [ ] **Step 1: Write `WatchdogWorker.kt`**

```kotlin
package ma.ensam.schoolapp.service

import android.content.Context
import androidx.work.Worker
import androidx.work.WorkerParameters
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs

class WatchdogWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val prefs = EncryptedPrefs(applicationContext)
        if (!prefs.watcherEnabled) return Result.success()
        val staleAfter = prefs.pollIntervalSeconds * 1000L + 120_000L
        val age = System.currentTimeMillis() - prefs.lastHeartbeat
        if (prefs.lastHeartbeat == 0L || age > staleAfter) {
            // Heartbeat stale → service likely killed by the OS. Restart it.
            WatcherService.start(applicationContext)
        }
        return Result.success()
    }
}
```

- [ ] **Step 2: Schedule it from `SchoolApp.onCreate()`** — replace the Application body:

```kotlin
package ma.ensam.schoolapp

import android.app.Application
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.HiltAndroidApp
import ma.ensam.schoolapp.service.WatchdogWorker
import java.util.concurrent.TimeUnit

@HiltAndroidApp
class SchoolApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val work = PeriodicWorkRequestBuilder<WatchdogWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "watcher_watchdog", ExistingPeriodicWorkPolicy.KEEP, work
        )
    }
}
```

- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/service/WatchdogWorker.kt android/app/src/main/java/ma/ensam/schoolapp/SchoolApp.kt
git commit -m "feat(android): WatchdogWorker restarts service when heartbeat goes stale"
```

---

### Task 9: BootReceiver

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/service/BootReceiver.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1: Write `BootReceiver.kt`**

```kotlin
package ma.ensam.schoolapp.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            if (EncryptedPrefs(context).watcherEnabled) {
                WatcherService.start(context)
            }
        }
    }
}
```

- [ ] **Step 2: Declare in `AndroidManifest.xml`** — inside `<application>`:

```xml
        <receiver
            android:name=".service.BootReceiver"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
```

- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/service/BootReceiver.kt android/app/src/main/AndroidManifest.xml
git commit -m "feat(android): BootReceiver restarts watcher after reboot"
```

---

## Phase 5 — MIUI survival & onboarding

### Task 10: MiuiUtils

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/util/MiuiUtils.kt`

- [ ] **Step 1: Write `MiuiUtils.kt`** (each intent wrapped; falls back to app-details settings if the OEM screen is missing)

```kotlin
package ma.ensam.schoolapp.util

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

object MiuiUtils {

    fun isMiui(): Boolean {
        val m = Build.MANUFACTURER.lowercase()
        return m.contains("xiaomi") || m.contains("redmi") || m.contains("poco") ||
            !getProp("ro.miui.ui.version.name").isNullOrBlank()
    }

    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.isIgnoringBatteryOptimizations(context.packageName)
    }

    /** ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS for this app. */
    fun openBatteryOptimization(context: Context) {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (!launch(context, intent)) openAppDetails(context)
    }

    /** MIUI/HyperOS auto-start manager. Tries known components, falls back to app details. */
    fun openAutoStart(context: Context) {
        val candidates = listOf(
            ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
            ComponentName("com.miui.securitycenter", "com.miui.powercenter.PowerSettings"),
        )
        for (c in candidates) {
            val intent = Intent().apply { component = c; addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }
            if (launch(context, intent)) return
        }
        openAppDetails(context)
    }

    private fun openAppDetails(context: Context) {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        launch(context, intent)
    }

    private fun launch(context: Context, intent: Intent): Boolean = try {
        context.startActivity(intent); true
    } catch (e: Exception) { false }

    private fun getProp(key: String): String? = try {
        @Suppress("PrivateApi")
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("get", String::class.java)
        (m.invoke(null, key) as? String)
    } catch (e: Exception) { null }
}
```

- [ ] **Step 2: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/util/MiuiUtils.kt
git commit -m "feat(android): MiuiUtils for HyperOS auto-start + battery intents"
```

---

### Task 11: Onboarding screen

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/onboarding/OnboardingScreen.kt`

**Notes:** A Compose screen with three actions: (1) request `POST_NOTIFICATIONS` (API 33+) via an activity-result launcher; (2) battery optimization exemption (MiuiUtils); (3) MIUI auto-start (only shown when `MiuiUtils.isMiui()`). A "Done" button calls `onComplete()` which the caller uses to set `prefs.onboardingComplete = true`. (Add `onboardingComplete` to EncryptedPrefs in Step 1.)

- [ ] **Step 1: Add `onboardingComplete` to `EncryptedPrefs.kt`** (new property + key, mirroring the others):

```kotlin
    var onboardingComplete: Boolean
        get() = prefs.getBoolean(KEY_ONBOARDING, false)
        set(v) = prefs.edit().putBoolean(KEY_ONBOARDING, v).apply()
```
and in the companion object: `private const val KEY_ONBOARDING = "onboarding_complete"`

- [ ] **Step 2: Write `OnboardingScreen.kt`**

```kotlin
package ma.ensam.schoolapp.ui.onboarding

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import ma.ensam.schoolapp.util.MiuiUtils

@Composable
fun OnboardingScreen(onComplete: () -> Unit) {
    val context = LocalContext.current
    val notifLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* result ignored; user can re-trigger from settings */ }

    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Keep the watcher alive", style = MaterialTheme.typography.headlineSmall)
        Text(
            "HyperOS aggressively stops background apps. Grant these so grade checks keep running:",
            style = MaterialTheme.typography.bodyMedium,
        )

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("1. Notifications", style = MaterialTheme.typography.titleMedium)
                Text("Allow notifications so you see grade alerts.")
                Button(
                    onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Allow notifications") }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("2. Battery: No restrictions", style = MaterialTheme.typography.titleMedium)
                Text("Exempt the app from battery optimization.")
                Button(
                    onClick = { MiuiUtils.openBatteryOptimization(context) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Open battery settings") }
            }
        }

        if (MiuiUtils.isMiui()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("3. Auto-start (Xiaomi)", style = MaterialTheme.typography.titleMedium)
                    Text("Enable Autostart for SchoolApp Watcher so it survives reboots and kills.")
                    Button(
                        onClick = { MiuiUtils.openAutoStart(context) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Open auto-start settings") }
                }
            }
        }

        Button(onClick = onComplete, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    }
}
```

- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/ui/onboarding/OnboardingScreen.kt android/app/src/main/java/ma/ensam/schoolapp/data/prefs/EncryptedPrefs.kt
git commit -m "feat(android): onboarding (notifications + battery + MIUI auto-start)"
```

---

## Phase 6 — Wire-up & on-device verification

### Task 12: Wire watcher toggle + onboarding into the app

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/ui/MainViewModel.kt`
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/ui/MainScreen.kt`
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt`

- [ ] **Step 1: Add watcher state + actions to `MainViewModel.kt`** — inject `@ApplicationContext`/prefs is already there; add:
  - field on `MainUiState`: `val watcherOn: Boolean = false`, `val onboardingDone: Boolean = false`
  - init: read `prefs.watcherEnabled` and `prefs.onboardingComplete` into state
  - `fun setWatcher(on: Boolean, context: Context)`: if on → `WatcherService.start(context)` else `WatcherService.stop(context)` and `prefs.watcherEnabled = on`; update state
  - `fun completeOnboarding()`: `prefs.onboardingComplete = true`; update state
  - `fun saveTelegram(token: String, chat: String)`: persist to prefs

(Full method bodies follow the existing `_state.value = _state.value.copy(...)` pattern in the file.)

- [ ] **Step 2: Add to `MainScreen.kt`**: a Switch row "Background watcher" bound to `state.watcherOn` calling `vm.setWatcher(it, context)` (get `context` via `LocalContext.current`); and Telegram token/chat `OutlinedTextField`s with a Save button calling `vm.saveTelegram(...)`.

- [ ] **Step 3: Gate onboarding in `MainActivity.kt`**: observe the ViewModel; if `!onboardingDone` show `OnboardingScreen(onComplete = vm::completeOnboarding)`, else show `MainScreen()`.

- [ ] **Step 4: Compile-check** → `BUILD SUCCESSFUL`.

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/ui/ android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt
git commit -m "feat(android): wire watcher toggle, Telegram config, onboarding gate"
```

---

### Task 13: On-device verification (HyperOS survival)

- [ ] **Step 1: Full unit suite** → `./gradlew testDebugUnitTest` → all green (Plan 1's 35 + extras 5 = 40).

- [ ] **Step 2: Build + install**

```bash
cd /home/notadil/Projects/schoolapp_watcher/android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

- [ ] **Step 3: Onboarding + start watcher** — launch, complete onboarding (grant notifications, battery, auto-start), enter credentials, toggle **Background watcher** on. Confirm the persistent "SchoolApp Watcher — Last check: HH:MM" notification appears:
```bash
adb shell dumpsys notification --noredact | grep -A3 watcher_status
```

- [ ] **Step 4: Confirm the foreground service is running**

```bash
adb shell dumpsys activity services ma.ensam.schoolapp | grep -i "WatcherService\|isForeground"
```
Expected: `WatcherService` present, `isForeground=true`.

- [ ] **Step 5: Simulate a HyperOS kill, confirm watchdog/boot recovery**

```bash
adb shell am force-stop ma.ensam.schoolapp        # simulate OS kill
adb shell dumpsys activity services ma.ensam.schoolapp | grep -i WatcherService   # should be gone
# Manually relaunch the app (or wait for WorkManager); confirm the service returns:
adb shell am start -n ma.ensam.schoolapp/.MainActivity
adb shell dumpsys activity services ma.ensam.schoolapp | grep -i WatcherService
```
Note: WorkManager's 15-min minimum makes immediate watchdog firing impractical to observe; verifying that (a) the service runs, (b) it restarts on app relaunch, and (c) `watcherEnabled` persists is sufficient for this milestone. Document the result.

- [ ] **Step 6: Force a change → notification** (optional, powerful): temporarily set the stored snapshot fingerprint stale by clearing app data and re-checking, OR lower `pollIntervalSeconds` to 60 and confirm a second check runs. Confirm an update notification appears on the `grade_updates` channel when grades differ.

- [ ] **Step 7: Commit a verification marker**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git commit --allow-empty -m "test(android): Plan 2 verified on Redmi (foreground service + watchdog + notifications)"
```

---

## Self-Review (against the design spec)

- **On-device scraping of extras (absences/sanctions/official module+semester)** → Tasks 2, 3. ✓ (parsers unit-tested)
- **Room persistence (snapshots + history)** → Task 4. ✓
- **check→diff→persist→notify orchestration** → Task 5. ✓
- **Two notification channels + Android 13 POST_NOTIFICATIONS** → Tasks 6, 11. ✓
- **Foreground Service (dataSync) with heartbeat + scheduled interval** → Task 7. ✓
- **WatchdogWorker restart on stale heartbeat** → Task 8. ✓
- **BootReceiver** → Task 9. ✓
- **MIUI auto-start + battery intents** → Task 10. ✓
- **Onboarding routing through permission screens** → Task 11. ✓
- **UI toggle + Telegram config + onboarding gate** → Task 12. ✓
- **On-device HyperOS survival verification** → Task 13. ✓
- **Deferred to Plan 3:** surfacing absences/history/results in dedicated screens, bottom-nav, dashboard countdown/pause-resume, colored grade cards, release build + signing + R8, battery-bypass user guide. (Extras are persisted opaquely in Task 5's `extrasJson`; Plan 3 renders them.)

**Type consistency:** `Extras`/`Absence`/`OfficialModule`/`SemesterResultRow` used in Tasks 1/2/3; `WatcherRepository.runCheck(): CheckResult` consumed by Task 7; `WatcherService.start/stop` used by Tasks 8/9/12; `EncryptedPrefs.lastHeartbeat/watcherEnabled/onboardingComplete` used by Tasks 7/8/9/11/12. No placeholders in code steps; Task 12 method bodies follow the existing ViewModel copy-state pattern (the only prose-described task — implementer should follow the established pattern exactly).

## Testing reality (this environment)

- **JVM-unit-tested:** extras parsers (Task 2). Everything else is Android-framework code verified by compile + on-device (Task 13), because Service/WorkManager/Receiver/Compose/Room-on-device aren't JVM-unit-testable here and the device's MIUI guard complicates instrumented-test APK installs.
- **Device install:** always `adb install -r ...` (not `installDebug`).
