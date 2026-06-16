# SchoolApp Watcher — KDE Plasma Widget Design

**Date:** 2026-06-16
**Status:** Approved

## Overview

A KDE Plasma 6 panel widget that monitors the running `schoolapp-watcher.service` and fires desktop notifications when grade or absence changes are detected. Lives in `schoolapp_watcher/plasmoid/`. Follows the same architecture as the existing `claude-usage-plasmoid` in this user's projects.

---

## Architecture

```
schoolapp_watcher/
└── plasmoid/
    ├── install.sh
    ├── uninstall.sh
    └── package/
        ├── metadata.json
        └── contents/
            ├── scripts/
            │   └── schoolapp_status.py   # Python backend — stdout = JSON
            ├── config/
            │   ├── config.qml
            │   ├── configGeneral.qml
            │   └── main.xml
            └── ui/
                └── main.qml             # QML widget
```

### Data flow

1. QML `Timer` (30s interval) calls `exec.run()` via `Plasma5Support.DataSource` (executable engine)
2. This spawns: `python3 schoolapp_status.py <api_url> <api_key>`
3. Script calls `GET /api/status` + `GET /api/history?limit=10` on `localhost:8787`
4. Script compares latest history entry `id`/timestamp against `~/.cache/schoolapp-widget/last_seen.json`
5. Script outputs one JSON blob to stdout; QML parses it
6. If `new_change: true`, QML fires a `Notification` (org.kde.notification)
7. A separate 1s QML `Timer` ticks down the `next_check_s` countdown in the compact view

### Python script contract

Input: `argv[1]` = API URL, `argv[2]` = API key (both passed by QML from `Plasmoid.configuration`)

Output (stdout, always valid JSON):
```json
{
  "ok": true,
  "watcher": "active",
  "next_check_s": 102,
  "poll_interval": 120,
  "last_check": "2026-06-16T14:31:08",
  "last_change": "2026-06-15T23:40:24",
  "latest_change_type": "grades",
  "latest_change_summary": "Notes mises à jour — S4",
  "history": [
    { "ts": "2026-06-15T23:40:24", "type": "grades", "summary": "Notes mises à jour — S4", "new": true },
    { "ts": "2026-06-15T16:41:31", "type": "modules", "summary": "Résultat module: Algèbre 2 — RAT (9.08)", "new": false }
  ],
  "new_change": false,
  "new_summaries": [],
  "error": "",
  "updated": "14:32"
}
```

`new_change` is the boolean edge trigger (true when at least one entry is newer than `last_seen.ts`). `new_summaries` is the ordered list of `summary` strings for those new entries (newest first), so QML builds the notification body directly. Each `history` item carries a `new` flag so the Changes tab can badge it without re-deriving `last_seen`. The script writes `last_seen.ts` **after** computing these, so the next poll sees them as seen.

**History entry shape (ground truth).** The watcher appends to `~/.local/state/schoolapp/changes.jsonl` and `/api/history` returns those lines reversed (newest first). Each entry has exactly these fields:

| Field | Example | Notes |
|-------|---------|-------|
| `ts` | `"2026-06-15T23:40:24"` | ISO timestamp, `timespec="seconds"` |
| `type` | `"grades"` | one of `grades`, `absences`, `modules`, `semesters` |
| `semester` | `"S4"` | semester code |
| `summary` | `"Notes mises à jour — S4"` | ready-made human string (French); grades summaries are generic, module/semester summaries carry detail like `"Résultat module: Algèbre 2 — RAT (9.08)"` |

The widget never parses element-level detail out of the history — it surfaces `summary` verbatim. Per-element current values come from `/api/grades/S4` (Grades tab only).

On any failure: `ok: false`, `error: "..."`, history/watcher fields are empty/null. Widget shows last known data grayed out.

### Caching / change detection

- `~/.cache/schoolapp-widget/last_seen.json` stores `{ "ts": "<ISO timestamp of latest seen history entry>" }`
- Script sets `new_change: true` only when the newest history entry's timestamp is newer than `last_seen.ts`
- On a successful response, script updates `last_seen.ts`
- First run (no cache): baselines silently, `new_change: false`

