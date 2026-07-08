"""Promotion distribution reconstruction from the rank(note) sweep."""

from schoolapp import promo


def _probe_for(notes):
    """Emulate the elemstat endpoint: rank = 1 + #students strictly above note."""
    return lambda v: 1 + sum(1 for n in notes if n > v)


def test_reconstruct_recovers_every_note_with_multiplicity():
    notes = [20.0, 18.5, 18.5, 12.0, 12.0, 12.0, 5.25, 0.0]  # 8 students
    steps = dict(promo.reconstruct(_probe_for(notes), lo=-1, hi=20.5))
    assert steps[20.0] == 1
    assert steps[18.5] == 2
    assert steps[12.0] == 3
    assert steps[5.25] == 1
    assert steps[0.0] == 1
    assert sum(steps.values()) == len(notes)


def test_reconstruct_handles_dense_two_decimal_notes():
    notes = [14.93, 14.93, 9.08, 9.07, 0.0]
    steps = dict(promo.reconstruct(_probe_for(notes), lo=-1, hi=20.5))
    assert steps[14.93] == 2 and steps[9.08] == 1 and steps[9.07] == 1
    assert sum(steps.values()) == 5


def test_expand_to_rows_is_sorted_best_first():
    steps = [(8.0, 1), (15.5, 2), (20.0, 1)]
    rows = promo.expand_to_rows("API421", "NoteRAT", steps)
    assert [r["note"] for r in rows] == ["20.00", "15.50", "15.50", "8.00"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4]
    assert all(r["element"] == "API421" and r["eval"] == "NoteRAT" for r in rows)


def _steps():
    # 6 students: notes 2.0×1, 8.0×2, 12.5×2, 19.0×1
    return [(2.0, 1), (8.0, 2), (12.5, 2), (19.0, 1)]


def test_histogram_rows_bins_by_width_with_percent_and_cumulative():
    rows = promo.histogram_rows("S1", "semester", "MoySem", _steps(), width=5.0)
    # bins from floor(2)=0 -> ceil(19)=20 in steps of 5: [0,5),[5,10),[10,15),[15,20]
    by_bin = {(r["bin_low"], r["bin_high"]): r for r in rows}
    assert by_bin[(0.0, 5.0)]["count"] == 1   # 2.0
    assert by_bin[(5.0, 10.0)]["count"] == 2  # 8.0×2
    assert by_bin[(10.0, 15.0)]["count"] == 2 # 12.5×2
    assert by_bin[(15.0, 20.0)]["count"] == 1 # 19.0 (top bin closed)
    assert round(by_bin[(5.0, 10.0)]["percent"], 2) == 33.33
    assert rows[-1]["cumulative"] == 6
    assert all(r["code"] == "S1" and r["eval"] == "MoySem" for r in rows)


def test_distribution_rows_are_exact_ground_truth_best_first():
    rows = promo.distribution_rows("S1", "semester", "MoySem", _steps())
    assert [r["note"] for r in rows] == ["19.00", "12.50", "8.00", "2.00"]
    assert [r["count"] for r in rows] == [1, 2, 2, 1]
    assert [r["rank_top"] for r in rows] == [1, 2, 4, 6]  # rank of the best in each note


def test_summary_row_reports_effectif_recovered_and_median():
    aggr = {"Moyenne promo": "10.5", "Min": "2.0", "Max": "19.0",
            "Ecart type": "5.0", "Effectif": "6"}
    row = promo.summary_row("S1", "semester", "MoySem", _steps(), aggr,
                            your_note="12.5", your_rank="3")
    assert row["effectif"] == 6 and row["recovered"] == 6
    assert row["moyenne_promo"] == "10.5" and row["median"] == 10.25
    assert row["your_note"] == "12.5" and row["your_rank"] == "3"


def test_student_rows_carry_level_and_code():
    rows = promo.student_rows("2A", "year", "MoyAn", [(8.0, 1), (15.0, 1)])
    assert rows[0] == {"code": "2A", "level": "year", "eval": "MoyAn",
                       "rank": 1, "note": "15.00"}
