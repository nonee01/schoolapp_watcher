from __future__ import annotations

import hmac
import json
import os
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import store
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
    """Check X-API-Key against API_KEY when set; unauthenticated if API_KEY is
    unset (cli.py warns about this at startup). Returns a (response, status)
    error tuple to short-circuit the route, or None if the request may proceed."""
    key = os.environ.get("API_KEY", "")
    if key and not hmac.compare_digest(request.headers.get("X-API-Key", ""), key):
        return jsonify({"error": "Invalid API key"}), 401
    return None


def _cell(row: list[str], idx: dict[str, int], key: str) -> str:
    """Look up one column of a snapshot row by header name; "--" if the column
    is absent, out of range, or blank (the store's convention for "no data")."""
    i = idx.get(key)
    if i is None or i >= len(row):
        return "--"
    v = row[i].strip()
    return v if v else "--"


def _systemctl(*args: str) -> str:
    """Run `systemctl --user <args>` and return its stdout, stripped. Returns ""
    on any failure (binary missing, timeout, non-systemd host) so callers degrade
    to "unknown"/"inactive" instead of the watcher-status endpoints crashing."""
    try:
        out = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def _active_interval() -> int:
    hour = datetime.now().hour
    return SLOW_INTERVAL if SLOW_WINDOW[0] <= hour < SLOW_WINDOW[1] else _POLL_INTERVAL


@app.errorhandler(HTTPException)
def _http_error(exc: HTTPException):
    """Routing errors (404 on an unknown path, 405 on a wrong method, etc.) as
    JSON instead of Flask's default HTML error page — this is an API, every
    client response should be parseable JSON."""
    return jsonify({"error": exc.description or exc.name}), exc.code


@app.errorhandler(Exception)
def _unhandled_error(exc: Exception):
    """Last-resort net: any exception that escapes a route (a crash-prone
    parse, a malformed store envelope, etc.) becomes a clean JSON 500 instead
    of a raw traceback reaching an HTTP client."""
    app.logger.exception("Unhandled error in %s", request.path)
    return jsonify({"error": "Internal server error"}), 500


@app.get("/api/status")
def status():
    """Watcher liveness + per-resource cache freshness. Reads systemctl state
    and snapshot/resource mtimes only; no network call.
    Frozen shape (see CLAUDE.md / schoolapp-api-compatibility skill): top-level
    keys watcher, last_check, next_check, poll_interval, server_time must not
    change. `resources` was added additively (spec §8.1)."""
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
        # additive (spec §8.1): per-resource freshness map from the store
        "resources": store.freshness(
            ["student/all", *store.RESOURCE_FILES.values(), "catalog/modules", "catalog/filieres"]),
    })


@app.get("/api/grades/<semester>")
def grades(semester: str):
    """Element/module grades for a semester, joined against the frozen
    curriculum preset (presets.py) so every element shows even if the portal
    snapshot is missing rows. Reads the cached snapshot only; no network call.
    Frozen shape (CLAUDE.md): {semester, modules[]} with each module/element
    key set fixed — do not add/remove/rename keys, see CLAUDE.md."""
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
    """The legacy snapshot's non-tabular sidecar data (absences/modules/
    semesters/sanctions keyed by id) — {} if there's no snapshot yet or it
    doesn't carry an `extras` dict."""
    snap = _load_snapshot(_snapshot_path(sem, None))
    if snap is None or not isinstance(snap.extras, dict):
        return {}
    return snap.extras


@app.get("/api/absences")
def absences():
    """Absence records + sanctions from the cached snapshot; no network call.
    Frozen shape (CLAUDE.md): {absences[], sanctions{}} — see CLAUDE.md."""
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
    """The portal's own official module results (as opposed to /api/grades'
    curriculum-joined view). Reads the cached snapshot only; no network call.
    Frozen shape (CLAUDE.md): {modules[]} — see CLAUDE.md."""
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
    """Per-semester summary results from the cached snapshot; no network call.
    Frozen shape (CLAUDE.md): {semesters[]} — see CLAUDE.md."""
    err = _auth()
    if err:
        return err
    extras = _extras()
    items = list((extras.get("semesters") or {}).values())
    items.sort(key=lambda x: (x.get("au", ""), x.get("sem", "")))
    return jsonify({"semesters": items})


@app.get("/api/history")
def history():
    """Newest-first watcher check history, one entry per line of the legacy
    history file (`?limit=`, default 100, clamped to [1, 1000]). Reads the
    cached file only; no network call. Frozen shape (CLAUDE.md): {history[]}
    — see CLAUDE.md."""
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
    """Trigger one synchronous watcher check against the live portal (network
    call — logs in, scrapes, may send email/Telegram notifications on change).
    Rejects a concurrent check with 409 rather than racing two logins. Not a
    frozen endpoint, but action-shaped: {changed, checked_at}."""
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
    """Stop the watcher systemd unit (`systemctl --user stop`), local to this
    host — no portal network call. Degrades to {"watcher": "inactive"} if
    systemctl itself is unavailable."""
    err = _auth()
    if err:
        return err
    _systemctl("stop", WATCHER_UNIT)
    return jsonify({"watcher": _systemctl("is-active", WATCHER_UNIT) or "inactive"})


@app.post("/api/watcher/resume")
def resume_watcher():
    """Start the watcher systemd unit (`systemctl --user start`), local to
    this host — no portal network call. Degrades to {"watcher": "unknown"} if
    systemctl itself is unavailable."""
    err = _auth()
    if err:
        return err
    _systemctl("start", WATCHER_UNIT)
    return jsonify({"watcher": _systemctl("is-active", WATCHER_UNIT) or "unknown"})


