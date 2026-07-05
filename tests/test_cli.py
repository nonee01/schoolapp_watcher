import json

from typer.testing import CliRunner

from schoolapp import cli, store, watcher
from schoolapp.cli import app
from schoolapp.extractors.catalog import parse_catalog_modules
from schoolapp.extractors.catalog_presets import CATALOG_RESOURCE
from schoolapp.models import Document, StudentData, StudentProfile
from tests.test_fetch_all import FakeSession

runner = CliRunner()


def _seed_store(tmp_path, monkeypatch):
    """Populate the store exactly as production does — one check_once over fixtures."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    watcher.check_once(
        email="student@example.test", password="hunter2", timeout=5,
        semester="S4", state_file=None, notify_email=False, config=None,
        session=FakeSession(),
    )


def test_version_flag_works():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "schoolapp" in result.output


def test_cli_help_lists_library_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("profile", "fetch-all", "export", "catalog", "serve", "status"):
        assert cmd in result.output


def test_catalog_show_from_store(fixture_html, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"), filiere="API-MPT")
    store.save_resource(CATALOG_RESOURCE, mods)
    result = runner.invoke(app, ["catalog", "show", "2A", "API-MPT", "S3"])
    assert result.exit_code == 0
    assert "API31" in result.output
    assert "API321" in result.output  # element weights rendered


def test_catalog_show_without_cache_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = runner.invoke(app, ["catalog", "show", "2A", "API-MPT", "S3"])
    assert result.exit_code == 1
    assert "catalog crawl" in result.output


def test_status_reads_store_freshness(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    empty = runner.invoke(app, ["status"])
    assert empty.exit_code == 0 and "Store is empty" in empty.output

    store.save_resource("student/profile", StudentProfile(nom="Doe"), source="fetch_all")
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "student/profile" in result.output
    assert "not cached" in result.output  # e.g. catalog/modules still absent


def test_serve_wires_waitress_with_host_and_port(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("API_KEY", "k")
    called = {}

    import waitress

    monkeypatch.setattr(waitress, "serve",
                        lambda flask_app, **kw: called.update(kw))
    result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "9999", "--threads", "2"])
    assert result.exit_code == 0
    assert called == {"host": "127.0.0.1", "port": 9999, "threads": 2}


def test_show_grades_human_and_json(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch)

    human = runner.invoke(app, ["show", "grades"])
    assert human.exit_code == 0
    assert "Element grades" in human.output and "API311" in human.output

    # -q suppresses the stderr chrome, so stdout is pure JSON
    result = runner.invoke(app, ["-q", "show", "grades", "--json"])
    assert result.exit_code == 0
    elements = json.loads(result.output)
    assert len(elements) == 24 and elements[0]["code"] == "API311"  # latest AU only

    full = json.loads(runner.invoke(app, ["-q", "show", "grades", "--history", "--json"]).output)
    assert len(full) == 46


def test_show_absences_and_modules(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch)
    absences = runner.invoke(app, ["show", "absences"])
    assert absences.exit_code == 0 and "Absences" in absences.output
    mods = json.loads(runner.invoke(app, ["-q", "show", "grades", "--modules", "--json"]).output)
    assert mods and all("code" in m for m in mods)


def test_show_empty_store_hint_and_json_null(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    human = runner.invoke(app, ["show", "profile"])
    assert human.exit_code == 0 and "No cached profile" in human.output
    result = runner.invoke(app, ["-q", "show", "profile", "--json"])
    assert json.loads(result.output) is None


class _FakeClient:
    def fetch_all(self, include_history=True, include_stats=False):
        return StudentData(
            profile=StudentProfile(nom="Doe"),
            documents=[Document(kind="attestation-scolarite",
                                url="/x", filename="attestation.pdf")],
            fetched_at="2026-07-02T00:00:00+00:00",
        )

    def documents(self):
        return [Document(kind="attestation-scolarite", url="/x", filename="attestation.pdf"),
                Document(kind="releve-annee", url="/y", filename="releve.pdf")]

    def download(self, doc):
        if doc.filename == "releve.pdf":
            raise RuntimeError("boom")
        return b"%PDF-1.4 fake"


def test_documents_download_caches_and_isolates_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: _FakeClient())
    out_dir = tmp_path / "pdfs"
    result = runner.invoke(app, ["-q", "documents", "download", "--all",
                                 "--out", str(out_dir), "--json"])
    assert result.exit_code == 0
    manifest = json.loads(result.output)
    ok = next(m for m in manifest if m["filename"] == "attestation.pdf")
    bad = next(m for m in manifest if m["filename"] == "releve.pdf")
    assert ok["bytes"] == len(b"%PDF-1.4 fake") and "error" not in ok
    assert "boom" in bad["error"]  # one failure doesn't abort the other
    assert store.document_path("attestation.pdf").exists()
    assert (out_dir / "attestation.pdf").read_bytes().startswith(b"%PDF")


def test_documents_download_lists_choices_when_no_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: _FakeClient())
    result = runner.invoke(app, ["-q", "documents", "download", "--json"])
    choices = json.loads(result.output)
    assert {c["kind"] for c in choices} == {"attestation-scolarite", "releve-annee"}
    assert not store.document_path("attestation.pdf").exists()  # nothing downloaded


def test_export_matches_store_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: _FakeClient())
    out_dir = tmp_path / "archive"
    result = runner.invoke(app, ["export", "--out", str(out_dir), "--with-documents"])
    assert result.exit_code == 0
    # nested student/ layout, identical to the store and the /api/export zip
    assert (out_dir / "student" / "all.json").exists()
    assert (out_dir / "student" / "profile.json").exists()
    assert (out_dir / "documents" / "attestation.pdf").read_bytes().startswith(b"%PDF")
    # --with-documents also seeds the live store so /api/documents/<kind> can serve it
    assert store.document_path("attestation.pdf").exists()


def test_changes_command_reads_history(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    p = tmp_path / "schoolapp" / "changes.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ts": "2026-07-05T15:00:00", "type": "rattrapage",
                             "semester": "S4", "summary": "API421 -> 15.03*"}) + "\n",
                 encoding="utf-8")
    human = runner.invoke(app, ["changes"])
    assert human.exit_code == 0 and "rattrapage" in human.output
    data = json.loads(runner.invoke(app, ["-q", "changes", "--json"]).output)
    assert data[0]["type"] == "rattrapage"


def test_bare_invocation_shows_dashboard_or_help(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    empty = runner.invoke(app, [])
    assert empty.exit_code == 0
    assert "fetch-all" in empty.output          # empty store -> guidance

    _seed_store(tmp_path, monkeypatch)
    dash = runner.invoke(app, [])
    assert dash.exit_code == 0
    assert "State store" in dash.output         # freshness table = dashboard marker

    explicit = runner.invoke(app, ["dashboard"])
    assert explicit.exit_code == 0 and "State store" in explicit.output


def test_explain_command(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch)
    result = runner.invoke(app, ["explain", "API311"])
    assert result.exit_code == 0 and "Art. 4" in result.output
    data = json.loads(runner.invoke(app, ["-q", "explain", "API311", "--json"]).output)
    assert data["code"] == "API311" and data["steps"]
    missing = runner.invoke(app, ["explain", "ZZZ999"])
    assert missing.exit_code == 1


def test_csv_command_stdout_and_file(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch)
    # -q keeps stderr chrome out of stdout so the CSV is clean and pipeable
    out = runner.invoke(app, ["-q", "csv", "grades"]).output
    lines = [l for l in out.splitlines() if l]
    assert lines[0].startswith("code,") and any("API311" in l for l in lines)

    dest = tmp_path / "grades.csv"
    result = runner.invoke(app, ["csv", "grades", "--latest", "--out", str(dest)])
    assert result.exit_code == 0
    body = dest.read_text().splitlines()
    assert body[0].startswith("code,")
    # --latest keeps one académique year only (24 current elements, not 46)
    assert 1 < len(body) <= 25


def test_csv_unknown_resource_and_empty_store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    bad = runner.invoke(app, ["csv", "nope"])
    assert bad.exit_code == 2 and "Unknown resource" in bad.output
    empty = runner.invoke(app, ["csv", "grades"])
    assert empty.exit_code == 1


class _PromoClient:
    NOTES = [20.0, 15.5, 15.5, 12.0, 8.0]  # 5 anonymized students, one element

    def element_grades(self, history=False):
        from schoolapp.models import ElementGrade
        return [ElementGrade(code="API421", au="2025-2026")]

    def rank_for_note(self, code, eval_kind, au, note):
        n = float(note)
        return 1 + sum(1 for x in self.NOTES if x > n), len(self.NOTES)


def test_promo_reconstructs_whole_promotion(tmp_path, monkeypatch):
    import csv as _csv
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_library_client", lambda *a, **k: _PromoClient())
    out = tmp_path / "promo.csv"
    result = runner.invoke(app, ["-q", "promo", "API421", "--eval", "moy", "--out", str(out)])
    assert result.exit_code == 0
    rows = list(_csv.DictReader(out.open()))
    assert len(rows) == 5                       # every student recovered
    assert all(r["eval"] == "MoyElem" for r in rows)
    assert [r["note"] for r in rows] == ["20.00", "15.50", "15.50", "12.00", "8.00"]
    assert [r["rank"] for r in rows] == ["1", "2", "3", "4", "5"]
    assert store.load_resource("promo/api421") is not None   # cached for reuse
