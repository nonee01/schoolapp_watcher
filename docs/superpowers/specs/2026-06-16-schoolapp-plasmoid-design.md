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
  "last_change": "2026-06-14T03:12:00",
  "latest_change_summary": "API451 CC  — → 14.5",
  "latest_change_label": "API451 · CC updated",
  "latest_change_module": "Analyse & Probabilités",
  "history": [
    { "ts": "...", "summary": "API451 CC  — → 14.5", "label": "API451 · CC updated", "module": "Analyse & Probabilités" }
  ],
  "new_change": false,
  "error": "",
  "updated": "14:32"
}
```

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
| Has any history | green dot + grade pill showing most recent change (`API451 ↑14.5`) |
| No history yet | green dot + `No changes` (muted) |
| Service stopped | red dot + `stopped` |
| Manually paused | amber dot + `paused` |
| API error | amber dot + `error` |

The compact view always shows the most recent entry from `/api/history` (if any). There is no time-based reset — the pill simply reflects the latest known change at all times.

### Full popup — 3 tabs

**Status tab (default)**
- Service status (active / inactive / paused) with color dot
- Next check countdown (1m 42s) with a thin progress bar showing % through the interval
- Last checked time + last change date
- Force check button + Pause/Resume button

**Changes tab**
- List of recent changes (last 10 from `/api/history`)
- Each item: module name, element code, field (CC/EX/TP), old → new value, timestamp
- "NEW" badge on entries detected since last seen

**Grades tab**
- Current S4 snapshot from `/api/grades/S4`
- Grouped by module: module name as header, elements as rows with their latest grade values
- Color-coded: green for filled values, muted for dashes

**Footer (all tabs)**
- "Updated HH:MM" on the left
- Refresh button on the right

### Desktop notification

- **Title:** `"API451 · CC updated"` (first changed element)
- **Body:** `"— → 14.5 · Analyse & Probabilités · Jun 14 03:12"`
- If multiple changes in one batch: body lists all, newline-separated (max 3, then "+ N more")
- Fires only on upward edge (`new_change: true`) — not on every poll
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