# ── library-store endpoints (spec §8.1) — all additive, all cache-served ──────

def _from_store(name: str, key: str, wrap=lambda d: d):
    """Standard read-through: 401 via _auth, 404 when the envelope isn't
    cached yet, otherwise {key: wrap(data), fetched_at}. Never hits the
    network — these endpoints only ever serve what fetch_all/the watcher
    already wrote to the store."""
    err = _auth()
    if err:
        return err
    env = store.load_resource(name)
    if env is None:
        return jsonify({"error": f"No cached {name} yet — run the watcher or `schoolapp fetch-all`"}), 404
    return jsonify({key: wrap(env["data"]), "fetched_at": env.get("fetched_at")})


@app.get("/api/profile")
def profile():
    """Cached student profile (name, filiere, niveau, ...). See _from_store."""
    return _from_store("student/profile", "profile")


@app.get("/api/years")
def years():
    """Cached year-level results. See _from_store."""
    return _from_store("student/years", "years")


@app.get("/api/courses")
def courses():
    """Cached course enrollments. See _from_store."""
    return _from_store("student/courses", "courses")


@app.get("/api/all")
def all_data():
    """The full cached StudentData bundle as one envelope (all resources in a
    single response) — no network call."""
    err = _auth()
    if err:
        return err
    env = store.load_resource("student/all")
    if env is None:
        return jsonify({"error": "No cached student data yet"}), 404
    return jsonify(env)


def _latest_au_only(items: list[dict]) -> list[dict]:
    """Filter a list of {..., "au": ...} dicts down to the most recent
    académie-universitaire, string-sorted (AU codes like "2025-2026" sort
    correctly this way). Returns `items` unchanged if none carry an `au`."""
    aus = [g.get("au", "") for g in items if g.get("au")]
    if not aus:
        return items
    latest = max(aus)
    return [g for g in items if g.get("au") == latest]


def _want_history() -> bool:
    return request.args.get("history", "0").lower() in ("1", "true", "yes")


@app.get("/api/grades/elements")
def grade_elements():
    """Cached element grades — current AU only by default, `?history=1` for
    every AU on record. See _from_store."""
    wrap = (lambda d: d) if _want_history() else _latest_au_only
    return _from_store("student/elements", "elements", wrap)


@app.get("/api/grades/modules")
def grade_modules():
    """Cached module grades — current AU only by default, `?history=1` for
    every AU on record. See _from_store."""
    wrap = (lambda d: d) if _want_history() else _latest_au_only
    return _from_store("student/modules", "modules", wrap)


@app.get("/api/stats/<code>")
def element_stats(code: str):
    """Promo-wide mark statistics cached for one element code (case-
    insensitive) — no network call; 404 if `schoolapp fetch-all --stats`
    hasn't cached anything for this code yet."""
    err = _auth()
    if err:
        return err
    env = store.load_resource("student/stats")
    stats = [s for s in (env["data"] if env else [])
             if (s.get("element") or "").upper() == code.upper()]
    if not stats:
        return jsonify({"error": f"No cached statistics for {code} — run `schoolapp fetch-all --stats`"}), 404
    return jsonify({"element": code.upper(), "stats": stats, "fetched_at": env.get("fetched_at")})


@app.get("/api/documents")
def documents():
    """Cached document listing (transcripts/relevés), each annotated with
    whether its PDF bytes are already downloaded locally. See _from_store."""
    def with_cached(docs: list[dict]) -> list[dict]:
        return [{**d, "cached": store.document_path(d.get("filename", "")).exists()} for d in docs]
    return _from_store("student/documents", "documents", with_cached)


@app.get("/api/documents/<name>")
def document_file(name: str):
    """Serve one previously-downloaded document's PDF bytes from local disk;
    no network call (documents are fetched separately via `schoolapp export
    --with-documents`, never inline on a GET). Rejects `name` containing "/"
    or ".." to keep the lookup inside the documents directory."""
    err = _auth()
    if err:
        return err
    if "/" in name or ".." in name:
        return jsonify({"error": "Invalid document name"}), 400
    path = store.document_path(name if name.endswith(".pdf") else f"{name}.pdf")
    if not path.exists():
        return jsonify({"error": f"{name} not downloaded yet — run `schoolapp export --with-documents`"}), 404
    return send_file(path, mimetype="application/pdf")


@app.get("/api/export")
def export():
    """The full cached bundle, either as JSON (`?format=json`, default — same
    body as /api/all) or as a zip of the whole state directory
    (`?format=zip`: student/, catalog/, documents/, minus .tmp files). No
    network call, no scraping — packages what's already on disk."""
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
    """Institution-wide module catalog crawled via `schoolapp catalog crawl`,
    optionally filtered by `?niveau=&filiere=&semestre=` (case-insensitive
    exact match, AND'd together). No network call — reads the cache."""
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
    """Cached list of filières from the catalog crawl. See _from_store."""
    return _from_store("catalog/filieres", "filieres")


@app.get("/api/promo/<code>")
def promo(code: str):
    """The reconstructed (anonymized) promotion grade distribution for an element,
    cached by `schoolapp promo <code>`. {eval: [[note, count], …]}."""
    return _from_store(f"promo/{code.lower()}", "promo")


@app.get("/api/changes")
def changes():
    """The watcher's change history — the same feed the email digests narrate."""
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
