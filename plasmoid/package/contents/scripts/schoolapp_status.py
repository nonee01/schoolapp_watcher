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
    if now is None:
        now = datetime.now()
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
    if now is None:
        now = datetime.now()
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


def build_output(status, history, grades, last_seen_ts, now=None):
    """Assemble the JSON payload the widget consumes."""
    if now is None:
        now = datetime.now()
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

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        _fail(str(e)[:60])
