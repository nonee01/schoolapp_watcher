# SchoolApp Android — Plan 3: Full UI & Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Finish the app into a shippable product: wire the extras (absences/sanctions/official results) all the way through (fetch → persist → diff → notify → display), replace the single scroll screen with a 5-tab bottom-nav UI (Dashboard, Grades, Absences, History, Settings) with color-coded grade cards and a next-check countdown, and produce a **signed release APK** plus a battery-bypass user guide.

**Architecture:** Builds on Plans 1–2. Adds: full `Extras` JSON (de)serialization in the repository; repository read APIs + Room `Flow`s; one `AppViewModel` exposing grades/absences/results/history/status to stateless screen composables; a `Scaffold`+`NavigationBar` shell (state-based tab switch, no extra nav library). Release: a generated keystore + `signingConfig` + `assembleRelease` (R8 already enabled).

**Tech Stack:** No new libraries (uses Compose Material3, Room Flows, existing deps). Release uses `keytool` (JDK 17, already present).

**Target device (verified):** Redmi 2209116AG, HyperOS 1.0, Android 13 / API 33, adb id `3ad2f4880013`. Install with `adb install -r app/build/outputs/apk/...` (the `installDebug` MIUI guard).

---

## Conventions

- Project root: `/home/notadil/Projects/schoolapp_watcher/android/`; branch `android-native-app`; only touch `android/`.
- Gradle Bash timeout 300000 ms. Unit tests: `./gradlew testDebugUnitTest`.
- Python parity already established in Plans 1–2; this plan is mostly Kotlin/Compose UI + build config, verified by compile + on-device.

## File Structure (Plan 3 additions/changes)

```
app/src/main/java/ma/ensam/schoolapp/
├── data/
│   ├── ExtrasJson.kt                      # Task 1 — Extras <-> JSON (testable)
│   ├── remote/SchoolAppClient.kt          # (unchanged; fetchExtras exists)
│   └── repository/WatcherRepository.kt     # Task 2 (modify) — fetch+persist+diff extras; read APIs
├── domain/ExtrasDiff.kt                    # Task 1 — diff extras → summaries (testable)
├── ui/
│   ├── AppViewModel.kt                     # Task 3 — exposes everything to screens
│   ├── Screens.kt                          # Tasks 4-6 — Dashboard/Grades/Absences/History/Settings
│   ├── components/Cards.kt                 # Task 5 — colored grade/module cards
│   └── theme/Theme.kt                      # (unchanged)
├── MainActivity.kt                         # Task 7 (modify) — Scaffold + NavigationBar shell
app/src/test/java/ma/ensam/schoolapp/
├── ExtrasJsonTest.kt                       # Task 1
└── ExtrasDiffTest.kt                       # Task 1
app/build.gradle.kts                        # Task 8 — signingConfig
docs/BATTERY_GUIDE.md                       # Task 9
```

---

## Phase A — Functional completion (extras end-to-end)

### Task 1: Extras JSON (de)serialization + extras diff (TDD)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/ExtrasJson.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/ExtrasDiff.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/ExtrasJsonTest.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/ExtrasDiffTest.kt`

**Note on test JSON:** `org.json` ships in the Android SDK but is NOT on the JVM unit-test classpath by default. To keep `ExtrasJson` unit-testable, implement it with **manual string building + a tiny hand parser is overkill**; instead use `org.json` in main code and add the test dependency `testImplementation("org.json:json:20240303")` so `org.json` resolves in unit tests. (Add this one test dep in Step 0.)

- [ ] **Step 0: Add the JSON test dependency**

In `gradle/libs.versions.toml` `[versions]` add `orgJson = "20240303"`; `[libraries]` add:
```toml
org-json = { group = "org.json", name = "json", version.ref = "orgJson" }
```
In `app/build.gradle.kts` dependencies add `testImplementation(libs.org.json)`. Compile-check: `./gradlew help` is not needed; this is validated by the tests below.

- [ ] **Step 1: Write `ExtrasJsonTest.kt`** (round-trip)

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.ExtrasJson
import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.junit.Assert.assertEquals
import org.junit.Test

