mod common;

use common::golden;
use pretty_assertions::assert_eq;
use schoolapp::json::{to_python_compact_json, to_store_json};
use schoolapp::models::*;

#[test]
fn defaults_serialize_like_python_dataclasses() {
    assert_eq!(to_store_json(&StudentProfile::default()), golden("models/StudentProfile.json"));
    assert_eq!(to_store_json(&ElementGrade::default()), golden("models/ElementGrade.json"));
    assert_eq!(to_store_json(&ModuleGrade::default()), golden("models/ModuleGrade.json"));
    assert_eq!(to_store_json(&SemesterResult::default()), golden("models/SemesterResult.json"));
    assert_eq!(to_store_json(&YearResult::default()), golden("models/YearResult.json"));
    assert_eq!(to_store_json(&DiplomaResult::default()), golden("models/DiplomaResult.json"));
    assert_eq!(to_store_json(&Absence::default()), golden("models/Absence.json"));
    assert_eq!(to_store_json(&Sanction::default()), golden("models/Sanction.json"));
    assert_eq!(to_store_json(&CourseEnrollment::default()), golden("models/CourseEnrollment.json"));
    assert_eq!(to_store_json(&MarkStatistics::default()), golden("models/MarkStatistics.json"));
    assert_eq!(to_store_json(&Document::default()), golden("models/Document.json"));
    assert_eq!(to_store_json(&StudentData::default()), golden("models/StudentData.json"));
}

#[test]
fn non_ascii_stays_raw_utf8() {
    let p = StudentProfile {
        prenom: "Yassine".into(),
        nom_ar: "العيدوس".into(),
        filiere: "Génie".into(),
        ..Default::default()
    };
    let out = to_store_json(&p);
    assert!(out.contains("\"nom_ar\": \"العيدوس\""), "{out}");
    assert!(out.contains("Génie") && !out.contains("\\u"), "{out}");
}

#[test]
fn compact_json_matches_python_default_separators() {
    let v = serde_json::json!({"headers": ["a", "b"], "rows": [["x", "é"]]});
    assert_eq!(to_python_compact_json(&v), r#"{"headers": ["a", "b"], "rows": [["x", "é"]]}"#);
}
