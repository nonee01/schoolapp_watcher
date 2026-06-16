# SchoolApp Watcher - KDE Plasma Widget

A Plasma 6 panel widget for the SchoolApp watcher. Shows watcher status and the
latest change in the panel, lists recent changes and current S4 grades in a
popup, and raises a desktop notification when a new change is detected.

## Requirements

- KDE Plasma 6 (`kpackagetool6`)
- The `schoolapp-api.service` running locally (default `http://localhost:8787`)
- Python 3 (stdlib only)

## Install

```bash
./install.sh
```

Then right-click the panel -> Add Widgets -> "SchoolApp Watcher". Open its
settings and set:

- **API URL** - default `http://localhost:8787`
- **API key** - the `API_KEY` from the watcher's `.env`

## How it works

`contents/scripts/schoolapp_status.py <url> <key> [action]` does all HTTP to the
API and prints one JSON blob; `contents/ui/main.qml` runs it every 30s, renders
the panel + popup, and fires a notification on the upward edge of a new change.
Change detection is cached in `~/.cache/schoolapp-widget/last_seen.json`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Uninstall

```bash
./uninstall.sh
```
