//! Course enrollments (`schoolapp/extractors/courses.py`).

use super::tables::{field, row_map, table_by_headers};
use crate::models::CourseEnrollment;

pub const COURSE_SIGNATURE: &[&str] = &["CodeElem", "Statut", "Num"];

pub fn parse_courses(html: &str) -> Vec<CourseEnrollment> {
    let Some((headers, rows)) = table_by_headers(html, COURSE_SIGNATURE) else {
        return Vec::new();
    };
    rows.iter()
        .map(|r| row_map(&headers, r))
        .filter(|raw| !field(raw, "CodeElem").is_empty())
        .map(|raw| CourseEnrollment {
            code_elem: field(&raw, "CodeElem"),
            statut: field(&raw, "Statut"),
            section: field(&raw, "Section"),
            groupe: field(&raw, "Groupe"),
            sous_groupe: field(&raw, "S.Groupe"),
            num: field(&raw, "Num"),
            raw,
        })
        .collect()
}