class ExtrasJsonTest {
    @Test fun round_trips_all_sections() {
        val extras = Extras(
            absences = mapOf("API411|2024-03-12|S1" to Absence("API411", "2024-03-12", "S1", "true", "retard")),
            sanctions = mapOf("Message" to "Avertissement"),
            modules = mapOf("API41|2023/2024" to OfficialModule("API41", "2023/2024", "13.40", "VRAC")),
            semesters = mapOf("2A|S3|2023/2024" to SemesterResultRow("2A", "S3", "2023/2024", "12.50", "V", "15/120", "--")),
        )
        val json = ExtrasJson.toJson(extras)
        val back = ExtrasJson.fromJson(json)
        assertEquals(extras.absences, back.absences)
        assertEquals(extras.sanctions, back.sanctions)
        assertEquals(extras.modules, back.modules)
        assertEquals(extras.semesters, back.semesters)
    }

    @Test fun empty_and_malformed_yield_empty() {
        assertEquals(Extras(), ExtrasJson.fromJson("{}"))
        assertEquals(Extras(), ExtrasJson.fromJson(""))
        assertEquals(Extras(), ExtrasJson.fromJson("not json"))
    }
}
```

- [ ] **Step 2: Run → FAIL.** `./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.ExtrasJsonTest"`

- [ ] **Step 3: Write `ExtrasJson.kt`**

```kotlin
package ma.ensam.schoolapp.data

import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.json.JSONObject

/** Serializes Extras to a single JSON object string and back. Tolerant of bad input. */
object ExtrasJson {

    fun toJson(e: Extras): String {
        val root = JSONObject()
        val abs = JSONObject()
        e.absences.forEach { (k, a) ->
            abs.put(k, JSONObject()
                .put("element", a.element).put("date", a.date).put("seance", a.seance)
                .put("justif", a.justif).put("remarks", a.remarks))
        }
        val san = JSONObject(); e.sanctions.forEach { (k, v) -> san.put(k, v) }
        val mods = JSONObject()
        e.modules.forEach { (k, m) ->
            mods.put(k, JSONObject().put("code", m.code).put("au", m.au).put("moy", m.moy).put("dec", m.dec))
        }
        val sems = JSONObject()
        e.semesters.forEach { (k, s) ->
            sems.put(k, JSONObject()
                .put("niveau", s.niveau).put("sem", s.sem).put("au", s.au).put("moy", s.moy)
                .put("dec", s.dec).put("rank", s.rank).put("pj", s.pj))
        }
        return root.put("absences", abs).put("sanctions", san).put("modules", mods).put("semesters", sems).toString()
    }

    fun fromJson(s: String): Extras {
        if (s.isBlank()) return Extras()
        val root = runCatching { JSONObject(s) }.getOrNull() ?: return Extras()
        return Extras(
            absences = root.optJSONObject("absences")?.let { o ->
                o.keys().asSequence().associateWith { k ->
                    val a = o.getJSONObject(k)
                    Absence(a.optString("element"), a.optString("date"), a.optString("seance"), a.optString("justif"), a.optString("remarks"))
                }
            } ?: emptyMap(),
            sanctions = root.optJSONObject("sanctions")?.let { o ->
                o.keys().asSequence().associateWith { k -> o.optString(k) }
            } ?: emptyMap(),
            modules = root.optJSONObject("modules")?.let { o ->
                o.keys().asSequence().associateWith { k ->
                    val m = o.getJSONObject(k)
                    OfficialModule(m.optString("code"), m.optString("au"), m.optString("moy"), m.optString("dec"))
                }
            } ?: emptyMap(),
            semesters = root.optJSONObject("semesters")?.let { o ->
                o.keys().asSequence().associateWith { k ->
                    val s2 = o.getJSONObject(k)
                    SemesterResultRow(s2.optString("niveau"), s2.optString("sem"), s2.optString("au"), s2.optString("moy"), s2.optString("dec"), s2.optString("rank"), s2.optString("pj"))
                }
            } ?: emptyMap(),
        )
    }
}
```

- [ ] **Step 4: Run → PASS (2 tests).**

