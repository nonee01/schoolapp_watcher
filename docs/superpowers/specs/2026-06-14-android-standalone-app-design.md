# SchoolApp Android — Standalone On-Device App Design

**Date:** 2026-06-14  
**Status:** Approved  
**Scope:** Native Kotlin Android app that replaces the Flask API + React Native + systemd architecture with a fully self-contained, serverless Android application.

---

## Problem Statement

The current architecture requires a laptop running a Python Flask API (over Tailscale) to serve the React Native mobile app. If the laptop is off or Tailscale disconnects, the mobile app is dead. The goal is to move all logic onto the Android device itself: scraping, fingerprinting, snapshot diffing, notifications, and background polling.

**Critical constraint:** Zero server infrastructure. The app must work offline from any external backend.

---

## Target Device Context

Primary device: **Xiaomi (MIUI/HyperOS)**. Xiaomi's OS aggressively kills background processes, ignores WorkManager timing guarantees, and blocks auto-start. The architecture is specifically engineered to survive this.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Kotlin |
| UI | Jetpack Compose (Material 3) |
| Architecture | MVVM + Clean Architecture |
| DI | Hilt |
| HTTP | OkHttp3 (with persistent CookieJar) |
| HTML Parsing | Jsoup |
| Local DB | Room (SQLite) |
| Secure Storage | EncryptedSharedPreferences |
| Background | ForegroundService (primary) + WorkManager watchdog (keepalive) |
| Notifications | NotificationManagerCompat (two channels) |
| Telegram | Direct OkHttp POST to Telegram Bot API |

---

## Architecture

### Layers

```
Python equivalent          Kotlin equivalent
─────────────────────────────────────────────────────
requests.Session        →  OkHttpClient + persistent CookieJar
BeautifulSoup           →  Jsoup
hashlib.sha256          →  java.security.MessageDigest
_marks_state()          →  Fingerprint.kt (per-element diff, ignores row order)
watch_loop()            →  WatcherService.kt (ForegroundService coroutine loop)
send_telegram()         →  TelegramNotifier.kt (direct OkHttp POST)
snapshot JSON files     →  Room: SnapshotEntity + HistoryEntity
.env / TOML config      →  EncryptedSharedPreferences
```

### Project Structure

```
app/src/main/
├── AndroidManifest.xml
├── java/ma/ensam/schoolapp/
│   ├── data/
│   │   ├── db/
│   │   │   ├── AppDatabase.kt
│   │   │   ├── SnapshotEntity.kt
│   │   │   ├── HistoryEntity.kt
│   │   │   └── WatcherDao.kt
│   │   ├── prefs/
│   │   │   └── EncryptedPrefs.kt
│   │   ├── remote/
│   │   │   ├── SchoolAppClient.kt      ← core scraper
│   │   │   └── TelegramNotifier.kt
│   │   └── repository/
│   │       └── WatcherRepository.kt
│   ├── domain/
│   │   ├── model/
│   │   │   ├── Module.kt
│   │   │   ├── Element.kt
│   │   │   ├── Snapshot.kt
│   │   │   └── HistoryEntry.kt
│   │   └── usecase/
│   │       ├── CheckGradesUseCase.kt
│   │       └── GetHistoryUseCase.kt
│   ├── service/
│   │   ├── WatcherService.kt           ← ForegroundService (primary engine)
│   │   ├── WatchdogWorker.kt           ← WorkManager keepalive (15-min)
│   │   └── BootReceiver.kt             ← restart on reboot
│   ├── ui/
│   │   ├── onboarding/
│   │   │   ├── OnboardingScreen.kt     ← MIUI permissions + POST_NOTIFICATIONS
│   │   │   └── OnboardingViewModel.kt
│   │   ├── dashboard/
│   │   │   ├── DashboardScreen.kt
│   │   │   └── DashboardViewModel.kt
│   │   ├── grades/
│   │   │   ├── GradesScreen.kt
│   │   │   └── GradesViewModel.kt
│   │   ├── absences/
│   │   │   └── AbsencesScreen.kt
│   │   ├── history/
│   │   │   └── HistoryScreen.kt
│   │   └── settings/
│   │       ├── SettingsScreen.kt
│   │       └── SettingsViewModel.kt
│   └── util/
│       ├── MiuiUtils.kt                ← Xiaomi Auto-Start + Battery intents
│       ├── Fingerprint.kt              ← SHA-256 snapshot hashing
│       └── NotificationHelper.kt       ← two notification channels
└── res/
    └── ...
```

---

## Component Design

### SchoolAppClient.kt

Translates the Python scraper exactly:

1. `login(email, password)`: GET `/login` → extract `input[name="_csrf"]` via Jsoup → POST credentials + CSRF → verify not redirected back to login.
2. `fetchMarksHtml()`: GET `/student/noteselem-encours` — reuses session cookies from OkHttp CookieJar.
3. `fetchExtras()`: Fetches `/student/absence/bilan`, `/student/absence/sanctions`, `/student/notesmod-encours`, `/student/notessem` in sequence.
4. `extractTable(html)`: Jsoup-parse the largest `<table>` by row count, extract headers from `<th>` and rows from `<td>`.
5. `looksLikeLoginPage(html)`: Check for `form[action="/login"]` + `input[name="password"]`.

