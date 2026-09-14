"""The shared presentation layer: color semantics + every renderer runs on the
envelope-shaped data the store hands back."""

import io

from rich.console import Console

from schoolapp import render


def _render(renderable) -> str:
    buf = io.StringIO()
    Console(file=buf, theme=render.THEME, width=200).print(renderable)
    return buf.getvalue()


def test_status_badge_semantics():
    assert render.status_badge("VORD").style == "ok"
    assert "✓" in render.status_badge("VORD").plain
    assert render.status_badge("NV").style == "fail"
    assert "✗" in render.status_badge("NV").plain
    assert render.status_badge("RAT").style == "rat"
    assert render.status_badge("--").style == "muted"
    assert render.status_badge("").style == "muted"
    assert render.status_badge(None).style == "muted"


def test_every_renderer_runs_on_envelope_data():
    assert "API311" in _render(render.element_grades_table(
        [{"code": "API311", "au": "24", "cc": "16", "moy": "14", "decision": "VORD"}]))
    assert "NV" in _render(render.module_grades_table(
        [{"code": "API45", "au": "24", "moy": "8", "decision": "NV"}]))
    assert _render(render.semesters_table(
        [{"niveau": "2A", "semestre": "S3", "au": "24", "moy_sem": "12", "decision": "V"}]))
    assert _render(render.years_table(
        [{"niveau": "2A", "filiere": "API", "au": "24", "moy_annee": "12", "decision": "V"}]))
    assert _render(render.courses_table([{"code_elem": "API311", "statut": "OK", "num": "1"}]))
    out = _render(render.absences_view(
        [{"element": "API311", "date": "01/01", "seance": "S1", "justified": True}],
        [{"CodeElem": "API311", "Justifiée": "1"}],
        [{"key": "Total", "value": "3"}]))
    assert "API311" in out and "Sanctions" in out
    assert "14.93" in _render(render.stats_view(
        [{"element": "API311", "eval_kind": "MoyElem", "title": "t", "rows": [["Votre note", "14.93"]]}]))
    assert "cached" in _render(render.documents_table(
        [{"kind": "attestation", "filename": "a.pdf"}], cached={"a.pdf": True}))
    assert "API31" in _render(render.catalog_table(
        [{"code_mod": "API31", "intitule": "x", "niveau": "2A", "semestre": "S3",
          "filiere": "F", "coef_mod": "1", "elements": [{"code": "API311"}]}]))
    assert "API-MPT" in _render(render.filieres_table([{"code": "API-MPT", "label": "x"}]))
    assert "not cached" in _render(render.freshness_table(
        "/tmp", {"student/all": "2026-07-02", "catalog/modules": None}))


def test_error_and_empty_panels():
    assert "boom" in _render(render.error_panel("boom", hint="try again"))
    assert "No cached grades" in _render(render.empty_hint("grades"))


def test_changes_table_and_dashboard_view():
    changes = [{"ts": "2026-07-05T15:00:00", "type": "rattrapage",
                "semester": "S4", "summary": "API421 -> 15.03*"}]
    assert "rattrapage" in _render(render.changes_table(changes))
    out = _render(render.dashboard_view(
        {"prenom": "A", "nom": "B", "filiere": "API", "niveau": "2A"},
        [{"niveau": "2A", "semestre": "S4", "au": "24", "moy_sem": "12", "decision": "V"}],
        {"student/all": "2026-07-05"}, changes, "/tmp/store"))
    assert "A B" in out and "S4" in out and "rattrapage" in out and "/tmp/store" in out
    # empty-safe
    assert _render(render.dashboard_view(None, [], {}, [], "/tmp/store"))


# ── staleness: a two-month-old store must not look current ────────────────

def test_age_text_flags_stale_and_very_stale():
    from datetime import datetime, timedelta, timezone

    from schoolapp import render

    def iso(days):
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    assert render.age_text(iso(0)).style == "ok"
    assert render.age_text(iso(3)).style == "muted"
    assert render.age_text(iso(20)).style == "warning"
    assert render.age_text(iso(68)).style == "fail"
    assert render.age_text(None).plain == "--"
    assert render.age_text("not-a-date").plain == "--"


def test_dashboard_warns_when_identity_comes_from_a_stale_profile():
    from datetime import datetime, timedelta, timezone

    from rich.console import Console

    from schoolapp import render

    old = (datetime.now(timezone.utc) - timedelta(days=68)).isoformat()
    view = render.dashboard_view(
        {"prenom": "A", "nom": "B", "filiere": "API-MPT", "niveau": "2A"},
        [], {"student/profile": old}, [], "/tmp/store")
    out = Console(theme=render.THEME, width=200, record=True)
    out.print(view)
    text = out.export_text()
    assert "68 days old" in text and "fetch-all" in text


def test_dashboard_quiet_when_profile_is_fresh():
    from datetime import datetime, timezone

    from rich.console import Console

    from schoolapp import render

    view = render.dashboard_view(
        {"prenom": "A", "nom": "B", "filiere": "GE-DI", "niveau": "3A"},
        [], {"student/profile": datetime.now(timezone.utc).isoformat()}, [], "/tmp/store")
    out = Console(theme=render.THEME, width=200, record=True)
    out.print(view)
    assert "fetch-all" not in out.export_text()
