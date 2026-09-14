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


def test_explain_element_full_rattrapage_story():
    items = [
        {"code": "API421", "au": "24/25", "cc": "16.25", "ex": "6.0", "tp": "",
         "moy": "9.08", "rat": "14.5", "moy_sr": "", "decision": "RAT",
         "moy_sr_computed": "15.03", "decision_computed": "VRAT"},
    ]
    exp = ac.explain_element("api421", items)
    assert exp["code"] == "API421"
    arts = [s["article"] for s in exp["steps"]]
    assert "Art. 4" in arts[0] and any("Art. 7" in a for a in arts)
    art7 = next(s for s in exp["steps"] if "Art. 7" in s["article"])
    assert art7["value"] == "15.03" and art7["official"] is False
    assert ac.explain_element("NOPE", items) is None


def test_explain_element_without_rat_is_art4_only():
    items = [{"code": "API411", "au": "24/25", "cc": "11.5", "ex": "14.25", "tp": "",
              "moy": "13.43", "rat": "", "moy_sr": "", "decision": "VORD",
              "moy_sr_computed": "", "decision_computed": ""}]
    exp = ac.explain_element("API411", items)
    assert len(exp["steps"]) == 1 and "Art. 4" in exp["steps"][0]["article"]


def _mod(code, moy="", decision="", moy_c="", dec_c=""):
    return {"code": code, "moy": moy, "decision": decision,
            "moy_computed": moy_c, "decision_computed": dec_c}


def test_year_outcome_art11_conditions():
    mods = [_mod("API41", "13.43", "VORD"),
            _mod("API42", "", "RAT", moy_c="11.00", dec_c="VRAT"),   # computed VRAT counts
            _mod("API44", "14.98", "VORD"),
            _mod("API45", "8.60", "NV")]
    out = ac.year_outcome(mods, "2A")
    assert out["non_valides"] == ["API45"]
    assert out["conditions"]["nv_count"] is True        # 1 NV <= 2
    assert out["conditions"]["floor"] is True           # all >= 7
    assert out["computed"] is True                      # used a *_computed value
    assert isinstance(out["would_validate"], bool)


def test_year_outcome_floor_and_count_breaches():
    mods = [_mod("API41", "6.50", "NV"), _mod("API42", "10.00", "NV"),
            _mod("API44", "10.50", "NV"), _mod("API45", "15.00", "VORD")]
    out = ac.year_outcome(mods, "2A")
    assert out["conditions"]["nv_count"] is False       # 3 NV > 2
    assert "API41" in out["floor_breach"]               # 6.50 < 7
    assert out["would_validate"] is False
    assert out["computed"] is False


# ── CoefCC/CoefEX are per element, not a fixed 0.3/0.7 ────────────────────
# Real 3A GE-DI S1 values from the plan d'études (/plan-etudes-view/modules).

def test_element_with_no_cc_ignores_cc_entirely():
    """PEI132 RDM: CoefCC 0.0 / CoefEX 1.0 - the exam mark IS the écrit mark."""
    got = ac.element_moy_so(cc=Decimal("18.0"), ex=Decimal("11.0"), tp=None,
                            c1=Decimal("1.0"), c2=Decimal("0.0"),
                            cc_w=Decimal("0.0"), ex_w=Decimal("1.0"))
    assert got == Decimal("11.0")
    # the old hardcoded split would have invented 13.1 out of a CC that does not count
    assert ac.element_moy_so(cc=Decimal("18.0"), ex=Decimal("11.0"), tp=None,
                             c1=Decimal("1.0"), c2=Decimal("0.0")) != got


def test_language_element_uses_04_06_split():
    """LE11 Langue Anglaise: CoefCC 0.4 / CoefEX 0.6."""
    got = ac.element_moy_so(cc=Decimal("15.0"), ex=Decimal("10.0"), tp=None,
                            c1=Decimal("1.0"), c2=Decimal("0.0"),
                            cc_w=Decimal("0.4"), ex_w=Decimal("0.6"))
    assert got == Decimal("12.0")


def test_tp_weighted_by_coeftp_digital_skills():
    """PS1: CoefEcrit 1.0, CoefTP 1.0 - the TP is half the element."""
    got = ac.element_moy_so(cc=None, ex=Decimal("10.0"), tp=Decimal("16.0"),
                            c1=Decimal("1.0"), c2=Decimal("1.0"),
                            cc_w=Decimal("0.0"), ex_w=Decimal("1.0"))
    assert got == Decimal("13.0")


