"""Règlement engine (CE 2019-10-22 / CU 2019-12-25). Real S4 values from the
user's transcript are the fixtures: the portal's own published numbers pin
Art. 4 rounding (9.075 -> 9.08 means decimal half-up, not float banker's)."""

from decimal import Decimal

from schoolapp import academics as ac


def test_parse_note():
    assert ac.parse_note("9.08") == Decimal("9.08")
    assert ac.parse_note("15,5") == Decimal("15.5")
    assert ac.parse_note("14.93*") == Decimal("14.93")
    assert ac.parse_note("--") is None and ac.parse_note("") is None and ac.parse_note(None) is None


def test_fmt_note_rounds_half_up_like_the_portal():
    assert ac.fmt_note(Decimal("15.025")) == "15.03"   # float math would give 15.02
    assert ac.fmt_note(Decimal("9.075")) == "9.08"
    assert ac.fmt_note(Decimal("15")) == "15.00"


def test_bars_for_cycle():
    prepa = ac.bars_for("2A")
    assert (prepa.module_pass, prepa.element_floor) == (Decimal("11"), Decimal("7"))
    ing = ac.bars_for("3A")
    assert (ing.module_pass, ing.element_floor) == (Decimal("12"), Decimal("8"))


def test_element_moy_so_art4_matches_portal():
    # API411: 0.3·11.5 + 0.7·14.25 = 13.425 -> 13.43 (no TP)
    assert ac.fmt_note(ac.element_moy_so(
        cc=Decimal("11.5"), ex=Decimal("14.25"), tp=None,
        c1=Decimal("5"), c2=Decimal("0"))) == "13.43"
    # API441 with TP: (8·(0.3·17.18 + 0.7·14.0) + 1·15.23)/9 = 14.985… -> within 0.01 of portal 14.98
    val = ac.element_moy_so(cc=Decimal("17.18"), ex=Decimal("14.0"), tp=Decimal("15.23"),
                            c1=Decimal("8"), c2=Decimal("1"))
    assert abs(val - Decimal("14.98")) <= Decimal("0.01")


def test_element_moy_sr_art7_real_cases():
    # API421 Algèbre 2: max(9.08, max(0.3·16.25 + 0.7·14.5, 14.5)) = 15.025 -> 15.03
    sr = ac.element_moy_sr(moy_so=Decimal("9.08"), cc=Decimal("16.25"), rat=Decimal("14.5"))
    assert ac.fmt_note(sr) == "15.03"
    # API452 Prog Avancée: max(8.6, max(14.55, 15.0)) = 15.00 (Rat alone wins)
    sr = ac.element_moy_sr(moy_so=Decimal("8.6"), cc=Decimal("13.5"), rat=Decimal("15.0"))
    assert ac.fmt_note(sr) == "15.00"
    # No CC -> max(SO, Rat)
    assert ac.element_moy_sr(moy_so=Decimal("9.0"), cc=None, rat=Decimal("10.0")) == Decimal("10.0")
    # SO better than rat session -> SO stands (Art. 7 Sup)
    assert ac.element_moy_sr(moy_so=Decimal("10.9"), cc=Decimal("5.0"), rat=Decimal("9.0")) == Decimal("10.9")


def test_models_gain_additive_computed_fields():
    from dataclasses import asdict
    from schoolapp.models import ElementGrade, ModuleGrade
    e = asdict(ElementGrade())
    assert e["moy_sr_computed"] == "" and e["decision_computed"] == ""
    m = asdict(ModuleGrade())
    assert m["moy_computed"] == "" and m["decision_computed"] == "" and m["coeff_assumed"] is False


def _elem(code, au="24/25", cc="", ex="", moy="", rat="", moy_sr="", decision=""):
    from schoolapp.models import ElementGrade
    return ElementGrade(code=code, au=au, cc=cc, ex=ex, moy=moy, rat=rat,
                        moy_sr=moy_sr, decision=decision)


def test_module_def_for_uses_presets():
    mdef = ac.module_def_for("API421")
    assert mdef is not None and mdef.code.upper() == "API42"
    assert ac.module_def_for("ZZZ999") is None


