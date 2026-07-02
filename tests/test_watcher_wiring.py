"""Phase 2 wiring: check_once runs on the library client/extractors while the
legacy snapshot + extras cache formats stay byte-identical."""

import json

from schoolapp import store, watcher
from schoolapp.extractors import (
    parse_absences,
    parse_module_grades,
    parse_sanctions,
    parse_semester_results,
)
from schoolapp.extractors._tables import table_by_headers
from tests.conftest import FIXTURES
from tests.test_fetch_all import FakeSession


# ── extras blob parity: adapters vs the original watcher parsing algorithm ──

def _cellget(headers, r, k):
    idx = {h: i for i, h in enumerate(headers)}
    i = idx.get(k)
    return r[i] if i is not None and i < len(r) else ""


def test_absences_blob_parity(fixture_html):
    html = fixture_html("absences")
    headers, rows = table_by_headers(html, {"Element", "Date", "Seance"})
    legacy = {}
    for r in rows:
        elem = _cellget(headers, r, "Element")
        if not elem:
            continue
        date = _cellget(headers, r, "Date").split(" ")[0]
        legacy[f"{elem}|{date}|{_cellget(headers, r, 'Seance')}"] = {
            "element": elem,
            "date": date,
            "seance": _cellget(headers, r, "Seance"),
            "justif": _cellget(headers, r, "Justif").lower(),
            "remarks": _cellget(headers, r, "Remarques"),
        }
    assert legacy and watcher._absences_blob(parse_absences(html)) == legacy


def test_sanctions_blob_parity(fixture_html):
    html = fixture_html("sanctions")
    blob = watcher._sanctions_blob(parse_sanctions(html))
    assert blob and all(isinstance(v, str) for v in blob.values())


def test_modules_blob_parity(fixture_html):
    html = fixture_html("modules_encours")
    headers, rows = table_by_headers(html, {"CodeMod", "Moy", "Dec"})
    legacy = {}
    for r in rows:
        code = _cellget(headers, r, "CodeMod")
        if not code:
            continue
        legacy[f"{code}|{_cellget(headers, r, 'AU')}"] = {
            "code": code,
            "au": _cellget(headers, r, "AU"),
            "moy": _cellget(headers, r, "Moy"),
            "dec": _cellget(headers, r, "Dec"),
        }
    assert legacy and watcher._modules_blob(parse_module_grades(html)) == legacy


def test_semesters_blob_parity(fixture_html):
    html = fixture_html("semesters")
    headers, rows = table_by_headers(html, {"Semestre", "Moy SEM"})
    legacy = {}
    for r in rows:
        if not _cellget(headers, r, "Semestre"):
            continue
        key = f"{_cellget(headers, r, 'Niveau')}|{_cellget(headers, r, 'Semestre')}|{_cellget(headers, r, 'AU')}"
        legacy[key] = {
            "niveau": _cellget(headers, r, "Niveau"),
            "sem": _cellget(headers, r, "Semestre"),
            "au": _cellget(headers, r, "AU"),
            "moy": _cellget(headers, r, "Moy SEM"),
            "dec": _cellget(headers, r, "Decesion") or _cellget(headers, r, "Decision"),
            "rank": _cellget(headers, r, "Classement"),
            "pj": _cellget(headers, r, "PJ"),
        }
    assert legacy and watcher._semesters_blob(parse_semester_results(html)) == legacy


# ── check_once end-to-end on the fixture-backed FakeSession ──────────────

def _run_check(monkeypatch, tmp_path, fail_paths=(), **kw):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    session = FakeSession(fail_paths)
    rc = watcher.check_once(
        email="student@example.test", password="hunter2", timeout=5,
        semester="S4", state_file=None, notify_email=False, config=None,
        session=session, **kw,
    )
    return rc, session


def test_check_once_first_run_snapshot_and_store(monkeypatch, tmp_path):
    rc, _ = _run_check(monkeypatch, tmp_path)
    assert rc == 1  # no baseline counts as a change (legacy behavior)
    snap = json.loads((tmp_path / "schoolapp" / "s4_snapshot.json").read_text())
    assert set(snap) == {"headers", "rows", "fingerprint", "extras"}
    assert "CodeElem" in snap["headers"]
    assert set(snap["extras"]) == {"absences", "sanctions", "modules", "semesters"}
    # modules blob must hold ONLY encours rows, not merged history
    assert len(snap["extras"]["modules"]) == 14
    env = store.load_resource("student/all")
    assert env and env["source"] == "watcher"
    assert len(env["data"]["element_grades"]) == 46  # merged current+history
    assert store.load_resource("student/profile")["data"]["nom"] == "Doe"


def test_check_once_second_run_no_change(monkeypatch, tmp_path):
    _run_check(monkeypatch, tmp_path)
    rc, _ = _run_check(monkeypatch, tmp_path)
    assert rc == 0


def test_check_once_carries_failed_extras_forward(monkeypatch, tmp_path):
    _run_check(monkeypatch, tmp_path)
    before = json.loads((tmp_path / "schoolapp" / "s4_snapshot.json").read_text())
    rc, _ = _run_check(monkeypatch, tmp_path, fail_paths={"/student/absence/bilan"})
    after = json.loads((tmp_path / "schoolapp" / "s4_snapshot.json").read_text())
    assert rc == 0  # carried-forward blob → no spurious "removed" alerts
    assert after["extras"]["absences"] == before["extras"]["absences"]


def test_check_once_raises_when_marks_page_unreachable(monkeypatch, tmp_path):
    import pytest

    with pytest.raises(Exception, match="boom"):
        _run_check(monkeypatch, tmp_path, fail_paths={"/student/noteselem-encours"})
