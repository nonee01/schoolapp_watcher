"""New store-served API endpoints + frozen-endpoint regression.

The store is populated the same way production does it: one watcher.check_once
over the fixture-backed FakeSession."""

import pytest

from schoolapp import store, watcher
from schoolapp.api import app
from schoolapp.models import MarkStatistics
from tests.test_fetch_all import FakeSession


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr("schoolapp.api._systemctl", lambda *a: "active")
    watcher.check_once(
        email="student@example.test", password="hunter2", timeout=5,
        semester="S4", state_file=None, notify_email=False, config=None,
        session=FakeSession(),
    )
    return app.test_client()


def test_auth_still_guards_new_endpoints(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "sekrit")
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers={"X-API-Key": "sekrit"}).status_code == 200


def test_status_gains_resources_map_additively(client):
    body = client.get("/api/status").get_json()
    # frozen keys untouched
    for key in ("watcher", "last_check", "next_check", "poll_interval", "server_time"):
        assert key in body
    assert body["resources"]["student/profile"]  # fresh from check_once
    assert body["resources"]["catalog/modules"] is None  # never crawled


def test_frozen_grades_endpoint_shape_unchanged(client):
    body = client.get("/api/grades/S4").get_json()
    assert body["semester"] == "S4"
    mod = body["modules"][0]
    assert set(mod) == {"code", "title", "coef", "seuil", "moy", "partial", "validated", "elements"}
    assert set(mod["elements"][0]) == {"code", "title", "cc", "ex", "tp", "moy", "estimated", "validated", "dec"}


def test_profile_years_courses_all(client):
    assert client.get("/api/profile").get_json()["profile"]["nom"] == "Doe"
    assert len(client.get("/api/years").get_json()["years"]) == 1
    assert len(client.get("/api/courses").get_json()["courses"]) == 23
    env = client.get("/api/all").get_json()
    assert env["source"] == "watcher" and len(env["data"]["element_grades"]) == 46


def test_grade_elements_history_switch(client):
    default = client.get("/api/grades/elements").get_json()["elements"]
    full = client.get("/api/grades/elements?history=1").get_json()["elements"]
    assert len(full) == 46 and len(default) == 24  # latest AU only by default
    assert len(client.get("/api/grades/modules").get_json()["modules"]) == 14


def test_stats_served_from_cache_or_404(client):
    assert client.get("/api/stats/API311").status_code == 404
    store.save_resource("student/stats",
                        [MarkStatistics(element="API311", eval_kind="MoyElem", rows=[["Votre note", "14.93"]])])
    body = client.get("/api/stats/api311").get_json()
    assert body["stats"][0]["rows"] == [["Votre note", "14.93"]]


def test_documents_listing_and_pdf_serving(client):
    docs = client.get("/api/documents").get_json()["documents"]
    assert len(docs) == 5 and all(d["cached"] is False for d in docs)
    name = docs[0]["filename"]
    assert client.get(f"/api/documents/{name}").status_code == 404
    store.save_document(name, b"%PDF-1.4 fake")
    resp = client.get(f"/api/documents/{name}")
    assert resp.status_code == 200 and resp.data.startswith(b"%PDF")
    assert client.get("/api/documents").get_json()["documents"][0]["cached"] is True
    assert client.get("/api/documents/..%2Fescape").status_code in (400, 404)


def test_export_json_and_zip(client):
    body = client.get("/api/export").get_json()
    assert "data" in body and "fetched_at" in body
    resp = client.get("/api/export?format=zip")
    assert resp.status_code == 200 and resp.data[:2] == b"PK"
    assert "zip" in resp.headers["Content-Type"]


def test_catalog_endpoints(client, fixture_html):
    assert client.get("/api/catalog").status_code == 404
    from schoolapp.extractors.catalog import parse_catalog_modules
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"), filiere="API-MPT")
    store.save_resource("catalog/modules", mods)
    store.save_resource("catalog/filieres", [])
    everything = client.get("/api/catalog").get_json()["modules"]
    filtered = client.get("/api/catalog?filiere=api-mpt&niveau=2A").get_json()["modules"]
    assert everything and filtered == everything  # fixture is a single 2A/API-MPT combo
    assert client.get("/api/catalog?filiere=NOPE").get_json()["modules"] == []
    assert client.get("/api/filieres").get_json()["filieres"] == []