def test_module_after_rat_validates_and_caps():
    mdef = ac.module_def_for("API452")  # module API45: Méthodes numériques + Prog Avancée
    notes = {e.code: Decimal("15.00") if e.code == "API452" else Decimal("11.14")
             for e in mdef.elements}
    out = ac.module_after_rat(mdef, notes, "2A")
    assert out.decision == "VRAT"
    assert out.final == "11.00"          # Art. 9 cap at the prépa bar
    assert Decimal(out.moy) > Decimal("11")   # true weighted moyenne, pre-cap
    assert out.coeff_assumed is False


def test_module_after_rat_element_floor_blocks_validation():
    mdef = ac.module_def_for("API452")
    notes = {e.code: Decimal("6.5") if e.code == "API451" else Decimal("18.0")
             for e in mdef.elements}
    out = ac.module_after_rat(mdef, notes, "2A")
    assert out.decision == "NV"          # element < 7 kills it (Art. 6)
    assert out.final == out.moy          # no cap when not validated


def test_annotate_fills_gaps_and_respects_official_values():
    from schoolapp.models import ModuleGrade, StudentData, StudentProfile
    data = StudentData(
        profile=StudentProfile(niveau="2A"),
        element_grades=[
            _elem("API421", cc="16.25", ex="6.0", moy="9.08", rat="14.5", decision="RAT"),
            _elem("API451", cc="", ex="6.75", moy="11.14", decision="VORD"),
            _elem("API452", cc="13.5", ex="6.5", moy="8.6", rat="15.0", decision="RAT"),
            # official SR already published -> engine must NOT touch it
            _elem("API411", moy="13.43", rat="10.0", moy_sr="13.43", decision="VORD"),
        ],
        module_grades=[ModuleGrade(code="API45", au="24/25", moy="", decision="")],
    )
    lines = ac.annotate_student_data(data)
    by_code = {e.code: e for e in data.element_grades}
    assert by_code["API421"].moy_sr_computed == "15.03"
    assert by_code["API452"].moy_sr_computed == "15.00"
    assert by_code["API452"].decision_computed == "VRAT"
    assert by_code["API411"].moy_sr_computed == ""   # official value won
    assert by_code["API451"].moy_sr_computed == ""   # no RAT taken
    mod = data.module_grades[0]
    assert mod.decision_computed == "VRAT" and mod.moy_computed == "11.00"
    assert any("API421" in ln for ln in lines) and any("API452" in ln for ln in lines)


def test_overlay_snapshot_rows_fills_computed_cells():
    headers = ["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    rows = [
        ["API411", "11.5", "14.25", "", "13.43", "", "", "13.43", "VORD"],
        ["API421", "16.25", "6.0", "", "9.08", "14.5", "", "9.08", "RAT"],
    ]
    new_rows, lines = ac.overlay_snapshot_rows(headers, rows, "S4")
    assert rows[1][6] == ""                      # input untouched (copy)
    assert new_rows[0] == rows[0]                # VORD row untouched
    idx = {h: i for i, h in enumerate(headers)}
    assert new_rows[1][idx["MoySR"]] == "15.03*"
    assert new_rows[1][idx["Moy"]] == "15.03*"
    assert new_rows[1][idx["Dec"]].endswith("*") and "V" in new_rows[1][idx["Dec"]]
    assert lines and "API421" in lines[0]


def test_overlay_leaves_published_sr_alone():
    headers = ["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    rows = [["API421", "16.25", "6.0", "", "9.08", "14.5", "12.00", "12.00", "VRAT"]]
    new_rows, lines = ac.overlay_snapshot_rows(headers, rows, "S4")
    assert new_rows == rows and lines == []


def test_annotate_is_noop_without_rat_notes():
    from schoolapp.models import StudentData, StudentProfile
    data = StudentData(profile=StudentProfile(niveau="2A"),
                       element_grades=[_elem("API411", moy="13.43", decision="VORD")])
    assert ac.annotate_student_data(data) == []
    assert data.element_grades[0].moy_sr_computed == ""