---

## UI Design

### Compact (panel bar) — 4 states

| State | Appearance |
|-------|-----------|
| Has any history | green dot + type chip + truncated latest `summary` (e.g. `📊 Notes mises à jour — S4`) |
| No history yet | green dot + `No changes` (muted) |
| Service stopped | red dot + `stopped` |
| Manually paused | amber dot + `paused` |
| API error | amber dot + `error` |

The compact view always shows the most recent entry from `/api/history` (if any). There is no time-based reset — the pill simply reflects the latest known change at all times. An icon keyed off `type` (📊 grades · 🚫 absences · 📋 modules · 🎓 semesters) precedes the summary; the summary is elided with `…` past ~28 chars so the panel stays narrow.

### Full popup — 3 tabs

**Status tab (default)**
- Service status (active / inactive / paused) with color dot
- Next check countdown (1m 42s) with a thin progress bar showing % through the interval
- Last checked time + last change date
- Force check button + Pause/Resume button

**Changes tab**
- List of recent changes (last 10 from `/api/history`)
- Each item: type chip (grades/absences/modules/semesters), the `summary` string, and a relative timestamp (e.g. "2h ago")
- "NEW" badge on entries with `ts` newer than `last_seen.ts`

**Grades tab**
- Current S4 snapshot from `/api/grades/S4`
- Grouped by module: module name as header, elements as rows with their latest grade values
- Color-coded: green for filled values, muted for dashes

**Footer (all tabs)**
- "Updated HH:MM" on the left
- Refresh button on the right

### Desktop notification

- **Title:** keyed off the newest entry's `type` — `"SchoolApp — grades"`, `"SchoolApp — absences"`, `"SchoolApp — modules"`, `"SchoolApp — semesters"`
- **Body:** the entry's `summary` verbatim (e.g. `"Notes mises à jour — S4"` or `"Résultat module: Algèbre 2 — RAT (9.08)"`)
- If more than one new entry since `last_seen`, body lists each summary newline-separated (max 3, then `"+ N more"`)
- Fires only on the upward edge (`new_change: true`) — not on every poll
- Uses `org.kde.notification` `Notification` component (same as claude-usage-plasmoid)
- `componentName: "plasma_workspace"`, `eventId: "notification"`

---

## Configuration

Stored via `Plasmoid.configuration` (declared in `main.xml`):

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `apiUrl` | string | `http://localhost:8787` | API base URL |
| `apiKey` | string | `""` | X-API-Key header value |
| `refreshInterval` | int | `30` | seconds between polls |
| `notifyEnabled` | bool | `true` | toggle desktop notifications |

Config page (`configGeneral.qml`): two text fields (API URL, API key) + refresh interval spinner + notify toggle.

---

## Error handling

- API unreachable → `ok: false`, `error: "offline"` → widget dims, shows error in Status tab, panel shows amber dot + `error`
- Wrong API key (401) → `error: "auth error"` → same treatment
- `/api/grades/S4` fails → Grades tab shows "No snapshot yet"
- Script crash → QML catches empty/invalid stdout, sets `errorMsg`, never crashes the widget

---

## Install / uninstall

`install.sh` runs `kpackagetool6 --install package/ --type Plasma/Applet` (or `--upgrade` if already installed).
`uninstall.sh` runs `kpackagetool6 --remove com.notadil.schoolappwatcher`.

Widget ID: `com.notadil.schoolappwatcher`

---

## Files to create

| File | Purpose |
|------|---------|
| `plasmoid/package/metadata.json` | Plugin metadata (id, name, author) |
| `plasmoid/package/contents/ui/main.qml` | Full QML widget (compact + full + notifications) |
| `plasmoid/package/contents/scripts/schoolapp_status.py` | Python backend |
| `plasmoid/package/contents/config/main.xml` | Configuration schema |
| `plasmoid/package/contents/config/config.qml` | Config page root |
| `plasmoid/package/contents/config/configGeneral.qml` | Config form UI |
| `plasmoid/install.sh` | Install/upgrade script |
| `plasmoid/uninstall.sh` | Remove script |
