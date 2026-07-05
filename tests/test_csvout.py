"""CSV serialization: flat resources + pivoted stats popups."""

import csv
import io

from schoolapp import csvout


def _parse(text):
    return list(csv.reader(io.StringIO(text)))


def test_rows_to_csv_infers_columns_and_skips_raw():
    rows = [
        {"code": "API311", "moy": "14.93", "decision": "VORD", "raw": {"x": "y"}},
        {"code": "API421", "moy": "9.08", "decision": "RAT", "raw": {}},
    ]
    parsed = _parse(csvout.rows_to_csv(rows))
    assert parsed[0] == ["code", "moy", "decision"]   # raw excluded
    assert parsed[1] == ["API311", "14.93", "VORD"]
    assert parsed[2][0] == "API421"


def test_rows_to_csv_explicit_columns_and_flattening():
    rows = [{"element": "API311", "justified": True, "tags": ["a", "b"]}]
    text = csvout.rows_to_csv(rows, columns=["element", "justified", "tags"])
    parsed = _parse(text)
    assert parsed[0] == ["element", "justified", "tags"]
    assert parsed[1] == ["API311", "oui", "a; b"]


def test_rows_to_csv_empty():
    assert csvout.rows_to_csv([]) == ""


def test_stats_to_csv_pivots_metrics_into_columns():
    stats = [
        {"element": "API421", "eval_kind": "NoteRAT", "au": "2025-2026", "note": "14.5",
         "rows": [["Votre note", "14.5"], ["Moyenne promo", "11.2"], ["Votre classement", "12"]]},
        {"element": "API311", "eval_kind": "MoyElem", "au": "2025-2026", "note": "14.93",
         "rows": [["Votre note", "14.93"], ["Max", "19.35"]]},
    ]
    parsed = _parse(csvout.stats_to_csv(stats))
    header = parsed[0]
    assert header[:4] == ["element", "eval_kind", "au", "note"]
    for label in ("Votre note", "Moyenne promo", "Votre classement", "Max"):
        assert label in header
    rat = parsed[1]
    row = dict(zip(header, rat))
    assert row["element"] == "API421" and row["eval_kind"] == "NoteRAT"
    assert row["Moyenne promo"] == "11.2" and row["Votre classement"] == "12"
    assert row["Max"] == ""   # this metric only exists for the other element
