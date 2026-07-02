"""Phase 6: generic change detection for the remaining per-student resources +
the once-per-crawl catalog change summary."""

import json
from dataclasses import replace

from typer.testing import CliRunner

from schoolapp import cli, store, watcher
from schoolapp.extractors.catalog import parse_catalog_modules
from schoolapp.extractors.catalog_presets import CATALOG_RESOURCE
from tests.test_fetch_all import FakeSession

runner = CliRunner()


def test_keyed_diff_lines_add_change_remove():
    old = [{"code": "A", "au": "24", "moy": "10"}, {"code": "B", "au": "24", "moy": "12"}]
    new = [{"code": "A", "au": "24", "moy": "15"}, {"code": "C", "au": "24", "moy": "9"}]
    lines = watcher._keyed_diff_lines(old, new, ("code", "au"), ("moy",))
    assert lines == ["A 24 - moy: 10 -> 15", "+ C 24 (moy=9)", "− B 24 (retiré)"]


def _check(monkeypatch, tmp_path, notify_email=False):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return watcher.check_once(
        email="student@example.test", password="hunter2", timeout=5,
        semester="S4", state_file=None, notify_email=notify_email, config=None,
        session=FakeSession(),
    )


def _tamper(tmp_path, resource, mutate):
    path = tmp_path / "schoolapp" / f"{resource}.json"
    env = json.loads(path.read_text())
    mutate(env["data"])
    path.write_text(json.dumps(env, ensure_ascii=False))


def test_first_run_emits_no_generic_alerts(monkeypatch, tmp_path):
    _check(monkeypatch, tmp_path)  # no envelopes yet -> no baseline -> silent
    hist = (tmp_path / "schoolapp" / "changes.jsonl").read_text().splitlines()
    types = {json.loads(line)["type"] for line in hist}
    assert types == {"grades"}  # only the legacy first-snapshot entry


def test_year_change_lands_in_digest_and_history(monkeypatch, tmp_path):
    _check(monkeypatch, tmp_path)
    _tamper(tmp_path, "student/years", lambda d: d[0].__setitem__("moy_annee", "9.99"))
    sent = {}
    monkeypatch.setattr(watcher, "send_email",
                        lambda *, subject, body, html, config: sent.update(subject=subject, html=html))
    rc = _check(monkeypatch, tmp_path, notify_email=True)
    assert rc == 1
    assert "Résultats d'année" in sent["html"] and "9.99 ->" in sent["html"]
    hist = [json.loads(x) for x in (tmp_path / "schoolapp" / "changes.jsonl").read_text().splitlines()]
    assert any(e["type"] == "years" for e in hist)


def test_history_grade_rows_diffed_but_current_rows_left_to_rich_path(monkeypatch, tmp_path):
    _check(monkeypatch, tmp_path)

    def mutate(items):
        for d in items:
            if "Dec" not in (d.get("raw") or {}):  # a history-only row
                d["moy"] = "0.42"
                return
    _tamper(tmp_path, "student/elements", mutate)
    rc = _check(monkeypatch, tmp_path)
    assert rc == 1
    hist = [json.loads(x) for x in (tmp_path / "schoolapp" / "changes.jsonl").read_text().splitlines()]
    assert any(e["type"] == "elements_history" and "0.42" not in e["summary"] for e in hist)


def test_catalog_crawl_emits_one_change_summary(monkeypatch, tmp_path, fixture_html):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"), filiere="API-MPT")
    assert len(mods) > 1
    store.save_resource(CATALOG_RESOURCE, mods[1:])  # baseline missing mods[0]
    fresh = [replace(mods[0]), replace(mods[1], coef_mod="9.9")] + mods[2:]

    class FakeClient:
        def filieres(self):
            return []

    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(cli, "crawl_catalog",
                        lambda client, niveaux=None, filieres=None, on_combo=None:
                        (on_combo("2A", "API-MPT", "S1", fresh, None), fresh)[1])
    result = runner.invoke(cli.app, ["catalog", "crawl"])
    assert result.exit_code == 0
    assert "Catalogue: +1 module(s), ~1 modifié(s)" in result.output
    hist = [json.loads(x) for x in (tmp_path / "schoolapp" / "changes.jsonl").read_text().splitlines()]
    assert sum(1 for e in hist if e["type"] == "catalog") == 1
