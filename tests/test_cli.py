from typer.testing import CliRunner

from schoolapp import store
from schoolapp.cli import app
from schoolapp.extractors.catalog import parse_catalog_modules
from schoolapp.extractors.catalog_presets import CATALOG_RESOURCE

runner = CliRunner()


def test_cli_help_lists_library_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("profile", "fetch-all", "export", "catalog"):
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