- [ ] **Step 5: Write `ExtrasDiffTest.kt`**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.ExtrasDiff
import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtrasDiffTest {
    @Test fun new_absence_is_reported() {
        val old = Extras()
        val new = Extras(absences = mapOf("API411|2024-03-12|S1" to Absence("API411", "2024-03-12", "S1", "false", "")))
        val msgs = ExtrasDiff.summaries(old, new)
        assertEquals(1, msgs.size)
        assertTrue(msgs[0].contains("API411"))
    }

    @Test fun unchanged_yields_nothing() {
        val e = Extras(sanctions = mapOf("Message" to "Avertissement"))
        assertTrue(ExtrasDiff.summaries(e, e).isEmpty())
    }

    @Test fun changed_module_decision_reported() {
        val old = Extras(modules = mapOf("API41|2023/2024" to ma.ensam.schoolapp.domain.model.OfficialModule("API41", "2023/2024", "9.0", "NV")))
        val new = Extras(modules = mapOf("API41|2023/2024" to ma.ensam.schoolapp.domain.model.OfficialModule("API41", "2023/2024", "13.4", "VRAC")))
        val msgs = ExtrasDiff.summaries(old, new)
        assertTrue(msgs.any { it.contains("API41") })
    }
}
```

- [ ] **Step 6: Run → FAIL.**

- [ ] **Step 7: Write `ExtrasDiff.kt`**

```kotlin
package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Extras

/** Human-readable one-line summaries of what changed between two Extras. */
object ExtrasDiff {
    fun summaries(old: Extras, new: Extras): List<String> {
        val out = ArrayList<String>()
        // New or newly-justified absences
        for ((k, a) in new.absences) {
            val o = old.absences[k]
            if (o == null) {
                val j = if (a.justif == "true") "justifiée" else "non justifiée"
                out.add("🚨 Absence $j — ${a.element} (${a.date} ${a.seance})")
            } else if (o.justif != a.justif && a.justif == "true") {
                out.add("✅ Absence justifiée — ${a.element} (${a.date})")
            }
        }
        // Sanctions changes
        for ((k, v) in new.sanctions) {
            if (old.sanctions[k] != v) out.add("⚠️ Sanction — $k: $v")
        }
        // Official module results
        for ((k, m) in new.modules) {
            if (old.modules[k] != m) out.add("📋 Module ${m.code} — ${m.moy} (${m.dec})")
        }
        // Semester results
        for ((k, s) in new.semesters) {
            if (old.semesters[k] != s) out.add("🎓 ${s.sem} — Moy ${s.moy}, rang ${s.rank} (${s.dec})")
        }
        return out
    }
}
```

- [ ] **Step 8: Run → PASS (3 tests). Commit.**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/gradle/libs.versions.toml android/app/build.gradle.kts \
  android/app/src/main/java/ma/ensam/schoolapp/data/ExtrasJson.kt \
  android/app/src/main/java/ma/ensam/schoolapp/domain/ExtrasDiff.kt \
  android/app/src/test/java/ma/ensam/schoolapp/ExtrasJsonTest.kt \
  android/app/src/test/java/ma/ensam/schoolapp/ExtrasDiffTest.kt
git commit -m "feat(android): Extras JSON round-trip + extras diff summaries (tested)"
```

---

