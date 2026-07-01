---
name: schoolapp-change-detection
description: Use when working on the watcher's snapshot, diff, or notification logic — how snapshots are stored and fingerprinted, how changes become diff cards, and how email/Telegram alerts are emitted.
---

# SchoolApp Change Detection & Notifications

## Overview

The watcher loop: fetch → build a `Snapshot` → compare its fingerprint to the cached
snapshot → if changed, render diff cards + notify → save the new snapshot → append one
line to `changes.jsonl`. The user's rule is **notify on every change** to per-student
resources.

## Storage (verified)

Base `$XDG_STATE_HOME/schoolapp/` (default `~/.local/state/schoolapp/`):

- `{semester.lower()}_snapshot.json` (e.g. `s4_snapshot.json`) — `_snapshot_path()`
- `changes.jsonl` — append-only history — `_history_path()` / `_append_history()`

```python
@dataclass
class Snapshot:
    headers: list[str]
    rows: list[list[str]]
    fingerprint: str
    extras: dict | None = None     # absences / sanctions / modules / semesters blobs
```

`_save_snapshot` writes atomically (`.tmp` + `os.replace`) — a crash can't corrupt the
cache. `_load_snapshot` returns `None` when the file is absent.

## Detecting change

`_fingerprint` = SHA over `json.dumps({headers, rows}, sort_keys=True, ensure_ascii=False)`.
Change = fingerprint differs from the cached one. The `extras` blobs are diffed separately
by the card builders below.

## Diffing → cards

Each diff function returns `(html_cards, telegram_text)`:

- `_diff_absence_cards(old_log, new_log, old_sanc, new_sanc, element_titles)`
- `_diff_module_cards(old_mods, new_mods, module_titles)`
- `_diff_semester_cards(old_sems, new_sems)`

**New resource types must follow the same `(cards, telegram_text)` contract** so the
existing render/notify path stays unchanged.

## Notifying

```python
send_email(subject, body, *, config=None, html=None)   # SMTP_HOST/PORT/USERNAME/PASSWORD/FROM/TO
send_telegram(message, *, config=None)                 # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
```

`check_once(...) -> int` returns **`1` when something changed**, else `0`. Watcher
health/recovery alerts go through `_try_notify(...)`. Reduced polling window:
`SLOW_WINDOW = (4, 6)` local hours at `SLOW_INTERVAL = 1800`s.

## Rules & gotchas

- **Notify on every change** for per-student resources. The **institution catalog** is the
  exception: emit **one change-summary per crawl** (added/removed/modified), not a card per
  cell (spec §9).
- **None means fetch-failed**, not "data cleared." Carry the previous cached value forward
  and do **not** emit a false "removed" notification (the `_fetch_extras` pattern).
- **No baseline → no alert.** The first-ever snapshot (cached was `None`) is stored
  silently; you can't diff against nothing.
- Append **exactly one** typed entry to `changes.jsonl` per detected change.

**Source of truth:** `schoolapp/watcher.py` (`Snapshot`, `_fingerprint`, `_save_snapshot`,
`_diff_*_cards`, `check_once`), `schoolapp/emailer.py`, `schoolapp/telegram_notifier.py`;
design spec §9.