def test_no_cc_element_carries_nothing_into_rattrapage():
    """Art. 7 with CoefCC 0: the rattrapage session is just Rat."""
    sr = ac.element_moy_sr(moy_so=Decimal("7.0"), cc=Decimal("18.0"),
                           rat=Decimal("11.0"),
                           cc_w=Decimal("0.0"), ex_w=Decimal("1.0"))
    assert sr == Decimal("11.0")


def test_default_weights_unchanged_for_ordinary_elements():
    """Elements that really are 0.3/0.7 must behave exactly as before."""
    assert ac.element_moy_so(cc=Decimal("12.0"), ex=Decimal("12.0"), tp=None,
                             c1=Decimal("1.0"), c2=Decimal("0.0")) == Decimal("12.0")


def test_catalog_zero_coefficient_is_not_replaced_by_default():
    """Decimal('0.0') is falsy: `parse_note(x) or 0.3` used to invent a CC."""
    assert ac._coef("0.0", 0.3) == 0.0
    assert ac._coef("0.4", 0.3) == 0.4
    assert ac._coef("", 0.3) == 0.3      # genuinely blank -> default
    assert ac._coef("--", 0.3) == 0.3
    assert ac._coef(None, 0.3) == 0.3


# ── semester_weights ──────────────────────────────────────────────────────

def test_semester_weights_sum_to_total_coefficient():
    from schoolapp.presets import modules_for_semester
    defs = modules_for_semester("S5")
    rows = ac.semester_weights(defs)
    assert len(rows) == 14
    assert round(sum(r["weight"] for r in rows), 6) == 30.0


def test_semester_weights_split_a_module_by_coefelem():
    """TC11 coef 5 splits 2.0/1.0 between its elements, not 50/50.

    3A is S5/S6 in the marks pages, even though the plan d'études page
    labels the same programme S1/S2.
    """
    from schoolapp.presets import modules_for_semester
    rows = {r["code"]: r for r in ac.semester_weights(modules_for_semester("S5"))}
    assert round(rows["TC111"]["weight"], 2) == 3.33   # CoefElem 2.0 of 3.0
    assert round(rows["TC112"]["weight"], 2) == 1.67   # CoefElem 1.0 of 3.0
    assert rows["TC111"]["weight"] > rows["PEI112"]["weight"]  # heaviest element


def test_semester_weights_flags_the_element_with_nothing_banked():
    from schoolapp.presets import modules_for_semester
    rows = ac.semester_weights(modules_for_semester("S5"))
    nothing = [r["code"] for r in rows if not r["banked"]]
    assert nothing == ["PEI141"]          # no CC, no TP: pure exam
    tp_only = sorted(r["code"] for r in rows if r["banked"] == "TP")
    assert tp_only == ["PEI131", "PEI132", "PS1"]
    assert rows[[r["code"] for r in rows].index("PS1")]["tp_share"] == 0.5


# ── pinned against real published marks (API35, 2A S3, AU 2025-2026) ──────
# Read off /student/noteselem-encours on 2026-09-13. These are the portal's
# own numbers, so a regression here means we disagree with the institution.

def test_api352_matches_the_portal_including_half_up_rounding():
    """CC 12.75, EX 7.0 -> SO 8.73 ; RAT 7.5 -> SR 9.08 (0.3·CC + 0.7·Rat)."""
    so = ac.element_moy_so(cc=Decimal("12.75"), ex=Decimal("7.0"), tp=None,
                           c1=Decimal("1"), c2=Decimal("0"))
    assert ac.fmt_note(so) == "8.73"
    sr = ac.element_moy_sr(moy_so=so, cc=Decimal("12.75"), rat=Decimal("7.5"))
    # 0.3*12.75 + 0.7*7.5 = 9.075 -> the portal publishes 9.08, not 9.07
    assert ac.fmt_note(sr) == "9.08"


def test_api351_keeps_the_ordinary_session_when_rattrapage_is_worse():
    """Art. 7 takes the max: a bad RAT never lowers an existing MoySO."""
    so = ac.element_moy_so(cc=Decimal("11.0"), ex=Decimal("10.0"), tp=None,
                           c1=Decimal("1"), c2=Decimal("0"))
    assert ac.fmt_note(so) == "10.30"
    sr = ac.element_moy_sr(moy_so=so, cc=Decimal("11.0"), rat=Decimal("6.0"))
    assert ac.fmt_note(sr) == "10.30"   # portal keeps 10.3, not the 7.5 rattrapage