### Task 2: Wire extras into WatcherRepository + read APIs

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/data/repository/WatcherRepository.kt`

**Changes:** (1) After `checkOnce`, call `client.fetchExtras()`, serialize with `ExtrasJson.toJson`, persist in the snapshot row; (2) diff old vs new extras via `ExtrasDiff.summaries`, append each as a `HistoryEntity` (type from the emoji-prefixed message → use type "absences"/"modules"/"semesters"/"sanctions" by simple keyword, or just "extras") and include them in the notification body; (3) add read APIs the UI needs: `latestSnapshot(semester): Snapshot?`, `latestExtras(semester): Extras`, `historyFlow(limit): Flow<List<HistoryEntity>>`.

- [ ] **Step 1: Replace the body of `runCheck()`** so that after computing `snap` and BEFORE persisting, it fetches extras and persists them, and folds extras summaries into history + notification. Add imports for `ExtrasJson`, `ExtrasDiff`, `Extras`, `Flow`. Concretely:
  - `val newExtras = runCatching { client.fetchExtras() }.getOrDefault(Extras())`
  - `val oldExtras = old?.let { ExtrasJson.fromJson(it.extrasJson) } ?: Extras()`
  - persist `extrasJson = ExtrasJson.toJson(newExtras)` (replace the old `extrasJson` carry-forward line)
  - `val extrasMsgs = if (old != null) ExtrasDiff.summaries(oldExtras, newExtras) else emptyList()`
  - `val changed = gradesChanged || extrasMsgs.isNotEmpty()` (where `gradesChanged` is the existing marks-state comparison)
  - on change: insert a history row for grades (if gradesChanged) and one per extras message; build the notification body from both; call `notify(...)` and `NotificationHelper` is invoked by the SERVICE (repository only sends Telegram + returns summary — keep current split: repository sends Telegram, service shows the local notification from `CheckResult.summary`). Ensure `CheckResult.summary` includes a short combined headline.

- [ ] **Step 2: Add read APIs** at the end of the class:
```kotlin
    suspend fun latestSnapshot(semester: String): ma.ensam.schoolapp.domain.model.Snapshot? {
        val e = dao.getSnapshot(semester) ?: return null
        return ma.ensam.schoolapp.domain.model.Snapshot(jsonToHeaders(e.headersJson), jsonToRows(e.rowsJson), e.fingerprint)
    }
    suspend fun latestExtras(semester: String): ma.ensam.schoolapp.domain.model.Extras {
        val e = dao.getSnapshot(semester) ?: return ma.ensam.schoolapp.domain.model.Extras()
        return ma.ensam.schoolapp.data.ExtrasJson.fromJson(e.extrasJson)
    }
    fun historyFlow(limit: Int) = dao.historyFlow(limit)
```

- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL`. Run full unit suite → all green (Plan 1-2's 40 + Task 1's 5 = 45).

- [ ] **Step 4: Commit**
```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/repository/WatcherRepository.kt
git commit -m "feat(android): fetch+persist+diff extras in runCheck; repository read APIs"
```

---

## Phase B — Multi-screen UI

### Task 3: AppViewModel (shared state for all screens)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/AppViewModel.kt`

**Responsibility:** Hilt ViewModel injecting `WatcherRepository`, `EncryptedPrefs`, `SchoolAppClient`. Holds `StateFlow<AppUiState>` with: credentials/telegram/semester/interval (from prefs), watcherOn, onboardingDone, loading/error, the latest `Snapshot`, the computed `SemesterResult` (grades cards), `Extras` (absences/results), and exposes `historyFlow`. Actions: `checkNow()` (calls repository.runCheck off the IO dispatcher, then refreshes latestSnapshot/latestExtras + recomputes calculator), `setWatcher(on, context)`, `completeOnboarding()`, save credentials/telegram/interval, `lastCheckEpoch`/`nextCheckEpoch` derived from `prefs.lastHeartbeat + pollInterval`. Reuse the marks→`SemesterResult` mapping and `marksFromSnapshot` from the old `MainViewModel` (move it here). On init, load persisted snapshot/extras so screens have data before any live check.

- [ ] **Step 1: Write `AppViewModel.kt`** implementing the above. It supersedes `MainViewModel`; keep `MainViewModel` file deletion for Task 7. Provide complete state + actions following the existing `_state.value = _state.value.copy(...)` pattern. (Full file written by the implementer using the established patterns from `MainViewModel`; every field/method concrete, no TODOs.)
- [ ] **Step 2: Compile-check** → `BUILD SUCCESSFUL`.
- [ ] **Step 3: Commit** `feat(android): AppViewModel exposing grades/absences/results/history/status`

---

### Task 4: Colored cards + Grades/Dashboard screens

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/components/Cards.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt` (Dashboard + Grades portions)

- [ ] **Step 1: `Cards.kt`** — `@Composable fun ModuleCard(result: ModuleResult, elements: ...)` with a left border + status chip colored green (VORD), amber (RAT), red (NV) via `ModuleStatus`; `StatusChip(status)`. Grade element rows show CC/EX/TP/Moy.
- [ ] **Step 2: Dashboard** — watcher status (Running/Stopped), last check (from `lastCheckEpoch`), **next-check countdown** (a `LaunchedEffect` ticking every second to `nextCheckEpoch`), a **Check Now** button, and a **pause/resume** Switch (calls `setWatcher`).
- [ ] **Step 3: Grades screen** — list of `ModuleCard`s from `state.calc.modules` zipped with preset elements; a semester-average header.
- [ ] **Step 4: Compile-check; commit** `feat(android): colored module cards + Dashboard + Grades screens`.

---

### Task 5: Absences / History / Settings screens

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt` (add three more screens)