OkHttp CookieJar is a simple in-memory implementation (no disk persistence needed — login is cheap and re-runs on session expiry).

### Fingerprint.kt

Replicates `_marks_state()` from Python: extracts only the real grade fields (CC, EX, TP, MoySO, RAT, MoySR, Moy, Dec) per CodeElem, ignores row order, serializes to sorted JSON, then SHA-256 hashes. Cosmetic page changes do not trigger notifications.

### WatcherService.kt (ForegroundService)

- `foregroundServiceType = dataSync` declared in manifest (required for Android 14+, prevents instant crash).
- Starts a coroutine scope (`Dispatchers.IO`) with a `while(true) { ... delay(intervalMs) }` loop.
- On each iteration: calls `CheckGradesUseCase`, compares fingerprints, fires local notification + Telegram if changed.
- Persistent notification on channel `watcher_status` (LOW importance, not dismissible): "SchoolApp Watcher — Last check: HH:MM".
- Grade change notification on channel `grade_updates` (HIGH importance, vibration): shows changed element names and new grades.

### WatchdogWorker.kt (WorkManager, 15-min periodic)

Single responsibility: check if `WatcherService` is alive. Detection method: `WatcherService` writes a heartbeat timestamp to `EncryptedPrefs` on every poll iteration. The watchdog reads this timestamp; if it is older than `pollInterval + 2 minutes`, the service is considered dead and restarted. (Note: `ActivityManager.getRunningServices()` is deprecated/restricted for third-party apps since API 26 and is not used.) If user has enabled the watcher, starts `WatcherService`. This catches the case where Xiaomi silently kills the ForegroundService during memory pressure.

### BootReceiver.kt

Listens for `ACTION_BOOT_COMPLETED`. If the user previously had the watcher enabled (stored in EncryptedPrefs), starts `WatcherService` automatically.

### MiuiUtils.kt

Detects MIUI/HyperOS via `Build.MANUFACTURER` check. Provides:
- `isMiui(): Boolean`
- `openAutoStartSettings(context)`: fires `miui.intent.action.OP_AUTO_START` intent
- `openBatteryOptimizationSettings(context)`: fires `Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`
- `openMiuiBatterySaverSettings(context)`: fallback to MIUI-specific battery settings screen

### Onboarding Flow

Three steps shown only on first launch:
1. **POST_NOTIFICATIONS** (Android 13+): `ActivityCompat.requestPermissions` for `POST_NOTIFICATIONS`.
2. **Battery Optimization**: button fires `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` for the app's package.
3. **MIUI Auto-Start** (shown only if `isMiui()`): button fires the MIUI auto-start intent with fallback instructions if intent is not available on this MIUI version.

Completion stored in EncryptedPrefs as `onboarding_complete = true`.

### EncryptedPrefs.kt

Wraps `EncryptedSharedPreferences` with typed accessors:
- `email`, `password` (SchoolApp credentials)
- `telegramToken`, `telegramChatId`
- `pollIntervalSeconds` (default 900)
- `semester` (S3/S4)
- `watcherEnabled`, `onboardingComplete`

### Room Database

**SnapshotEntity**: `id`, `semester`, `headersJson`, `rowsJson`, `fingerprint`, `extrasJson`, `timestamp`  
**HistoryEntity**: `id`, `semester`, `type` (grades/absences/modules/semesters), `summary`, `timestamp`

---

## AndroidManifest.xml — Permissions & Declarations

```xml
<!-- Network -->
<uses-permission android:name="android.permission.INTERNET" />

<!-- Background execution -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
<uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />

<!-- Notifications (Android 13+) -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

<!-- Service declaration (Android 14 requires foregroundServiceType) -->
<service
    android:name=".service.WatcherService"
    android:foregroundServiceType="dataSync"
    android:exported="false" />

<!-- Boot receiver -->
<receiver
    android:name=".service.BootReceiver"
    android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED" />
    </intent-filter>
</receiver>
```

---

## Grade Calculator (embedded)

The S3/S4 module/element presets from `presets.py` are translated to Kotlin data classes (`ModuleDef`, `ElementDef`). The `_calc_element_grade()` logic (`cc * coef_cc + ex * coef_ex`) is preserved exactly. The Settings screen hosts the calculator UI (preset picker, per-element CC/EX/TP inputs, computed module and semester averages with VORD/RAT/NV color coding).

---

## Notification Channels

| Channel ID | Name | Importance | Use |
|---|---|---|---|
| `watcher_status` | Watcher Status | LOW | Persistent "running" notification |
| `grade_updates` | Grade Updates | HIGH | New/changed grades, absences, sanctions |

---

## Build & Release

- `./gradlew assembleRelease` with R8 enabled (default in release builds)
- ProGuard rules to keep: OkHttp, Jsoup, Room, Hilt generated classes
- Rules to obfuscate: `SchoolAppClient`, `TelegramNotifier`, endpoint strings (move to `BuildConfig` fields or string resources not included in R8 keep rules)

---

## Out of Scope

- iOS support
- Any server, API, Docker, VPS, or Tailscale
- Python-to-APK wrappers (Kivy/Buildozer)
- Web interface
