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
