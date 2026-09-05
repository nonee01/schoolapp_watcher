# CLAUDE.md

## Build & Install Commands
- **Python Setup**: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e .`
- **Python API Run**: `schoolapp --env-file .env serve` (waitress on port 8787; `--reload` for the Flask dev server; `python3 -m schoolapp.api` still works). The API is read-through: it serves the state store the watcher / `schoolapp fetch-all` write — it does not scrape on GET.
- **Python CLI Run**: `schoolapp s3 list` / `schoolapp s4 list`; `schoolapp fetch-all` (populate the store), `schoolapp status` (store freshness = what the API would serve), `schoolapp export --out DIR`, `schoolapp catalog crawl|show`.
- **Android Build**: `cd android && ./gradlew assembleDebug`
- **Android Install**: `adb install -r android/app/build/outputs/apk/debug/app-debug.apk` (workaround for HyperOS `INSTALL_FAILED_USER_RESTRICTED` on Redmi test device `3ad2f4880013`)

## Test Commands
- **Python Tests**: `pytest`
- **Android Tests**: `cd android && ./gradlew test`

## Architecture & Code Style
- **Python**:
  - Python 3.11+, typed dataclasses (e.g. `Snapshot`), `requests.Session` for scraping.
  - Snapshot change detection using SHA256 of JSON payloads.
  - Frozen API contracts for `/api/status`, `/api/grades/<sem>`, `/api/absences`, `/api/modules`, `/api/semesters`, and `/api/history` (consumed by KDE Plasmoid and Android Native App). Do not alter response shapes.
- **Android (Kotlin)**:
  - Android 13 (API 33) target, Kotlin, Jetpack Compose, Hilt DI, Room DB (`AppDatabase`, `WatcherDao`), ViewModels (`AppViewModel`), background updates via `WatchdogWorker` / `WatcherService`.
  - Repository Pattern (`WatcherRepository`) managing cache reads/writes.
