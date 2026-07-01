import pytest

from schoolapp.extractors._tables import (
    normalize_cell,
    extract_table,
    table_by_headers,
    fingerprint,
)

TABLE_HTML = """
<table>
  <tr><th>CodeElem</th><th>Moy</th></tr>
  <tr><td>API101</td><td> 12.5 </td></tr>
  <tr><td>API102</td><td>9</td></tr>
</table>
"""


def test_normalize_cell_collapses_whitespace():
    assert normalize_cell("  hello \n  world ") == "hello world"


def test_extract_table_reads_headers_and_rows():
    headers, rows = extract_table(TABLE_HTML)
    assert headers == ["CodeElem", "Moy"]
    assert rows == [["API101", "12.5"], ["API102", "9"]]


def test_extract_table_raises_when_no_table():
    with pytest.raises(RuntimeError):
        extract_table("<p>no table here</p>")


def test_table_by_headers_matches_subset_or_none():
    headers, rows = table_by_headers(TABLE_HTML, {"CodeElem"})
    assert rows[0] == ["API101", "12.5"]
    assert table_by_headers(TABLE_HTML, {"Nope"}) is None


def test_fingerprint_is_stable_and_sensitive():
    fp1 = fingerprint(["A"], [["1"]])
    fp2 = fingerprint(["A"], [["1"]])
    fp3 = fingerprint(["A"], [["2"]])
    assert fp1 == fp2
    assert fp1 != fp3
