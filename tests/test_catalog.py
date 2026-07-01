from schoolapp import store
from schoolapp.extractors import catalog_presets
from schoolapp.extractors.catalog import (
    crawl_catalog,
    parse_catalog_modules,
    parse_catalog_options,
    parse_filieres,
)
from schoolapp.models import CatalogModule
from schoolapp.presets import ElementDef, ModuleDef


def test_catalog_options(fixture_html):
    opts = parse_catalog_options(fixture_html("catalog_form"))
    assert len(opts["niveau"]) == 7 and "2A" in opts["niveau"]
    assert len(opts["filiere"]) == 37 and "API-MPT" in opts["filiere"]
    assert opts["semestre"] == ["S1", "S2"]
    assert opts["csrf"]


def test_catalog_modules_full(fixture_html):
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"), filiere="API-MPT")
    assert [m.code_mod for m in mods] == ["API31", "API32", "API33", "API34",
                                          "API35", "API36", "API37"]
    m = mods[0]
    assert (m.intitule, m.niveau, m.semestre) == ("Analyse 3", "2A", "S3")  # server maps S1→S3
    assert (m.vh_mod, m.coef_mod, m.seuil, m.eliminatoire) == ("56", "5.0", "11.0", "7.0")
    assert m.filiere == "API-MPT"
    assert sum(len(x.elements) for x in mods) == 13


def test_catalog_module_nested_elements(fixture_html):
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"))
    api32 = next(m for m in mods if m.code_mod == "API32")
    assert [e.code for e in api32.elements] == ["API321", "API322"]
    e = api32.elements[0]
    assert (e.intitule, e.vh_ctd, e.vh_tp) == ("Chimie organique", "28", "6")
    assert (e.coef_cc, e.coef_ex, e.coef_ecrit, e.coef_tp, e.coef_eelem) == \
        ("0.3", "0.7", "2.5", "0.5", "3.0")


def test_catalog_modules_empty_combo(fixture_html):
    assert parse_catalog_modules(fixture_html("catalog_modules_empty")) == []


def test_filieres(fixture_html):
    filieres = parse_filieres(fixture_html("filieres"))
    assert len(filieres) == 37
    f = filieres[0]
    assert f.code == "API-MPT"
    assert f.label.startswith("Années Préparatoires")
    assert f.raw["Departement"] == "AEEE"


class FakeCatalogClient:
    def __init__(self, fail_combo=None):
        self.fail_combo = fail_combo
        self.posted = []

    def catalog_options(self):
        return {"niveau": ["1A", "2A"], "filiere": ["F1"], "semestre": ["S1"], "csrf": "tok"}

    def catalog_modules(self, niveau, filiere, semestre, csrf=None):
        self.posted.append((niveau, filiere, semestre, csrf))
        if (niveau, filiere, semestre) == self.fail_combo:
            raise RuntimeError("combo boom")
        # the server returns the same module for both niveaux → exercises dedupe
        return [CatalogModule(code_mod="M1", niveau="1A", semestre="S1", filiere=filiere)]


def test_crawl_catalog_dedupes():
    client = FakeCatalogClient()
    mods = crawl_catalog(client)
    assert len(mods) == 1
    assert client.posted == [("1A", "F1", "S1", "tok"), ("2A", "F1", "S1", "tok")]


def test_crawl_catalog_isolates_combo_errors():
    client = FakeCatalogClient(fail_combo=("1A", "F1", "S1"))
    calls = []
    mods = crawl_catalog(client, on_combo=lambda n, f, s, fresh, err: calls.append((n, fresh, err)))
    assert len(mods) == 1  # the 2A combo still delivered
    assert calls[0][1] is None and isinstance(calls[0][2], RuntimeError)
    assert calls[1][2] is None and len(calls[1][1]) == 1


def test_store_roundtrip(tmp_path):
    mods = [CatalogModule(code_mod="M1", niveau="1A", semestre="S1", filiere="F1")]
    path = store.save_resource("catalog/modules", mods, source="/plan-etudes-view/modules",
                               directory=tmp_path)
    assert path == tmp_path / "catalog" / "modules.json"
    envelope = store.load_resource("catalog/modules", directory=tmp_path)
    assert envelope["source"] == "/plan-etudes-view/modules"
    assert envelope["fetched_at"]
    assert envelope["data"][0]["code_mod"] == "M1"
    assert not path.with_name(path.name + ".tmp").exists()  # atomic write cleaned up


def test_store_missing_and_corrupt(tmp_path):
    assert store.load_resource("catalog/modules", directory=tmp_path) is None
    bad = tmp_path / "catalog" / "modules.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    assert store.load_resource("catalog/modules", directory=tmp_path) is None


def test_store_freshness(tmp_path):
    store.save_resource("student/profile", {"x": 1}, directory=tmp_path)
    fresh = store.freshness(["student/profile", "catalog/modules"], directory=tmp_path)
    assert fresh["student/profile"] and fresh["catalog/modules"] is None


def test_module_defs_from_catalog(fixture_html, tmp_path):
    mods = parse_catalog_modules(fixture_html("catalog_modules_full"), filiere="API-MPT")
    defs = catalog_presets.module_defs("2A", "API-MPT", "S3", modules=mods)
    assert len(defs) == 7
    d = defs[0]
    assert (d.code, d.coef_mod, d.seuil, d.eliminatoire) == ("API31", 5.0, 11.0, 7.0)
    assert d.elements[0] == ElementDef("API311", "Analyse 3", 0.3, 0.7, 5.0, 0.0, 5.0)
    # via the cached store file
    store.save_resource(catalog_presets.CATALOG_RESOURCE, mods, directory=tmp_path)
    from_store = catalog_presets.module_defs("2A", "API-MPT", "S3", directory=tmp_path)
    assert from_store == defs
    assert catalog_presets.module_defs("2A", "GC24", "S3", modules=mods) == []


def test_reconcile_reports_mismatches():
    catalog = [ModuleDef("M1", "T", "2A", "S3", 5.0, 11.0, 7.0, [])]
    presets = [ModuleDef("M1", "T", "2A", "S3", 5.0, 10.0, 7.0, []),
               ModuleDef("M2", "U", "2A", "S3", 3.0, 11.0, 7.0, [])]
    mismatches = catalog_presets.reconcile(catalog, presets)
    assert mismatches == ["M1.seuil: catalog=11.0 presets=10.0"]
