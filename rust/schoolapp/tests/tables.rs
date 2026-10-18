mod common;

use common::{fixture, golden};
use pretty_assertions::assert_eq;
use schoolapp::extract::tables::{extract_table, fingerprint, normalize_cell, table_by_headers};
use schoolapp::json::to_store_json;

#[test]
fn extract_table_and_fingerprint_match_python() {
    let html = fixture("elements_encours");
    let (headers, rows) = extract_table(&html).unwrap();
    let got = to_store_json(&serde_json::json!({"headers": headers, "rows": rows}));
    assert_eq!(got, golden("extract/elements_encours__extract_table.json"));
    assert_eq!(fingerprint(&headers, &rows), golden("extract/elements_encours__fingerprint.txt").trim());
}

#[test]
fn no_table_is_the_python_error() {
    assert_eq!(extract_table("<p>rien</p>").unwrap_err().to_string(), "No table found on marks page");
}

#[test]
fn normalize_cell_collapses_unicode_whitespace() {
    assert_eq!(normalize_cell("  12,5\u{a0}\n  /20 "), "12,5 /20");
}

#[test]
fn table_by_headers_skips_tables_missing_a_column() {
    let html = "<table><tr><th>A</th></tr></table>\
                <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>";
    assert_eq!(table_by_headers(html, &["A", "B"]).unwrap().1, vec![vec!["1".to_string(), "2".into()]]);
    assert!(table_by_headers(html, &["C"]).is_none());
}