# ── the presets ARE the portal ────────────────────────────────────────────
# Transcribed from /plan-etudes-view/modules (3A / GE-DI / S1) and re-verified
# against the live page on 2026-09-13. If the school republishes the plan
# d'études these break, which is the point: the whole revision plan is
# weighted off these numbers.

PORTAL_S5 = {
    # code:    (CoefCC, CoefEX, CoefEcrit, CoefTP, CoefElem)
    "LE11":    (0.4, 0.6, 1.0, 0.0, 1.0),
    "LE12":    (0.4, 0.6, 1.0, 0.0, 1.0),
    "PEI111":  (0.3, 0.7, 1.0, 0.5, 1.5),
    "PEI112":  (0.3, 0.7, 1.0, 0.5, 1.5),
    "PEI121":  (0.3, 0.7, 1.0, 0.5, 1.5),
    "PEI122":  (0.3, 0.7, 1.0, 0.5, 1.5),
    "PEI131":  (0.0, 1.0, 1.0, 0.5, 1.5),
    "PEI132":  (0.0, 1.0, 1.0, 0.5, 1.5),
    "PEI141":  (0.0, 1.0, 1.0, 0.0, 1.0),
    "PEI142":  (0.3, 0.7, 1.0, 0.0, 1.0),
    "PEI143":  (0.3, 0.7, 1.0, 0.0, 1.0),
    "PS1":     (0.0, 1.0, 1.0, 1.0, 2.0),
    "TC111":   (0.3, 0.7, 1.5, 0.5, 2.0),
    "TC112":   (0.3, 0.7, 1.0, 0.0, 1.0),
}

PORTAL_MODULES_S5 = {
    "LE1":   ("Langues Etrangères (Anglais, Français)", 3.0),
    "PEI11": ("Electronique de puissance et Electrotechnique", 5.0),
    "PEI12": ("Traitement de signal et Automatique", 5.0),
    "PEI13": ("Dimensionnement des structures", 4.0),
    "PEI14": ("Eléments et architectures de machines et Fabrication Additive et MMC", 5.0),
    "PS1":   ("Digital Skills - Excel Avancé", 3.0),
    "TC11":  ("Méthodes numériques et Statistiques", 5.0),
}


def test_every_s5_coefficient_matches_the_portal():
    from schoolapp.presets import modules_for_semester
    got = {e.code: (e.coef_cc, e.coef_ex, e.coef_ecrit, e.coef_tp, e.coef_eelem)
           for m in modules_for_semester("S5") for e in m.elements}
    assert got == PORTAL_S5


def test_every_s5_module_matches_the_portal():
    from schoolapp.presets import modules_for_semester
    got = {m.code: (m.title, m.coef_mod) for m in modules_for_semester("S5")}
    assert got == PORTAL_MODULES_S5
    for m in modules_for_semester("S5"):
        assert (m.seuil, m.eliminatoire) == (12.0, 8.0)   # cycle ingénieur


def test_element_shares_sum_to_one_and_match_art_4():
    from schoolapp.presets import modules_for_semester
    for m in modules_for_semester("S5"):
        for e in m.elements:
            sh = ac.element_shares(e)
            assert round(sum(sh.values()), 9) == 1.0, e.code
    by = {e.code: ac.element_shares(e)
          for m in modules_for_semester("S5") for e in m.elements}
    # CoefCC 0.3 is NOT 30% once a TP shares the element
    assert round(by["PEI111"]["test"], 4) == 0.20
    assert round(by["PEI111"]["tp"], 4) == round(1/3, 4)
    # no TP, so CoefCC passes through unchanged
    assert round(by["PEI142"]["test"], 4) == 0.30
    # the two extremes
    assert by["PEI141"]["exam"] == 1.0          # nothing but the exam
    assert by["PS1"]["tp"] == 0.5               # half of it unrecoverable


def test_niveau_for_semester_spans_the_prepa_boundary():
    assert [ac.niveau_for_semester(s) for s in ("S1", "S2", "S3", "S4", "S5", "S6")] == \
        ["1A", "1A", "2A", "2A", "3A", "3A"]
    assert ac.niveau_for_semester("s5") == "3A"
    assert ac.niveau_for_semester("") == "2A"      # unreadable label: prépa bars, as before


