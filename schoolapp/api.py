from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request

from .presets import modules_for_semester
from .watcher import (
    SLOW_INTERVAL,
    SLOW_WINDOW,
    _all_titles,
    _compute_module_moy,
    _compute_moy,
    _history_path,
    _is_validated,
    _load_snapshot,
    _snapshot_path,
    check_once,
)

app = Flask(__name__)

WATCHER_UNIT = "schoolapp-watcher.service"
_check_lock = threading.Lock()
_POLL_INTERVAL = int(os.environ.get("WATCHER_INTERVAL", "120"))


def _auth():
    key = os.environ.get("API_KEY", "")
    if key and request.headers.get("X-API-Key") != key:
        return jsonify({"error": "Invalid API key"}), 401
    return None


def _cell(row: list[str], idx: dict[str, int], key: str) -> str:
    i = idx.get(key)
    if i is None or i >= len(row):
        return "--"
    v = row[i].strip()
    return v if v else "--"


def _systemctl(*args: str) -> str:
    out = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=15)
    return out.stdout.strip()


def _active_interval() -> int:
    hour = datetime.now().hour
    return SLOW_INTERVAL if SLOW_WINDOW[0] <= hour < SLOW_WINDOW[1] else _POLL_INTERVAL


@app.get("/api/status")
def status():
    err = _auth()
    if err:
        return err
    snap_path = _snapshot_path("S4", None)
    last_check = None
    next_check = None
    if snap_path.exists():
        mtime = snap_path.stat().st_mtime
        last_check = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
        next_check = (datetime.fromtimestamp(mtime) + timedelta(seconds=_active_interval())).isoformat(timespec="seconds")
    active = _systemctl("is-active", WATCHER_UNIT)
    return jsonify({
        "watcher": active or "unknown",
        "last_check": last_check,
        "next_check": next_check,
        "poll_interval": _active_interval(),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    })


@app.get("/api/grades/<semester>")
def grades(semester: str):
    err = _auth()
    if err:
        return err
    sem = semester.upper()
    try:
        mods = modules_for_semester(sem)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404

    snap = _load_snapshot(_snapshot_path(sem, None))
    if snap is None or "CodeElem" not in snap.headers:
        return jsonify({"error": f"No snapshot for {sem} yet"}), 404

    idx = {h: i for i, h in enumerate(snap.headers)}
    ci = idx.get("CodeElem", 0)
    by_code = {r[ci].strip(): r for r in snap.rows if len(r) > ci and r[ci].strip()}
    element_defs = {el.code.upper(): el for m in mods for el in m.elements}

    out_modules = []
    for mod in mods:
        elements = []
        for el in mod.elements:
            row = by_code.get(el.code)
            cc = _cell(row, idx, "CC") if row else "--"
            ex = _cell(row, idx, "EX") if row else "--"
            tp = _cell(row, idx, "TP") if row else "--"
            moy = _cell(row, idx, "Moy") if row else "--"
            dec = _cell(row, idx, "Dec") if row else "--"
            if moy == "--":
                moy = _compute_moy(el.code, cc, ex, tp, element_defs)
            elements.append({
                "code": el.code,
                "title": el.title,
                "cc": cc,
                "ex": ex,
                "tp": tp,
                "moy": moy,
                "estimated": moy.endswith("*"),
                "validated": _is_validated(moy) if moy != "--" else None,
                "dec": dec,
            })
        mod_moy, partial = _compute_module_moy(mod, by_code, idx, element_defs)
        out_modules.append({
            "code": mod.code,
            "title": mod.title,
            "coef": mod.coef_mod,
            "seuil": mod.seuil,
            "moy": mod_moy,
            "partial": partial,
            "validated": _is_validated(mod_moy) if mod_moy != "--" else None,
            "elements": elements,
        })
    return jsonify({"semester": sem, "modules": out_modules})


def _extras(sem: str = "S4") -> dict:
    snap = _load_snapshot(_snapshot_path(sem, None))
    if snap is None or not isinstance(snap.extras, dict):
        return {}
    return snap.extras


@app.get("/api/absences")
def absences():
    err = _auth()
    if err:
        return err
    extras = _extras()
    el_titles, _ = _all_titles()
    items = []
    for a in (extras.get("absences") or {}).values():
        items.append({
            "element": a.get("element", ""),
            "title": el_titles.get((a.get("element") or "").upper(), a.get("element", "")),
            "date": a.get("date", ""),
            "seance": a.get("seance", ""),
            "justified": a.get("justif") == "true",
            "remarks": a.get("remarks", ""),
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({"absences": items, "sanctions": extras.get("sanctions") or {}})


@app.get("/api/modules")
def official_modules():
    err = _auth()
    if err:
        return err
    extras = _extras()
    _, mod_titles = _all_titles()
    items = []
    for m in (extras.get("modules") or {}).values():
        items.append({
            "code": m.get("code", ""),
            "title": mod_titles.get((m.get("code") or "").upper(), m.get("code", "")),
            "au": m.get("au", ""),
            "moy": m.get("moy", "--"),
            "dec": m.get("dec", "--"),
        })
    items.sort(key=lambda x: (x["au"], x["code"]))
    return jsonify({"modules": items})


@app.get("/api/semesters")
def semesters():
    err = _auth()
    if err:
        return err
    extras = _extras()
    items = list((extras.get("semesters") or {}).values())
    items.sort(key=lambda x: (x.get("au", ""), x.get("sem", "")))
    return jsonify({"semesters": items})


@app.get("/api/history")
def history():
    err = _auth()
    if err:
        return err
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 1000)
    except (ValueError, TypeError):
        limit = 100
    path = _history_path("S4", None)
    entries: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    entries.reverse()
    return jsonify({"history": entries[:limit]})


@app.post("/api/check")
def force_check():
    err = _auth()
    if err:
        return err
    email = os.environ.get("SCHOOLAPP_EMAIL", "")
    password = os.environ.get("SCHOOLAPP_PASSWORD", "")
    if not email or not password:
        return jsonify({"error": "Credentials not configured"}), 503
    if not _check_lock.acquire(blocking=False):
        return jsonify({"error": "A check is already running"}), 409
    sem = request.args.get("semester", "S4").upper()
    try:
        code = check_once(
            email=email,
            password=password,
            timeout=20,
            semester=sem,
            state_file=None,
            notify_email=True,
            notify_telegram=True,
            config=None,
        )
    except Exception as exc:
        return jsonify({"error": f"Check failed: {exc}"}), 502
    finally:
        _check_lock.release()
    return jsonify({"changed": code == 1, "checked_at": datetime.now().isoformat(timespec="seconds")})


@app.post("/api/watcher/pause")
def pause_watcher():
    err = _auth()
    if err:
        return err
    _systemctl("stop", WATCHER_UNIT)
    return jsonify({"watcher": _systemctl("is-active", WATCHER_UNIT) or "inactive"})


@app.post("/api/watcher/resume")
def resume_watcher():
    err = _auth()
    if err:
        return err
    _systemctl("start", WATCHER_UNIT)
    return jsonify({"watcher": _systemctl("is-active", WATCHER_UNIT) or "unknown"})


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8787, threads=4)
