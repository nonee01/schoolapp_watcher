# SchoolApp Watcher Plasma Widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A KDE Plasma 6 panel widget that polls the running `schoolapp-api.service`, shows watcher status + the latest change in the panel, lists recent changes and current S4 grades in a popup, and fires a desktop notification when a new change appears.

**Architecture:** A stdlib-only Python backend (`schoolapp_status.py`) does all HTTP to the local API (`localhost:8787`), computes change-detection against a small cache file, and prints one JSON blob. `main.qml` runs that script every 30s via `Plasma5Support.DataSource` (executable engine), renders the compact panel + 3-tab popup, and fires `org.kde.notification` on the upward edge. All testable logic lives in Python; QML stays thin. Mirrors the user's existing `claude-usage-plasmoid`.

**Tech Stack:** QML (Plasma 6 / Qt6), Python 3 stdlib (`urllib`, `json`, `datetime`), `unittest` for tests, `kpackagetool6` for install, `xmllint` for config validation.

**Spec:** `docs/superpowers/specs/2026-06-16-schoolapp-plasmoid-design.md`

**Conventions for this plan:**
- All paths are relative to the repo root `/home/notadil/Projects/schoolapp_watcher`.
- Widget ID: `com.notadil.schoolappwatcher`.
- The API is already running; confirm with: `curl -s localhost:8787/api/status -H "X-API-Key: $(grep ^API_KEY= .env | cut -d= -f2)"`.
- Tests run with **stdlib unittest** (no pytest on this machine): `python3 -m unittest discover -s plasmoid/tests -v`.

---

### Task 1: Package skeleton + metadata.json

**Files:**
- Create: `plasmoid/package/metadata.json`
- Create (empty dirs via the files below): `plasmoid/package/contents/{ui,scripts,config}/`

- [ ] **Step 1: Create `plasmoid/package/metadata.json`**

```json
{
    "KPlugin": {
        "Id": "com.notadil.schoolappwatcher",
        "Name": "SchoolApp Watcher",
        "Description": "Watcher status, recent grade changes, and notifications from the SchoolApp watcher API",
        "Icon": "view-calendar-tasks",
        "Authors": [
            { "Name": "notadil" }
        ],
        "Category": "System Information",
        "License": "MIT",
        "Version": "1.0"
    },
    "KPackageStructure": "Plasma/Applet",
    "X-Plasma-API-Minimum-Version": "6.0"
}
```

- [ ] **Step 2: Verify the JSON parses and the id is correct**

Run:
```bash
python3 -c "import json; d=json.load(open('plasmoid/package/metadata.json')); assert d['KPlugin']['Id']=='com.notadil.schoolappwatcher'; print('metadata OK')"
```
Expected: `metadata OK`

- [ ] **Step 3: Commit**

```bash
git add plasmoid/package/metadata.json
git commit -m "feat(widget): scaffold SchoolApp plasmoid package metadata"
```

---

### Task 2: Configuration schema + config pages

The widget stores `apiUrl`, `apiKey`, `refreshInterval`, `notifyEnabled` in `Plasmoid.configuration`.

**Files:**
- Create: `plasmoid/package/contents/config/main.xml`
- Create: `plasmoid/package/contents/config/config.qml`
- Create: `plasmoid/package/contents/config/configGeneral.qml`

- [ ] **Step 1: Create `plasmoid/package/contents/config/main.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<kcfg xmlns="http://www.kde.org/standards/kcfg/1.0"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.kde.org/standards/kcfg/1.0
      http://www.kde.org/standards/kcfg/1.0/kcfg.xsd">
    <kcfgfile name=""/>
    <group name="General">
        <entry name="apiUrl" type="String">
            <label>Base URL of the SchoolApp watcher API</label>
            <default>http://localhost:8787</default>
        </entry>
        <entry name="apiKey" type="String">
            <label>X-API-Key for the watcher API</label>
            <default></default>
        </entry>
        <entry name="refreshInterval" type="Int">
            <label>Poll interval in seconds</label>
            <default>30</default>
        </entry>
        <entry name="notifyEnabled" type="Bool">
            <label>Notify on a new change</label>
            <default>true</default>
        </entry>
    </group>
</kcfg>
```

- [ ] **Step 2: Validate the XML**

Run: `xmllint --noout plasmoid/package/contents/config/main.xml && echo "main.xml well-formed"`
Expected: `main.xml well-formed`

- [ ] **Step 3: Create `plasmoid/package/contents/config/config.qml`**

```qml
import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    ConfigCategory {
        name: "General"
        icon: "configure"
        source: "configGeneral.qml"
    }
}
```

- [ ] **Step 4: Create `plasmoid/package/contents/config/configGeneral.qml`**

```qml
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: page

    property alias cfg_apiUrl: urlField.text
    property alias cfg_apiKey: keyField.text
    property alias cfg_refreshInterval: refreshSpin.value
    property alias cfg_notifyEnabled: notifyCheck.checked

    QQC2.TextField {
        id: urlField
        Kirigami.FormData.label: "API URL:"
        placeholderText: "http://localhost:8787"
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
    }

    QQC2.TextField {
        id: keyField
        Kirigami.FormData.label: "API key:"
        echoMode: TextInput.PasswordEchoOnEdit
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
    }

    QQC2.SpinBox {
        id: refreshSpin
        Kirigami.FormData.label: "Poll every:"
        from: 10
        to: 600
        stepSize: 5
        textFromValue: function(value) { return value + " s" }
        valueFromText: function(text) { return parseInt(text) }
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.CheckBox {
        id: notifyCheck
        Kirigami.FormData.label: "Notifications:"
        text: "Notify when a new change is detected"
    }
}
```