def test_overlay_takes_its_bars_from_the_semesters_own_year():
    """The niveau argument defaulted to "2A", so a 3A table was validated against
    the prépa bars (11/7/11) instead of the cycle ingénieur's (12/8/12).

    Presets carry their own seuil, so this only shows on a module the presets do
    not describe - which is exactly when the fallback is what decides.
    """
    headers = ["CodeElem", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec"]
    rows = [["ZZZ11", "10.0", "6.0", "", "9.0", "11.5", "", "9.0", "RAT"]]
    idx = {h: i for i, h in enumerate(headers)}

    prepa, _ = ac.overlay_snapshot_rows(headers, rows, "S4")
    ingenieur, _ = ac.overlay_snapshot_rows(headers, rows, "S5")

    assert prepa[0][idx["MoySR"]] == "11.50*" and ingenieur[0][idx["MoySR"]] == "11.50*"
    assert prepa[0][idx["Dec"]] == "VRAT*"     # 11.50 clears the prépa bar of 11
    assert ingenieur[0][idx["Dec"]] == "NV*"   # and misses the cycle ingénieur bar of 12
    # an explicit niveau still wins over the label
    forced, _ = ac.overlay_snapshot_rows(headers, rows, "S5", niveau="2A")
    assert forced[0][idx["Dec"]] == "VRAT*"


def test_a_real_zero_is_not_swapped_for_the_fallback_column():
    """`parse_note(a) or parse_note(b)` read column b whenever a held a real 0,
    and 0 is exactly what an absence scores, so the walkthrough quietly explained
    a different mark than the one on the portal."""
    assert ac._first_note("0.00", "12.00") == Decimal("0.00")
    assert ac._first_note("", "12.00") == Decimal("12.00")
    assert ac._first_note("--", None) is None

    # A zero in the session ordinaire must survive: the fallback column holds the
    # post-rattrapage moyenne, which is a different number for a different session.
    items = [{"code": "API421", "au": "2025-2026", "cc": "16.25", "ex": "0.00",
              "tp": "", "moy_so": "0.00", "moy": "9.08", "rat": "14.5",
              "moy_sr": "", "decision": "RAT"}]
    exp = ac.explain_element("API421", items)
    assert exp["steps"][0]["value"] == "0.00"          # the zero, not the 9.08


def test_art7_formula_matches_the_elements_own_coefficients():
    """The value beside it came from elem_weights, but the formula string was a
    fixed 0.3/0.7 - so every CoefCC = 0 element was explained with a contrôle
    continu term that neither the règlement nor the number uses."""
    assert ac._sr_formula("PEI141") == "max(SO, Rat) - pas de contrôle continu (CoefCC = 0)"
    assert ac._sr_formula("LE11") == "max(SO, max(0.4·CC + 0.6·Rat, Rat))"
    assert ac._sr_formula("API421") == "max(SO, max(0.3·CC + 0.7·Rat, Rat))"
    assert ac._sr_formula("ZZZ99") == "max(SO, max(0.3·CC + 0.7·Rat, Rat))"

    items = [{"code": "PEI141", "au": "2026-2027", "cc": "", "ex": "7.0", "tp": "",
              "moy": "7.0", "moy_so": "7.0", "rat": "11.0", "moy_sr": "",
              "decision": "RAT"}]
    art7 = ac.explain_element("PEI141", items)["steps"][1]
    assert "·CC" not in art7["formula"]          # no contrôle continu term at all
    assert art7["value"] == "11.00"                     # max(SO 7.0, Rat 11.0)


def test_art4_reads_the_session_ordinaire_column_not_the_final_moyenne():
    """On a rattrapé element the portal's "Moy" is the post-rattrapage value, so
    reading it first printed the SR under Art. 4 and fed max(SO, ...) a note the
    ordinary session never produced. API352 is the published case: CC 12.75,
    EX 7.0 -> 0.3·12.75 + 0.7·7.0 = 8.73, while Moy carries the 9.08 after RAT."""
    items = [{"code": "API352", "au": "2025-2026", "cc": "12.75", "ex": "7.0",
              "tp": "", "moy_so": "8.73", "rat": "7.5", "moy_sr": "9.08",
              "moy": "9.08", "decision": "NV"}]
    steps = ac.explain_element("API352", items)["steps"]
    assert steps[0]["article"] == "Art. 4" and steps[0]["value"] == "8.73"
    assert steps[1]["article"] == "Art. 7" and steps[1]["value"] == "9.08"
