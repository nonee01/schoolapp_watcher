from dataclasses import asdict

from schoolapp.models import ElementGrade, StudentData, Absence, PASS_THRESHOLD


def test_pass_threshold_is_eleven():
    assert PASS_THRESHOLD == 11.0


def test_element_grade_is_estimated_and_validated():
    assert ElementGrade(code="API101", moy="12.5*").is_estimated is True
    assert ElementGrade(code="API101", moy="12.5").is_estimated is False
    assert ElementGrade(code="API101", moy="12.5*").validated is True
    assert ElementGrade(code="API101", moy="10.0").validated is False
    assert ElementGrade(code="API101", moy="--").validated is None
    assert ElementGrade(code="API101", moy="").validated is None
    assert ElementGrade(code="API101", moy="n/a").validated is None


def test_models_are_asdict_serializable():
    eg = ElementGrade(code="API101", cc="12", raw={"CC": "12"})
    d = asdict(eg)
    assert d["code"] == "API101"
    assert d["raw"] == {"CC": "12"}


def test_studentdata_defaults_are_independent():
    a, b = StudentData(), StudentData()
    a.absences.append(Absence(element="API101"))
    assert b.absences == []          # default_factory, not shared
    assert a.errors == {}
