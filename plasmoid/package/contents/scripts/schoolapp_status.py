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
