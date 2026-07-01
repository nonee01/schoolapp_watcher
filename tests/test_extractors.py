from schoolapp.extractors import (
    REGISTRY,
    build_documents,
    parse_absence_summary,
    parse_absences,
    parse_courses,
    parse_diploma,
    parse_element_grades,
    parse_mark_statistics,
    parse_module_grades,
    parse_profile,
    parse_sanctions,
    parse_semester_results,
    parse_year_results,
)

EMPTY_PAGE = "<html><body><p>rien ici</p></body></html>"


def test_element_grades_encours(fixture_html):
    grades = parse_element_grades(fixture_html("elements_encours"))
    assert len(grades) == 24
    g = grades[0]
    assert (g.code, g.au, g.cc, g.ex, g.moy, g.decision) == \
        ("API311", "2025-2026", "16.5", "14.25", "14.93", "VORD")
    assert g.tp == "--"
    assert g.validated is True
    assert g.is_estimated is False
    assert g.raw["CodeElem"] == "API311"


def test_element_grades_history_uses_decision_column(fixture_html):
    grades = parse_element_grades(fixture_html("elements_history"))
    assert len(grades) == 22
    g = grades[0]
    assert (g.code, g.au, g.rat, g.moy_sr, g.decision) == \
        ("API111", "2024-2025", "15.75", "15.75", "VRAT")


def test_module_grades_encours(fixture_html):
    mods = parse_module_grades(fixture_html("modules_encours"))
    assert len(mods) == 14
    assert (mods[0].code, mods[0].moy, mods[0].decision) == ("API31", "14.93", "VORD")


def test_module_grades_history_keeps_pj_in_raw(fixture_html):
    mods = parse_module_grades(fixture_html("modules_history"))
    assert len(mods) == 14
    assert mods[0].decision == "VRAT"
    assert mods[0].raw["PJ"] == "0.0"


def test_semester_results(fixture_html):
    sems = parse_semester_results(fixture_html("semesters"))
    assert len(sems) == 3
    s = sems[0]
    assert (s.niveau, s.semestre, s.au, s.moy_sem) == ("1A", "S1", "2024-2025", "12.573")
    assert s.decision == "--"  # via the site's `Decesion` typo column
    assert s.classement == "224 / 423"
    assert s.releve_url == "/student/documents/relevesem?niveau=1A&semestre=S1"
    assert s.raw["Filière"] == "API-MPT"


def test_year_results(fixture_html):
    years = parse_year_results(fixture_html("years"))
    assert len(years) == 1
    y = years[0]
    assert (y.niveau, y.filiere, y.au, y.statut) == ("1A", "API-MPT", "2024-2025", "NI")
    assert (y.moy_annee, y.decision, y.classement) == ("13.684", "V", "98 / 419")
    assert y.releve_url == "/student/documents/releveannee?niveau=1A"


def test_diploma_empty_state_is_not_an_error(fixture_html):
    d = parse_diploma(fixture_html("diploma"))
    assert d.empty is True
    assert "Vous n'avez pas de note de diplome" in (d.message or "")
    assert d.rows == []


def test_absence_log(fixture_html):
    absences = parse_absences(fixture_html("absences"))
    assert len(absences) == 6
    a = absences[0]
    assert (a.element, a.date, a.seance) == ("API472", "2026-05-11", "Seance 3")
    assert a.justified is True


def test_absence_summary(fixture_html):
    summary = parse_absence_summary(fixture_html("absences"))
    assert len(summary) == 23
    assert summary[0]["CodeElem"] == "API311"
    assert summary[0]["Intitulé"] == "Analyse 3"


def test_sanctions(fixture_html):
    sanctions = parse_sanctions(fixture_html("sanctions"))
    assert len(sanctions) == 4
    assert (sanctions[0].key, sanctions[0].value) == ("Absences non justifiées", "2")
    assert sanctions[-1].value == "Avertissement"


def test_courses(fixture_html):
    courses = parse_courses(fixture_html("courses"))
    assert len(courses) == 23
    c = courses[0]
    assert (c.code_elem, c.statut, c.section, c.sous_groupe, c.num) == \
        ("API311", "NI", "Sec6", "SG63", "404")
    assert c.groupe == ""


def test_profile(fixture_html):
    p = parse_profile(fixture_html("profile"))
    assert p.code == "STU0000"
    assert p.cne_masar == "X000000000"
    assert (p.nom, p.prenom) == ("Doe", "Jane")
    assert (p.filiere, p.niveau) == ("API-MPT", "2A")
    assert p.email == "student@example.test"
    assert p.photo_url == "photo.png"
    assert "Lieu_Naissance" in p.raw and "Prof_Père" in p.raw  # full page preserved


def test_profile_duplicate_labels_disambiguated():
    html = "<table><tr><th>X</th><td>a</td></tr><tr><th>X</th><td>b</td></tr></table>"
    p = parse_profile(html)
    assert p.raw == {"X": "a", "X (2)": "b"}


def test_mark_statistics_popup(fixture_html):
    stat = parse_mark_statistics(fixture_html("stats"), element="API311",
                                 eval_kind="MoyElem", au="2025-2026", note="14.93")
    assert stat is not None
    assert stat.title == "Statistiques MoyElem - API311 - 2025-2026"
    assert len(stat.rows) == 7
    assert ["Votre note", "14.93"] in stat.rows
    assert (stat.element, stat.eval_kind) == ("API311", "MoyElem")


def test_parsers_return_empty_on_missing_table():
    assert parse_element_grades(EMPTY_PAGE) == []
    assert parse_module_grades(EMPTY_PAGE) == []
    assert parse_semester_results(EMPTY_PAGE) == []
    assert parse_year_results(EMPTY_PAGE) == []
    assert parse_absences(EMPTY_PAGE) == []
    assert parse_absence_summary(EMPTY_PAGE) == []
    assert parse_sanctions(EMPTY_PAGE) == []
    assert parse_courses(EMPTY_PAGE) == []
    d = parse_diploma(EMPTY_PAGE)
    assert d.empty is True and d.message is None


def test_build_documents(fixture_html):
    years = parse_year_results(fixture_html("years"))
    sems = parse_semester_results(fixture_html("semesters"))
    docs = build_documents(years, sems)
    assert len(docs) == 5  # attestation + 1 year relevé + 3 semester relevés
    assert docs[0].kind == "attestation-scolarite"
    assert docs[1].kind == "releve-annee"
    assert docs[1].filename == "releve-1A-2024-2025.pdf"
    assert {d.kind for d in docs[2:]} == {"releve-semestre"}
    assert all(d.content_type == "application/pdf" for d in docs)


def test_registry_covers_table_resources():
    assert {"element_grades", "module_grades", "semester_results", "year_results",
            "absences", "absence_summary", "courses"} <= set(REGISTRY)
    signature, parser = REGISTRY["element_grades"]
    assert "CodeElem" in signature and callable(parser)
