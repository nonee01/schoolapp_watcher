from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from . import store
from .presets import available_semesters, modules_for_semester
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


def _current_semester() -> str:
    """The semester the watcher most recently wrote a snapshot for.

    These endpoints used to name "S4" outright, so the day the student moved
    up a year /api/status started reporting the age of a file nothing writes
    any more, and /api/check refetched last year on demand.
    """
    known = available_semesters()
    newest, newest_mtime = (known[-1] if known else "S1"), -1.0
    for sem in known:
        path = _snapshot_path(sem, None)
        if path.exists() and path.stat().st_mtime > newest_mtime:
            newest, newest_mtime = sem, path.stat().st_mtime
    return newest


@app.get("/api/status")
def status():
    err = _auth()
    if err:
        return err
    snap_path = _snapshot_path(_current_semester(), None)
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
        # additive (spec §8.1): per-resource freshness map from the store
        "resources": store.freshness(
            ["student/all", *store.RESOURCE_FILES.values(), "catalog/modules", "catalog/filieres"]),
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


def _extras(sem: str | None = None) -> dict:
    snap = _load_snapshot(_snapshot_path(sem or _current_semester(), None))
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
    path = _history_path(_current_semester(), None)
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
    sem = request.args.get("semester", _current_semester()).upper()
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


# ── library-store endpoints (spec §8.1) - all additive, all cache-served ──────

def _from_store(name: str, key: str, wrap=lambda d: d):
    """Standard read: 401 via _auth, 404 when the envelope isn't cached yet."""
    err = _auth()
    if err:
        return err
    env = store.load_resource(name)
    if env is None:
        return jsonify({"error": f"No cached {name} yet - run the watcher or `schoolapp fetch-all`"}), 404
    return jsonify({key: wrap(env["data"]), "fetched_at": env.get("fetched_at")})


@app.get("/api/profile")
def profile():
    return _from_store("student/profile", "profile")


@app.get("/api/years")
def years():
    return _from_store("student/years", "years")


@app.get("/api/courses")
def courses():
    return _from_store("student/courses", "courses")


@app.get("/api/all")
def all_data():
    err = _auth()
    if err:
        return err
    env = store.load_resource("student/all")
    if env is None:
        return jsonify({"error": "No cached student data yet"}), 404
    return jsonify(env)


def _latest_au_only(items: list[dict]) -> list[dict]:
    aus = [g.get("au", "") for g in items if g.get("au")]
    if not aus:
        return items
    latest = max(aus)
    return [g for g in items if g.get("au") == latest]


def _want_history() -> bool:
    return request.args.get("history", "0").lower() in ("1", "true", "yes")


@app.get("/api/grades/elements")
def grade_elements():
    wrap = (lambda d: d) if _want_history() else _latest_au_only
    return _from_store("student/elements", "elements", wrap)


@app.get("/api/grades/modules")
def grade_modules():
    wrap = (lambda d: d) if _want_history() else _latest_au_only
    return _from_store("student/modules", "modules", wrap)


@app.get("/api/stats/<code>")
def element_stats(code: str):
    err = _auth()
    if err:
        return err
    env = store.load_resource("student/stats")
    stats = [s for s in (env["data"] if env else [])
             if (s.get("element") or "").upper() == code.upper()]
    if not stats:
        return jsonify({"error": f"No cached statistics for {code} - run `schoolapp fetch-all --stats`"}), 404
    return jsonify({"element": code.upper(), "stats": stats, "fetched_at": env.get("fetched_at")})


@app.get("/api/documents")
def documents():
    def with_cached(docs: list[dict]) -> list[dict]:
        return [{**d, "cached": store.document_path(d.get("filename", "")).exists()} for d in docs]
    return _from_store("student/documents", "documents", with_cached)


@app.get("/api/documents/<name>")
def document_file(name: str):
    err = _auth()
    if err:
        return err
    if "/" in name or ".." in name:
        return jsonify({"error": "Invalid document name"}), 400
    path = store.document_path(name if name.endswith(".pdf") else f"{name}.pdf")
    if not path.exists():
        return jsonify({"error": f"{name} not downloaded yet - run `schoolapp export --with-documents`"}), 404
    return send_file(path, mimetype="application/pdf")


@app.get("/api/export")
def export():
    err = _auth()
    if err:
        return err
    if request.args.get("format", "json").lower() != "zip":
        env = store.load_resource("student/all")
        if env is None:
            return jsonify({"error": "No cached student data yet"}), 404
        return jsonify(env)

    import io
    import zipfile

    base = store.state_dir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sub in ("student", "catalog", "documents"):
            folder = base / sub
            if not folder.is_dir():
                continue
            for f in sorted(folder.iterdir()):
                if f.is_file() and not f.name.endswith(".tmp"):
                    zf.write(f, f"{sub}/{f.name}")
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"schoolapp-export-{stamp}.zip")


@app.get("/api/catalog")
def catalog():
    def filtered(mods: list[dict]) -> list[dict]:
        out = mods
        for field in ("niveau", "filiere", "semestre"):
            want = request.args.get(field)
            if want:
                out = [m for m in out if (m.get(field) or "").upper() == want.upper()]
        return out
    return _from_store("catalog/modules", "modules", filtered)


@app.get("/api/filieres")
def filieres():
    return _from_store("catalog/filieres", "filieres")


@app.get("/api/promo/<code>")
def promo(code: str):
    """The reconstructed (anonymized) promotion grade distribution for an element,
    cached by `schoolapp promo <code>`. {eval: [[note, count], …]}."""
    return _from_store(f"promo/{code.lower()}", "promo")


@app.get("/api/changes")
def changes():
    """The watcher's change history - the same feed the email digests narrate."""
    err = _auth()
    if err:
        return err
    try:
        limit = max(0, int(request.args.get("limit", 50)))
    except ValueError:
        limit = 50
    items = store.read_changes(limit=limit, since=request.args.get("since") or None,
                               type=request.args.get("type") or None)
    return jsonify({"changes": items, "count": len(items)})


_CSV_RESOURCES = {
    "elements": "student/elements", "grades": "student/elements",
    "modules": "student/modules", "semesters": "student/semesters",
    "years": "student/years", "courses": "student/courses",
    "absences": "student/absences", "stats": "student/stats",
}


@app.get("/api/csv/<resource>")
def csv_export(resource: str):
    """CSV of any tabular resource (marks, NoteRAT/exam ranking stats) for
    spreadsheets. Same rows the CLI `schoolapp csv` writes."""
    err = _auth()
    if err:
        return err
    from . import csvout

    name = _CSV_RESOURCES.get(resource.strip().lower())
    if name is None:
        return jsonify({"error": f"Unknown resource '{resource}'",
                        "choices": sorted(set(_CSV_RESOURCES))}), 404
    env = store.load_resource(name)
    if env is None:
        return jsonify({"error": f"No cached {name} yet"}), 404
    data = env["data"]
    text = csvout.stats_to_csv(data) if name == "student/stats" else csvout.rows_to_csv(data)
    return app.response_class(text, mimetype="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{resource}.csv"'})


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8787, threads=4)