- [ ] **Step 5: Commit**

```bash
git add plasmoid/package/contents/config/
git commit -m "feat(widget): add config schema and settings page"
```

---

### Task 3: Python backend — pure helpers (TDD)

The backend's pure functions: `relative_time`, `next_check_seconds`, `annotate_history`. No network, no disk, no wall clock (injected `now`). ISO timestamps from the watcher are fixed-width `timespec="seconds"`, so lexicographic string comparison is a valid ordering.

**Files:**
- Create: `plasmoid/package/contents/scripts/schoolapp_status.py`
- Create: `plasmoid/tests/test_schoolapp_status.py`

- [ ] **Step 1: Write the failing test `plasmoid/tests/test_schoolapp_status.py`**

```python
import importlib.util
import os
import unittest
from datetime import datetime

# Load the script as a module (it lives in a non-package scripts/ dir).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "package", "contents", "scripts", "schoolapp_status.py")
_spec = importlib.util.spec_from_file_location("schoolapp_status", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestRelativeTime(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)

    def test_just_now(self):
        self.assertEqual(mod.relative_time("2026-06-16T11:59:40", self.now), "just now")

    def test_minutes(self):
        self.assertEqual(mod.relative_time("2026-06-16T11:30:00", self.now), "30m ago")

    def test_hours(self):
        self.assertEqual(mod.relative_time("2026-06-16T09:00:00", self.now), "3h ago")

    def test_days(self):
        self.assertEqual(mod.relative_time("2026-06-14T12:00:00", self.now), "2d ago")

    def test_bad_input(self):
        self.assertEqual(mod.relative_time("not-a-date", self.now), "")


class TestNextCheckSeconds(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)

    def test_future(self):
        s = mod.next_check_seconds({"next_check": "2026-06-16T12:01:30"}, self.now)
        self.assertEqual(s, 90)

    def test_past_clamps_to_zero(self):
        s = mod.next_check_seconds({"next_check": "2026-06-16T11:59:00"}, self.now)
        self.assertEqual(s, 0)

    def test_missing(self):
        self.assertEqual(mod.next_check_seconds({}, self.now), 0)


class TestAnnotateHistory(unittest.TestCase):
    HIST = [
        {"ts": "2026-06-15T23:40:24", "type": "grades", "summary": "Notes mises à jour — S4"},
        {"ts": "2026-06-15T16:41:31", "type": "modules", "summary": "Résultat module: Algèbre 2 — RAT (9.08)"},
    ]

    def test_new_entries_flagged(self):
        annotated, new_summaries = mod.annotate_history(self.HIST, "2026-06-15T20:00:00")
        self.assertTrue(annotated[0]["new"])
        self.assertFalse(annotated[1]["new"])
        self.assertEqual(new_summaries, ["Notes mises à jour — S4"])

    def test_first_run_baselines_silently(self):
        annotated, new_summaries = mod.annotate_history(self.HIST, "")
        self.assertFalse(any(a["new"] for a in annotated))
        self.assertEqual(new_summaries, [])

    def test_nothing_new(self):
        annotated, new_summaries = mod.annotate_history(self.HIST, "2026-06-15T23:40:24")
        self.assertFalse(any(a["new"] for a in annotated))
        self.assertEqual(new_summaries, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: FAIL — `FileNotFoundError` / `ModuleNotFoundError` because `schoolapp_status.py` does not exist yet.

- [ ] **Step 3: Create `plasmoid/package/contents/scripts/schoolapp_status.py` with the helpers**

```python
#!/usr/bin/env python3
"""SchoolApp Watcher widget backend.

Usage: schoolapp_status.py <api_url> <api_key> [action]
  action in {poll (default), check, pause, resume}

Prints one JSON object on stdout describing watcher status, recent changes,
the current S4 grades snapshot, and whether a new change appeared since the
last run. Network access limited to the configured API URL. Stdlib only.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

HOME = os.path.expanduser("~")
CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")),
    "schoolapp-widget")
SEEN_FILE = os.path.join(CACHE_DIR, "last_seen.json")

TYPE_ICON = {"grades": "📊", "absences": "🚫", "modules": "📋", "semesters": "🎓"}
TYPE_TITLE = {
    "grades": "SchoolApp — grades",
    "absences": "SchoolApp — absences",
    "modules": "SchoolApp — modules",
    "semesters": "SchoolApp — semesters",
}


# ----------------------------------------------------------------- pure helpers

def relative_time(ts_iso, now=None):
    """'just now' / 'Nm ago' / 'Nh ago' / 'Nd ago'. '' on bad input."""
    now = now or datetime.now()
    try:
        t = datetime.fromisoformat(ts_iso)
    except (ValueError, TypeError):
        return ""
    delta = (now - t).total_seconds()
    if delta < 0:
        delta = 0
    minutes = int(delta // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours, _ = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h ago"
    days, _ = divmod(hours, 24)
    return f"{days}d ago"


def next_check_seconds(status, now=None):
    """Seconds until status['next_check'] (ISO). 0 if missing/past/bad."""
    now = now or datetime.now()
    nc = status.get("next_check")
    if not nc:
        return 0
    try:
        t = datetime.fromisoformat(nc)
    except (ValueError, TypeError):
        return 0
    return max(0, int((t - now).total_seconds()))


def annotate_history(history, last_seen_ts):
    """Tag entries newer than last_seen_ts as new.

    Returns (annotated_list, new_summaries). With no last_seen_ts (first run)
    nothing is new — we baseline silently. ISO timestamps are fixed-width so
    string comparison orders them correctly.
    """
    annotated = []
    new_summaries = []
    for e in history:
        ts = e.get("ts", "")
        is_new = bool(last_seen_ts) and ts > last_seen_ts
        annotated.append({
            "ts": ts,
            "type": e.get("type", ""),
            "summary": e.get("summary", ""),
            "new": is_new,
        })
        if is_new:
            new_summaries.append(e.get("summary", ""))
    return annotated, new_summaries
```

- [ ] **Step 4: Run the test to verify the helpers pass**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: PASS for all `TestRelativeTime`, `TestNextCheckSeconds`, `TestAnnotateHistory` cases (11 tests).

- [ ] **Step 5: Commit**

```bash
git add plasmoid/package/contents/scripts/schoolapp_status.py plasmoid/tests/test_schoolapp_status.py
git commit -m "feat(widget): backend pure helpers with unit tests"
```

---

### Task 4: Python backend — output assembly (TDD)

`build_output` turns injected `status`, `history`, `grades`, `last_seen_ts`, and `now` into the final dict the QML consumes. No I/O.

**Files:**
- Modify: `plasmoid/package/contents/scripts/schoolapp_status.py`
- Modify: `plasmoid/tests/test_schoolapp_status.py`

- [ ] **Step 1: Add the failing test (append to `plasmoid/tests/test_schoolapp_status.py`, before the `if __name__` line)**

```python
class TestBuildOutput(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 16, 12, 0, 0)
        self.status = {
            "watcher": "active",
            "last_check": "2026-06-16T11:59:00",
            "next_check": "2026-06-16T12:01:30",
            "poll_interval": 120,
        }
        self.history = [
            {"ts": "2026-06-16T11:58:00", "type": "grades", "summary": "Notes mises à jour — S4"},
            {"ts": "2026-06-15T16:41:31", "type": "modules", "summary": "Résultat module: Algèbre 2 — RAT (9.08)"},
        ]
        self.grades = {"semester": "S4", "modules": [
            {"code": "API45", "title": "Analyse", "moy": "12.5", "validated": True,
             "elements": [{"code": "API451", "cc": "14.5", "ex": "--", "tp": "--", "moy": "14.5*"}]},
        ]}

    def test_shape_and_new_change(self):
        out = mod.build_output(self.status, self.history, self.grades,
                               last_seen_ts="2026-06-16T11:00:00", now=self.now)
        self.assertTrue(out["ok"])
        self.assertEqual(out["watcher"], "active")
        self.assertEqual(out["next_check_s"], 90)
        self.assertEqual(out["poll_interval"], 120)
        self.assertEqual(out["latest_change_type"], "grades")
        self.assertEqual(out["latest_change_summary"], "Notes mises à jour — S4")
        self.assertTrue(out["new_change"])
        self.assertEqual(out["new_summaries"], ["Notes mises à jour — S4"])
        self.assertEqual(out["history"][0]["new"], True)
        self.assertEqual(out["history"][1]["new"], False)
        self.assertEqual(out["grades"]["modules"][0]["code"], "API45")
        self.assertEqual(out["error"], "")

    def test_empty_history(self):
        out = mod.build_output(self.status, [], self.grades,
                               last_seen_ts="2026-06-16T11:00:00", now=self.now)
        self.assertFalse(out["new_change"])
        self.assertEqual(out["latest_change_summary"], "")
        self.assertEqual(out["latest_change_type"], "")
        self.assertEqual(out["history"], [])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest plasmoid.tests.test_schoolapp_status.TestBuildOutput -v` (or the discover command)
Expected: FAIL — `AttributeError: module 'schoolapp_status' has no attribute 'build_output'`.

- [ ] **Step 3: Add `build_output` to `schoolapp_status.py` (after `annotate_history`)**

```python
def build_output(status, history, grades, last_seen_ts, now=None):
    """Assemble the JSON payload the widget consumes."""
    now = now or datetime.now()
    annotated, new_summaries = annotate_history(history, last_seen_ts)
    latest = annotated[0] if annotated else None
    return {
        "ok": True,
        "watcher": status.get("watcher", "unknown"),
        "next_check_s": next_check_seconds(status, now),
        "poll_interval": status.get("poll_interval", 0),
        "last_check": status.get("last_check"),
        "last_change": latest["ts"] if latest else None,
        "latest_change_type": latest["type"] if latest else "",
        "latest_change_summary": latest["summary"] if latest else "",
        "history": annotated,
        "grades": grades or {},
        "new_change": bool(new_summaries),
        "new_summaries": new_summaries,
        "error": "",
        "updated": now.strftime("%H:%M"),
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: PASS (13 tests total).

- [ ] **Step 5: Commit**

```bash
git add plasmoid/package/contents/scripts/schoolapp_status.py plasmoid/tests/test_schoolapp_status.py
git commit -m "feat(widget): backend output assembly with tests"
```

---

### Task 5: Python backend — network, cache, action POST, main() (TDD)

Adds the only impure parts: `http_json` (GET/POST against the API), `load_seen`/`save_seen`, and `main()`. `main()` performs an optional action POST, GETs status/history/grades, assembles output, persists the newest `ts` as the new `last_seen`, and prints. On a failed status fetch it emits `ok: false` with an error and never raises.

**Files:**
- Modify: `plasmoid/package/contents/scripts/schoolapp_status.py`
- Modify: `plasmoid/tests/test_schoolapp_status.py`

- [ ] **Step 1: Add the failing integration test (append before `if __name__`)**

```python
import io
import json as _json
import tempfile
from contextlib import redirect_stdout


class _FakeResp:
    def __init__(self, payload, code=200):
        self._body = _json.dumps(payload).encode()
        self.code = code

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["XDG_CACHE_HOME"] = self.tmp
        # Recompute cache paths inside the module to honor the temp dir.
        mod.CACHE_DIR = os.path.join(self.tmp, "schoolapp-widget")
        mod.SEEN_FILE = os.path.join(mod.CACHE_DIR, "last_seen.json")
        self.routes = {
            "/api/status": {"watcher": "active", "last_check": "2026-06-16T11:59:00",
                            "next_check": "2026-06-16T12:30:00", "poll_interval": 120},
            "/api/history": {"history": [
                {"ts": "2026-06-16T11:58:00", "type": "grades", "summary": "Notes mises à jour — S4"}]},
            "/api/grades/S4": {"semester": "S4", "modules": []},
        }

    def _fake_urlopen(self, req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        for path, payload in self.routes.items():
            if url.endswith(path):
                return _FakeResp(payload)
        return _FakeResp({}, code=404)

    def _run(self, action="poll"):
        mod.urllib.request.urlopen = self._fake_urlopen
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.main(["http://localhost:8787", "k", action])
        return _json.loads(buf.getvalue())

    def test_first_run_baselines_then_detects(self):
        out1 = self._run()
        self.assertTrue(out1["ok"])
        self.assertFalse(out1["new_change"])  # first run baselines silently
        # Second run with an older last_seen already saved: still nothing new.
        out2 = self._run()
        self.assertFalse(out2["new_change"])

    def test_new_change_after_newer_entry(self):
        self._run()  # baseline at 11:58
        self.routes["/api/history"]["history"].insert(
            0, {"ts": "2026-06-16T12:05:00", "type": "modules", "summary": "Résultat module: X"})
        out = self._run()
        self.assertTrue(out["new_change"])
        self.assertEqual(out["new_summaries"], ["Résultat module: X"])

    def test_status_failure_is_graceful(self):
        def boom(req, timeout=0):
            raise urllib.error.URLError("offline")
        mod.urllib.request.urlopen = boom
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.main(["http://localhost:8787", "k", "poll"])
        out = _json.loads(buf.getvalue())
        self.assertFalse(out["ok"])
        self.assertTrue(out["error"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: FAIL — `AttributeError: module 'schoolapp_status' has no attribute 'main'`.

- [ ] **Step 3: Add network, cache, and main() to `schoolapp_status.py`**

```python
# ----------------------------------------------------------------- io

def http_json(url, api_key, method="GET", timeout=8):
    """One request. Returns (data, None) or (None, error-string)."""
    req = urllib.request.Request(url, method=method)
    if api_key:
        req.add_header("X-API-Key", api_key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None, "auth error (check API key)"
        return None, f"http {e.code}"
    except urllib.error.URLError:
        return None, "offline (API unreachable)"
    except Exception as e:  # noqa: BLE001 - never crash the widget
        return None, str(e)[:60]


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh).get("ts", "")
    except Exception:
        return ""


def save_seen(ts):
    if not ts:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = SEEN_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"ts": ts}, fh)
        os.replace(tmp, SEEN_FILE)
    except Exception:
        pass


ACTION_ENDPOINT = {
    "check": ("/api/check", "POST"),
    "pause": ("/api/watcher/pause", "POST"),
    "resume": ("/api/watcher/resume", "POST"),
}


def _fail(error):
    print(json.dumps({
        "ok": False, "watcher": "unknown", "next_check_s": 0, "poll_interval": 0,
        "last_check": None, "last_change": None, "latest_change_type": "",
        "latest_change_summary": "", "history": [], "grades": {},
        "new_change": False, "new_summaries": [], "error": error,
        "updated": datetime.now().strftime("%H:%M"),
    }))


def main(argv):
    if len(argv) < 2:
        _fail("usage: schoolapp_status.py <api_url> <api_key> [action]")
        return
    base = argv[0].rstrip("/")
    key = argv[1]
    action = argv[2] if len(argv) > 2 else "poll"

    # Optional action POST first; ignore its body, then fall through to poll.
    if action in ACTION_ENDPOINT:
        path, method = ACTION_ENDPOINT[action]
        http_json(base + path, key, method=method, timeout=25)

    status, err = http_json(base + "/api/status", key)
    if err:
        _fail(err)
        return
    history_resp, _ = http_json(base + "/api/history?limit=10", key)
    grades, _ = http_json(base + "/api/grades/S4", key)
    history = (history_resp or {}).get("history", [])

    last_seen = load_seen()
    out = build_output(status, history, grades or {}, last_seen)
    # Persist the newest seen ts so the next poll treats current entries as seen.
    if out["history"]:
        save_seen(out["history"][0]["ts"])
    print(json.dumps(out))
```

- [ ] **Step 4: Add the CLI entry point at the very end of `schoolapp_status.py`**

```python
if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        _fail(str(e)[:60])
```

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: PASS (16 tests total).

- [ ] **Step 6: Smoke-test against the live API**

Run:
```bash
python3 plasmoid/package/contents/scripts/schoolapp_status.py \
  http://localhost:8787 "$(grep ^API_KEY= .env | cut -d= -f2)" poll | python3 -m json.tool
```
Expected: a JSON object with `"ok": true`, a `watcher` value, `next_check_s` ≥ 0, and a populated `history` array. (First run shows `new_change: false`.)

- [ ] **Step 7: Commit**

```bash
git add plasmoid/package/contents/scripts/schoolapp_status.py plasmoid/tests/test_schoolapp_status.py
git commit -m "feat(widget): backend network, cache, actions, and main()"
```

---

### Task 6: QML — compact (panel) representation

Creates `main.qml` with the data plumbing (`DataSource` + parse), all root properties, the 1-second countdown ticker, and the compact panel with its 4 states. The `fullRepresentation` is a temporary placeholder replaced in Task 7.

**Files:**
- Create: `plasmoid/package/contents/ui/main.qml`

- [ ] **Step 1: Create `plasmoid/package/contents/ui/main.qml`**

```qml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.notification

PlasmoidItem {
    id: root

    readonly property string scriptPath: Qt.resolvedUrl("../scripts/schoolapp_status.py").toString().replace("file://", "")

    property bool ok: false
    property bool loaded: false
    property string watcher: "unknown"     // active | inactive | paused | unknown
    property int nextCheckS: 0
    property int pollInterval: 0
    property string latestType: ""
    property string latestSummary: ""
    property var history: []
    property var gradeModules: []
    property string updated: "—"
    property string errorMsg: ""

    // Notification edge tracking: remember the newest ts we've already alerted on.
    property string lastNotifiedTs: ""

    readonly property var typeIcon: ({
        "grades": "📊", "absences": "🚫", "modules": "📋", "semesters": "🎓"
    })

    Notification {
        id: changeNotification
        componentName: "plasma_workspace"
        eventId: "notification"
        iconName: "view-calendar-tasks"
        title: "SchoolApp Watcher"
        flags: Notification.Persistent
    }

    function titleForType(t) {
        if (t === "grades") return "SchoolApp — grades"
        if (t === "absences") return "SchoolApp — absences"
        if (t === "modules") return "SchoolApp — modules"
        if (t === "semesters") return "SchoolApp — semesters"
        return "SchoolApp Watcher"
    }

    function maybeNotify(j) {
        if (!Plasmoid.configuration.notifyEnabled) return
        if (!j.new_change || !j.new_summaries || j.new_summaries.length === 0) return
        var newestTs = j.history && j.history.length > 0 ? j.history[0].ts : ""
        if (newestTs === "" || newestTs === lastNotifiedTs) return  // already alerted
        var lines = j.new_summaries.slice(0, 3)
        var extra = j.new_summaries.length - lines.length
        var body = lines.join("\n")
        if (extra > 0) body += "\n+ " + extra + " more"
        changeNotification.title = titleForType(j.latest_change_type)
        changeNotification.text = body
        changeNotification.sendEvent()
        lastNotifiedTs = newestTs
    }

    function statusColor() {
        if (!ok) return Kirigami.Theme.neutralTextColor
        if (watcher === "active") return Kirigami.Theme.positiveTextColor
        if (watcher === "paused") return Kirigami.Theme.neutralTextColor
        return Kirigami.Theme.negativeTextColor
    }

    function fmtCountdown(s) {
        if (s <= 0) return "now"
        var m = Math.floor(s / 60)
        var sec = s % 60
        if (m <= 0) return sec + "s"
        return m + "m " + (sec < 10 ? "0" : "") + sec + "s"
    }

    function elide(str, n) {
        if (!str) return ""
        return str.length > n ? str.substring(0, n - 1) + "…" : str
    }

    // Compact panel summary text.
    readonly property string compactText: {
        if (!loaded) return "…"
        if (!ok) return "error"
        if (watcher === "inactive" || watcher === "unknown") return "stopped"
        if (watcher === "paused") return "paused"
        if (latestSummary.length === 0) return "No changes"
        var ic = typeIcon[latestType] || ""
        return (ic ? ic + " " : "") + elide(latestSummary, 28)
    }

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source)
            root.loaded = true
            var out = (data["stdout"] || "").trim()
            if (out.length === 0) {
                root.ok = false
                root.errorMsg = (data["stderr"] || "no output").trim().substring(0, 60)
                return
            }
            try {
                var j = JSON.parse(out)
                root.ok = j.ok === true
                root.watcher = j.watcher || "unknown"
                root.nextCheckS = j.next_check_s || 0
                root.pollInterval = j.poll_interval || 0
                root.latestType = j.latest_change_type || ""
                root.latestSummary = j.latest_change_summary || ""
                root.history = j.history || []
                root.gradeModules = (j.grades && j.grades.modules) ? j.grades.modules : []
                root.updated = j.updated || "—"
                root.errorMsg = j.error || ""
                if (root.ok) root.maybeNotify(j)
            } catch (e) {
                root.ok = false
                root.errorMsg = "parse error"
            }
        }
        function poll() { connectSource("python3 '" + root.scriptPath + "' '"
            + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "'") }
        function action(name) { connectSource("python3 '" + root.scriptPath + "' '"
            + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "' " + name) }
    }

    // Poll timer (network).
    Timer {
        interval: Math.max(10, Plasmoid.configuration.refreshInterval) * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: exec.poll()
    }

    // 1s local countdown ticker (no network).
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: if (root.nextCheckS > 0) root.nextCheckS -= 1
    }

    Plasmoid.icon: "view-calendar-tasks"
    toolTipMainText: "SchoolApp Watcher"
    toolTipSubText: {
        if (!loaded) return "Loading…"
        if (!ok) return "⚠ " + errorMsg
        var s = "Watcher: " + watcher + "\n"
        if (latestSummary.length > 0) s += "Latest: " + latestSummary + "\n"
        return s + "Next check " + fmtCountdown(nextCheckS)
    }

    compactRepresentation: MouseArea {
        id: compact
        property bool horizontal: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        Layout.minimumWidth: horizontal ? row.implicitWidth + Kirigami.Units.smallSpacing * 2 : 0
        Layout.minimumHeight: horizontal ? 0 : row.implicitHeight + Kirigami.Units.smallSpacing * 2
        acceptedButtons: Qt.LeftButton
        onClicked: root.expanded = !root.expanded

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                width: Kirigami.Units.iconSizes.small * 0.5
                height: width
                radius: width / 2
                color: root.statusColor()
                Layout.alignment: Qt.AlignVCenter
            }
            PlasmaComponents3.Label {
                text: root.compactText
                font.bold: true
                color: root.ok ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
            }
        }
    }

    // Replaced with the full 3-tab popup in Task 7.
    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 16
        PlasmaComponents3.Label { anchors.centerIn: parent; text: "popup placeholder" }
    }
}
```

- [ ] **Step 2: Sanity-check the script path resolves and JSON keys match**

Verify by eye that every `j.<key>` read in `onNewData` exists in the Task 4/5 `build_output` output: `ok, watcher, next_check_s, poll_interval, latest_change_type, latest_change_summary, history, grades.modules, updated, error, new_change, new_summaries`. All present.

- [ ] **Step 3: Commit**

```bash
git add plasmoid/package/contents/ui/main.qml
git commit -m "feat(widget): QML data plumbing and compact panel"
```

---

### Task 7: QML — full popup (3 tabs), footer, notification wiring, action buttons

Replaces the placeholder `fullRepresentation` with the Status / Changes / Grades tabs, a footer, and Force-check / Pause-Resume buttons that call `exec.action(...)`.

**Files:**
- Modify: `plasmoid/package/contents/ui/main.qml`

- [ ] **Step 1: Replace the placeholder `fullRepresentation` block**

Find this exact block (created in Task 6) and replace the whole of it:

```qml
    // Replaced with the full 3-tab popup in Task 7.
    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 16
        PlasmaComponents3.Label { anchors.centerIn: parent; text: "popup placeholder" }
    }
```

Replace it with:

```qml
    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 18
        Layout.preferredWidth: Kirigami.Units.gridUnit * 20
        Layout.preferredHeight: Kirigami.Units.gridUnit * 22

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            // Header
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    width: Kirigami.Units.iconSizes.small * 0.6; height: width; radius: width / 2
                    color: root.statusColor()
                }
                Kirigami.Heading { text: "SchoolApp Watcher"; level: 3; Layout.fillWidth: true }
                PlasmaComponents3.Label {
                    text: root.ok ? "live" : "offline"
                    opacity: 0.6
                    color: root.ok ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            QQC2.TabBar {
                id: tabBar
                Layout.fillWidth: true
                QQC2.TabButton { text: "Status" }
                QQC2.TabButton { text: "Changes" }
                QQC2.TabButton { text: "Grades" }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabBar.currentIndex

                // ---- STATUS TAB ----
                ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Service"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label { text: root.watcher; font.bold: true; color: root.statusColor() }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Next check"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label { text: root.fmtCountdown(root.nextCheckS); font.bold: true }
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0; to: 1
                        value: root.pollInterval > 0
                            ? (1 - Math.min(1, root.nextCheckS / root.pollInterval)) : 0
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Last change"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label {
                            text: root.history.length > 0 ? root.relativeFor(root.history[0].ts) : "—"
                        }
                    }
                    Item { Layout.fillHeight: true }
                    PlasmaComponents3.Label {
                        visible: !root.ok
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        color: Kirigami.Theme.neutralTextColor
                        text: "⚠ " + root.errorMsg
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Button {
                            text: "Force check"; icon.name: "view-refresh"
                            onClicked: exec.action("check")
                        }
                        PlasmaComponents3.Button {
                            text: root.watcher === "paused" || root.watcher === "inactive" ? "Resume" : "Pause"
                            icon.name: root.watcher === "paused" || root.watcher === "inactive"
                                ? "media-playback-start" : "media-playback-pause"
                            onClicked: exec.action(
                                (root.watcher === "paused" || root.watcher === "inactive") ? "resume" : "pause")
                        }
                    }
                }

                // ---- CHANGES TAB ----
                QQC2.ScrollView {
                    clip: true
                    ListView {
                        model: root.history
                        spacing: Kirigami.Units.smallSpacing
                        delegate: RowLayout {
                            required property var modelData
                            width: ListView.view ? ListView.view.width : implicitWidth
                            PlasmaComponents3.Label {
                                text: root.typeIcon[modelData.type] || "•"
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                PlasmaComponents3.Label {
                                    text: modelData.summary
                                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                                    font.bold: modelData.new === true
                                }
                                PlasmaComponents3.Label {
                                    text: root.relativeFor(modelData.ts)
                                    opacity: 0.6; font.pointSize: Kirigami.Theme.smallFont.pointSize
                                }
                            }
                            PlasmaComponents3.Label {
                                visible: modelData.new === true
                                text: "NEW"
                                color: Kirigami.Theme.highlightColor
                                font.bold: true; font.pointSize: Kirigami.Theme.smallFont.pointSize
                            }
                        }
                    }
                }

                // ---- GRADES TAB ----
                QQC2.ScrollView {
                    clip: true
                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: root.gradeModules
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 1
                                PlasmaComponents3.Label {
                                    text: (modelData.code || "") + " — " + (modelData.title || "")
                                    font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight
                                }
                                Repeater {
                                    model: modelData.elements || []
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        PlasmaComponents3.Label {
                                            text: modelData.code; opacity: 0.8; Layout.fillWidth: true
                                        }
                                        PlasmaComponents3.Label {
                                            text: modelData.moy && modelData.moy !== "--" ? modelData.moy : "—"
                                            color: (modelData.moy && modelData.moy !== "--")
                                                ? Kirigami.Theme.positiveTextColor
                                                : Kirigami.Theme.disabledTextColor
                                            font.bold: true
                                        }
                                    }
                                }
                            }
                        }
                        PlasmaComponents3.Label {
                            visible: root.gradeModules.length === 0
                            text: "No snapshot yet"; opacity: 0.6
                        }
                    }
                }
            }

            // Footer
            Kirigami.Separator { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents3.Label {
                    text: "Updated " + root.updated; opacity: 0.6
                    font.pointSize: Kirigami.Theme.smallFont.pointSize; Layout.fillWidth: true
                }
                PlasmaComponents3.Button {
                    text: "Refresh"; icon.name: "view-refresh"; onClicked: exec.poll()
                }
            }
        }
    }
```

- [ ] **Step 2: Add the `relativeFor` helper next to the other root functions (after `elide`)**

The Changes tab and Status tab call `root.relativeFor(ts)`. QML can't reuse the Python `relative_time`, so add a small JS twin:

```qml
    function relativeFor(tsIso) {
        if (!tsIso) return ""
        var t = new Date(tsIso)
        if (isNaN(t.getTime())) return ""
        var mins = Math.floor((Date.now() - t.getTime()) / 60000)
        if (mins < 1) return "just now"
        if (mins < 60) return mins + "m ago"
        var h = Math.floor(mins / 60)
        if (h < 24) return h + "h ago"
        return Math.floor(h / 24) + "d ago"
    }
```

- [ ] **Step 3: Commit**

```bash
git add plasmoid/package/contents/ui/main.qml
git commit -m "feat(widget): full 3-tab popup, notifications, and actions"
```

---

### Task 8: install / uninstall scripts + README

**Files:**
- Create: `plasmoid/install.sh`
- Create: `plasmoid/uninstall.sh`
- Create: `plasmoid/README.md`

- [ ] **Step 1: Create `plasmoid/install.sh`**

```bash
#!/usr/bin/env bash
# Install or upgrade the SchoolApp Watcher plasmoid.
set -euo pipefail

ID="com.notadil.schoolappwatcher"
PKG="$(cd "$(dirname "$0")" && pwd)/package"

if ! command -v kpackagetool6 >/dev/null 2>&1; then
    echo "error: kpackagetool6 not found — this needs KDE Plasma 6." >&2
    exit 1
fi

if kpackagetool6 --type Plasma/Applet --show "$ID" >/dev/null 2>&1; then
    echo "Upgrading $ID ..."
    kpackagetool6 --type Plasma/Applet --upgrade "$PKG"
else
    echo "Installing $ID ..."
    kpackagetool6 --type Plasma/Applet --install "$PKG"
fi

echo
echo "Done. Add it via: right-click panel -> Add Widgets -> \"SchoolApp Watcher\""
echo "Then open its settings and set the API URL + API key."
echo "If an existing copy doesn't refresh, restart Plasma:"
echo "  kquitapp6 plasmashell && setsid kstart plasmashell"
```

- [ ] **Step 2: Create `plasmoid/uninstall.sh`**

```bash
#!/usr/bin/env bash
# Remove the SchoolApp Watcher plasmoid.
set -euo pipefail
ID="com.notadil.schoolappwatcher"
kpackagetool6 --type Plasma/Applet --remove "$ID"
echo "Removed $ID. Restart Plasma if it's still in a panel:"
echo "  kquitapp6 plasmashell && setsid kstart plasmashell"
```

- [ ] **Step 3: Create `plasmoid/README.md`**

```markdown
# SchoolApp Watcher — KDE Plasma Widget

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

Then right-click the panel → Add Widgets → "SchoolApp Watcher". Open its
settings and set:

- **API URL** — default `http://localhost:8787`
- **API key** — the `API_KEY` from the watcher's `.env`

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
```

- [ ] **Step 4: Make scripts executable and verify bash syntax**

Run:
```bash
chmod +x plasmoid/install.sh plasmoid/uninstall.sh
bash -n plasmoid/install.sh && bash -n plasmoid/uninstall.sh && echo "scripts OK"
```
Expected: `scripts OK`

- [ ] **Step 5: Commit**

```bash
git add plasmoid/install.sh plasmoid/uninstall.sh plasmoid/README.md
git commit -m "feat(widget): install/uninstall scripts and README"
```

---

### Task 9: Live install + smoke test (manual verification)

No QML linter or `plasmoidviewer` is available on this machine, so the widget is verified by installing it against the live API and observing it. The API is already running.

- [ ] **Step 1: Run the full Python suite once more**

Run: `python3 -m unittest discover -s plasmoid/tests -v`
Expected: PASS (16 tests).

- [ ] **Step 2: Install the package**

Run: `cd plasmoid && ./install.sh`
Expected: `Installing com.notadil.schoolappwatcher ...` followed by kpackagetool success output (no errors).

- [ ] **Step 3: Add the widget to the panel and confirm visually**

Add via right-click panel → Add Widgets → "SchoolApp Watcher" (or run the `addWidget` qdbus line printed by install.sh). Open its settings, set the API URL and API key from `.env`.

Confirm, in order:
- Panel shows a green dot + a change summary (e.g. `📊 Notes mises à jour — S4`) within ~30s.
- The countdown in the popup's Status tab ticks down each second and the progress bar advances.
- The Changes tab lists recent entries with relative timestamps.
- The Grades tab shows S4 modules with their element averages.
- Clicking **Force check** triggers a check (panel/`Updated` time refreshes); **Pause** flips the service to `paused` (red/neutral dot) and the button becomes **Resume**.

- [ ] **Step 4: Verify a notification fires on a real change**

With the widget running, force a state where a new history entry appears (either wait for a real change, or append a synthetic newest line to confirm wiring):
```bash
printf '%s\n' '{"ts": "'"$(date +%Y-%m-%dT%H:%M:%S)"'", "type": "grades", "semester": "S4", "summary": "TEST — widget notification check"}' >> ~/.local/state/schoolapp/changes.jsonl
```
Within one poll cycle (~30s) a desktop notification titled "SchoolApp — grades" with body "TEST — widget notification check" should appear, and the entry should show a **NEW** badge in the Changes tab.

Then remove the synthetic line so it doesn't pollute history:
```bash
sed -i '$d' ~/.local/state/schoolapp/changes.jsonl
```
(Verify the last line is the synthetic TEST line before deleting: `tail -1 ~/.local/state/schoolapp/changes.jsonl`.)

- [ ] **Step 5: Final commit (if any tweaks were needed during smoke test)**

```bash
git add -A plasmoid/
git commit -m "fix(widget): adjustments from live smoke test" || echo "nothing to commit"
```

---

## Self-Review Notes

- **Spec coverage:** compact 4-state panel (Task 6) ✓; 3-tab popup Status/Changes/Grades (Task 7) ✓; notification on upward edge with type-titled body (Tasks 6–7) ✓; config apiUrl/apiKey/refreshInterval/notifyEnabled (Task 2) ✓; force-check + pause/resume (Task 7, via script actions in Task 5) ✓; caching/change-detection in `~/.cache/schoolapp-widget/last_seen.json` (Task 5) ✓; error handling offline/401/no-snapshot (Tasks 5–7) ✓; install/uninstall (Task 8) ✓.
- **Type consistency:** the script output keys (`ok, watcher, next_check_s, poll_interval, last_check, last_change, latest_change_type, latest_change_summary, history[{ts,type,summary,new}], grades{modules[...]}, new_change, new_summaries, error, updated`) are produced in `build_output` (Task 4) / `_fail` (Task 5) and every one is consumed by the QML `onNewData` (Task 6) and popup (Task 7). `exec.poll()` and `exec.action(name)` are defined in Task 6 and called in Task 7.
- **Decision — relative time in two places:** Python `relative_time` (tested) is used for any server-side formatting; QML `relativeFor` is a deliberate small JS twin because QML can't call the Python function and the values must re-tick live as the popup stays open. Both follow the same just-now/m/h/d scheme.
- **Decision — no QML unit tests:** `qmllint`/`plasmoidviewer` aren't installed; all branching logic lives in the TDD'd Python backend, and the QML is verified live in Task 9.
