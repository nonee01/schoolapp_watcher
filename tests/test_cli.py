from typer.testing import CliRunner

from schoolapp import cli, store
from schoolapp.cli import app
from schoolapp.extractors.catalog import parse_catalog_modules
from schoolapp.extractors.catalog_presets import CATALOG_RESOURCE
from schoolapp.models import Document, StudentData, StudentProfile

runner = CliRunner()


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


class _FakeClient:
    def fetch_all(self, include_history=True, include_stats=False):
        return StudentData(
            profile=StudentProfile(nom="Doe"),
            documents=[Document(kind="attestation-scolarite",
                                url="/x", filename="attestation.pdf")],
            fetched_at="2026-07-02T00:00:00+00:00",
        )

    def download(self, doc):
        return b"%PDF-1.4 fake"


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