- [ ] **Step 1: Absences screen** — from `state.extras.absences` (sorted by date desc): each row shows element + date + séance + a justified/non-justified chip; plus a sanctions section from `state.extras.sanctions`.
- [ ] **Step 2: History screen** — collect `repository.historyFlow(200)` (exposed via AppViewModel) and list `timestamp · semester · summary` with a type emoji.
- [ ] **Step 3: Settings screen** — credential fields, Telegram token/chat, a **poll-interval slider** (e.g., 60s–3600s) saving to prefs, the **S3/S4** picker, and the **calculator** (reuse the calc card from Plan 1) with a "Recompute" button.
- [ ] **Step 4: Compile-check; commit** `feat(android): Absences, History, Settings screens`.

---

### Task 6: Results screen (official modules + semesters)

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/ui/Screens.kt`

- [ ] **Step 1: Results screen** — two sections from `state.extras`: official module results (`modules`) and semester results (`semesters`), each a card with code/AU/moy/decision colored by decision (V* green, NV red, else gray).
- [ ] **Step 2: Compile-check; commit** `feat(android): official Results screen (modules + semesters)`.

---

### Task 7: Navigation shell (bottom nav) + onboarding gate

**Files:**
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt`
- Delete: `android/app/src/main/java/ma/ensam/schoolapp/ui/MainScreen.kt`, `android/app/src/main/java/ma/ensam/schoolapp/ui/MainViewModel.kt`

- [ ] **Step 1: MainActivity** — keep the `@Inject prefs` recovery start; `setContent` shows `OnboardingScreen` when `!onboardingDone` else a `Scaffold` with a `NavigationBar` of 5 items (Dashboard 📊, Grades 📚, Absences 🚨, Results 🎓, Settings ⚙️) and a `when(tab)` body calling the screen composables with `AppViewModel` (via `hiltViewModel()`). Use a `rememberSaveable` `tab` index. Keep `SchoolAppTheme`.
- [ ] **Step 2: Remove the now-unused `MainScreen.kt`/`MainViewModel.kt`** (their logic moved to `AppViewModel`/`Screens.kt`). Ensure nothing references them.
- [ ] **Step 3: Compile-check** → `BUILD SUCCESSFUL`. Build + install + on-device smoke test: launch, tab through all 5 screens, Check Now populates Grades/Absences/Results, Dashboard countdown ticks. Screenshot each.
- [ ] **Step 4: Commit** `feat(android): 5-tab bottom-nav shell; retire single MainScreen`.

---

## Phase C — Release

### Task 8: Signed release build

**Files:**
- Modify: `android/app/build.gradle.kts`
- Create: `android/keystore.properties` (gitignored), `android/app/schoolapp-release.jks` (gitignored)
- Modify: `android/.gitignore`

- [ ] **Step 1: Generate a keystore** (non-interactive):
```bash
cd /home/notadil/Projects/schoolapp_watcher/android
keytool -genkeypair -v -keystore app/schoolapp-release.jks -keyalg RSA -keysize 2048 -validity 10000 \
  -alias schoolapp -storepass schoolapp123 -keypass schoolapp123 \
  -dname "CN=SchoolApp Watcher, OU=Personal, O=ENSAM, L=Meknes, S=Meknes, C=MA"
```

- [ ] **Step 2: `keystore.properties`** (gitignored — secrets):
```properties
storeFile=schoolapp-release.jks
storePassword=schoolapp123
keyAlias=schoolapp
keyPassword=schoolapp123
```

- [ ] **Step 3: Add to `.gitignore`:** `keystore.properties` and `*.jks`.

