mod common;

use common::{fixture, golden};
use schoolapp::extract::{
    parse_absence_summary, parse_absences, parse_courses, parse_element_grades, parse_module_grades,
    parse_sanctions,
};
use schoolapp::json::to_store_json;

fn check<T: serde::Serialize>(got: &T, golden_path: &str) {
    pretty_assertions::assert_eq!(to_store_json(got), golden(golden_path), "{golden_path}");
}

#[test]
fn element_grades() {
    check(&parse_element_grades(&fixture("elements_encours")), "extract/elements_encours__parse_element_grades.json");
    check(&parse_element_grades(&fixture("elements_history")), "extract/elements_history__parse_element_grades.json");
}

#[test]
fn module_grades() {
    check(&parse_module_grades(&fixture("modules_encours")), "extract/modules_encours__parse_module_grades.json");
    check(&parse_module_grades(&fixture("modules_history")), "extract/modules_history__parse_module_grades.json");
}

#[test]
fn courses() {
    check(&parse_courses(&fixture("courses")), "extract/courses__parse_courses.json");
}

#[test]
fn absences_summary_sanctions() {
    check(&parse_absences(&fixture("absences")), "extract/absences__parse_absences.json");
    check(&parse_absence_summary(&fixture("absences")), "extract/absences__parse_absence_summary.json");
    check(&parse_sanctions(&fixture("sanctions")), "extract/sanctions__parse_sanctions.json");
}

#[test]
fn script_style_and_template_text_stay_out_of_cells() {
    check(&parse_element_grades(&golden("synthetic/script_in_cell.html")), "synthetic/script_in_cell__parse_element_grades.json");
}

#[test]
fn ragged_rows() {
    check(&parse_element_grades(&golden("synthetic/ragged_rows.html")), "synthetic/ragged_rows__parse_element_grades.json");
}

/// Python's html.parser nests unclosed cells and finds no rows here; the Rust
/// port parses them like a browser (see the Task 3 ruling in the plan ledger).
#[test]
fn unclosed_cells_parse_like_a_browser() {
    let html = "<table><tr><th>CodeElem<th>AU<th>Moy\
                <tr><td>E201<td>2025/2026<td><b>12</b>.<i>5</i>\
                <tr><td>E202&nbsp;<td>  2025/2026 <td>\n 08,75 \n</table>";
    let grades = parse_element_grades(html);
    let got: Vec<(&str, &str, &str)> = grades.iter().map(|g| (g.code.as_str(), g.au.as_str(), g.moy.as_str())).collect();
    assert_eq!(got, vec![("E201", "2025/2026", "12 . 5"), ("E202", "2025/2026", "08,75")]);
}
