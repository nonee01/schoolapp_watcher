//! Element and module marks (`schoolapp/extractors/grades.py`).

use super::tables::{field, first_nonempty, row_map, table_by_headers};
use crate::models::{ElementGrade, ModuleGrade};

pub const ELEMENT_SIGNATURE: &[&str] = &["CodeElem", "AU", "Moy"];
pub const MODULE_SIGNATURE: &[&str] = &["CodeMod", "AU", "Moy"];

/// Element marks table: same shape on /noteselem-encours (`Dec`) and /noteselem (`Decision`).
pub fn parse_element_grades(html: &str) -> Vec<ElementGrade> {
    let Some((headers, rows)) = table_by_headers(html, ELEMENT_SIGNATURE) else {
        return Vec::new();
    };
    rows.iter()
        .map(|r| row_map(&headers, r))
        .filter(|raw| !field(raw, "CodeElem").is_empty())
        .map(|raw| ElementGrade {
            code: field(&raw, "CodeElem"),
            au: field(&raw, "AU"),
            cc: field(&raw, "CC"),
            ex: field(&raw, "EX"),
            tp: field(&raw, "TP"),
            moy_so: field(&raw, "MoySO"),
            rat: field(&raw, "RAT"),
            moy_sr: field(&raw, "MoySR"),
            moy: field(&raw, "Moy"),
            decision: first_nonempty(&raw, &["Dec", "Decision"]),
            raw,
            ..Default::default()
        })
        .collect()
}

/// Module results: /notesmod-encours (`Dec`) and /notesmod (`Decision`, extra `PJ` kept in raw).
pub fn parse_module_grades(html: &str) -> Vec<ModuleGrade> {
    let Some((headers, rows)) = table_by_headers(html, MODULE_SIGNATURE) else {
        return Vec::new();
    };
    rows.iter()
        .map(|r| row_map(&headers, r))
        .filter(|raw| !field(raw, "CodeMod").is_empty())
        .map(|raw| ModuleGrade {
            code: field(&raw, "CodeMod"),
            au: field(&raw, "AU"),
            moy: field(&raw, "Moy"),
            decision: first_nonempty(&raw, &["Dec", "Decision"]),
            raw,
            ..Default::default()
        })
        .collect()
}