- [ ] **Step 4: Wire `signingConfigs` in `app/build.gradle.kts`** — at the top of the `android {}` block load the properties; add a `release` signing config; set `buildTypes.release.signingConfig = signingConfigs.getByName("release")`. (R8 `isMinifyEnabled=true` is already set.) Load pattern:
```kotlin
    val keystorePropsFile = rootProject.file("keystore.properties")
    val keystoreProps = java.util.Properties().apply {
        if (keystorePropsFile.exists()) load(keystorePropsFile.inputStream())
    }
    signingConfigs {
        create("release") {
            if (keystorePropsFile.exists()) {
                storeFile = file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }
```
and in `buildTypes { release { ... } }` add `signingConfig = signingConfigs.getByName("release")`.

- [ ] **Step 5: Build the release APK** (R8 shrink/obfuscate):
```bash
cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew assembleRelease
```
Expected: `BUILD SUCCESSFUL`, APK at `app/build/outputs/apk/release/app-release.apk`. If R8 strips something needed (Room/Hilt/Jsoup/OkHttp), add keep rules to `proguard-rules.pro` per the missing-class error and rebuild.

- [ ] **Step 6: Install the release APK on device** and smoke-test (it's a different signature than debug, so uninstall debug first if it conflicts):
```bash
adb uninstall ma.ensam.schoolapp 2>/dev/null; adb install app/build/outputs/apk/release/app-release.apk
adb shell am start -n ma.ensam.schoolapp/.MainActivity
```
Confirm no crash (R8 can break reflection — verify the scraper login + a Check Now still works, since OkHttp/Jsoup are reflection-sensitive).

- [ ] **Step 7: Commit** (config only; NOT the jks/properties):
```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/build.gradle.kts android/.gitignore android/app/proguard-rules.pro
git commit -m "build(android): signed release config + R8 keep rules; assembleRelease"
```

---

### Task 9: Battery-bypass user guide + final verification

**Files:**
- Create: `docs/BATTERY_GUIDE.md`

- [ ] **Step 1: Write `docs/BATTERY_GUIDE.md`** — concrete HyperOS steps: Settings → Apps → SchoolApp Watcher → **Autostart ON**; **Battery saver → No restrictions**; lock the app in Recents (swipe down on the card → lock); disable **MIUI Optimization** caveats; enable notifications. Include the in-app onboarding buttons as the first-line path and these manual steps as backup.
- [ ] **Step 2: Final on-device pass** — release APK installed; complete onboarding; enter credentials + Telegram; toggle watcher on; confirm foreground notification; tab through all 5 screens with real data; `adb shell am force-stop` then relaunch → service recovers. Document results.
- [ ] **Step 3: Commit** `docs(android): battery-bypass guide; Plan 3 verified on device`.

---

## Self-Review (against spec)

- **Extras end-to-end (fetch→persist→diff→notify→display)** → Tasks 1, 2 (logic, tested), 5, 6 (display). ✓ (closes the Plan 2 gap where `fetchExtras()` was never called)
- **Dashboard with status + last/next check countdown + pause/resume** → Task 4. ✓
- **Color-coded grade/module cards (VORD/RAT/NV)** → Task 4. ✓
- **Absences, History, Results, Settings(+calculator+interval slider) screens** → Tasks 5, 6. ✓
- **Bottom-nav navigation** → Task 7. ✓
- **Signed release APK with R8** → Task 8. ✓
- **Battery-bypass guide** → Task 9. ✓

**Testing reality:** JVM-unit-tested = ExtrasJson + ExtrasDiff (Task 1, 5 tests). Everything else is Compose UI / build config verified by compile + on-device (Tasks 7, 8, 9). Release R8 is the main risk → Task 8 Step 6 explicitly re-tests the reflection-sensitive scraper on the release build.

**Type consistency:** `Extras`/`Absence`/`OfficialModule`/`SemesterResultRow` reused from Plan 2; `ExtrasJson.toJson/fromJson` (Task 1) used by Task 2 + AppViewModel; `ExtrasDiff.summaries` used by Task 2; `WatcherRepository.latestSnapshot/latestExtras/historyFlow` (Task 2) consumed by `AppViewModel` (Task 3); `ModuleStatus` colors in Task 4; `AppViewModel` consumed by all screens (Tasks 4-7). `MainScreen`/`MainViewModel` retired in Task 7.
