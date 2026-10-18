mod common;

use common::{fixture, golden};
use schoolapp::extract::{
    build_documents, parse_diploma, parse_mark_statistics, parse_profile, parse_semester_results,
    parse_year_results,
};
use schoolapp::json::to_store_json;

fn check<T: serde::Serialize>(got: &T, golden_path: &str) {
    pretty_assertions::assert_eq!(to_store_json(got), golden(golden_path), "{golden_path}");
}

#[test]
fn semester_and_year_results() {
    check(&parse_semester_results(&fixture("semesters")), "extract/semesters__parse_semester_results.json");
    check(&parse_year_results(&fixture("years")), "extract/years__parse_year_results.json");
}

#[test]
fn diploma_page() {
    check(&parse_diploma(&fixture("diploma")), "extract/diploma__parse_diploma.json");
}

#[test]
fn empty_diploma_page() {
    check(&parse_diploma(&golden("synthetic/empty_diploma.html")), "synthetic/empty_diploma__parse_diploma.json");
}

#[test]
fn profile_page() {
    check(&parse_profile(&fixture("profile")), "extract/profile__parse_profile.json");
}

#[test]
fn profile_edge_cases() {
    check(&parse_profile(&golden("synthetic/duplicate_labels.html")), "synthetic/duplicate_labels__parse_profile.json");
    check(&parse_profile(&golden("synthetic/arabic_profile.html")), "synthetic/arabic_profile__parse_profile.json");
}

#[test]
fn stats_popup() {
    check(
        &parse_mark_statistics(&fixture("stats"), "ELEM1", "MoyElem", "2025/2026", "12.50"),
        "extract/stats__parse_mark_statistics.json",
    );
    assert!(parse_mark_statistics("<html></html>", "", "", "", "").is_none());
}

#[test]
fn documents_from_results() {
    let years = parse_year_results(&fixture("years"));
    let sems = parse_semester_results(&fixture("semesters"));
    check(&build_documents(&years, &sems), "extract/documents.json");
}
