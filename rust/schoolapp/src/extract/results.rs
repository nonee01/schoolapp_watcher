//! Semester, year and diploma results (`schoolapp/extractors/results.py`).

use std::sync::LazyLock;

use scraper::{ElementRef, Html, Selector};

use super::tables::{TABLE, TD, TH, TR, field, first_nonempty, normalize_cell, row_map, text_of};
use crate::models::{DiplomaResult, Raw, SemesterResult, YearResult};

pub const SEMESTER_SIGNATURE: &[&str] = &["Semestre", "Moy SEM"];
pub const YEAR_SIGNATURE: &[&str] = &["Niveau", "AU", "Moy Année"];
pub const DIPLOMA_EMPTY_MARKER: &str = "Vous n'avez pas de note de diplome";

static LINK: LazyLock<Selector> = LazyLock::new(|| Selector::parse("a[href]").expect("static selector"));

/// Header-signature table walk that also keeps each row's first `<a href>` (the relevé PDF).
fn rows_with_links(html: &str, wanted: &[&str]) -> Vec<(Raw, String)> {
    let doc = Html::parse_document(html);
    for table in doc.select(&TABLE) {
        let headers: Vec<String> = table.select(&TH).map(text_of).collect();
        if !wanted.iter().all(|w| headers.iter().any(|h| h == w)) {
            continue;
        }
        return table
            .select(&TR)
            .filter_map(|tr| {
                let cells: Vec<String> = tr.select(&TD).map(text_of).collect();
                if !cells.iter().any(|c| !c.is_empty()) {
                    return None;
                }
                let href = tr
                    .select(&LINK)
                    .next()
                    .and_then(|a| a.value().attr("href"))
                    .unwrap_or_default()
                    .to_string();
                Some((row_map(&headers, &cells), href))
            })
            .collect();
    }
    Vec::new()
}

pub fn parse_semester_results(html: &str) -> Vec<SemesterResult> {
    rows_with_links(html, SEMESTER_SIGNATURE)
        .into_iter()
        .filter(|(raw, _)| !field(raw, "Semestre").is_empty())
        .map(|(raw, releve_url)| SemesterResult {
            niveau: field(&raw, "Niveau"),
            semestre: field(&raw, "Semestre"),
            au: field(&raw, "AU"),
            moy_sem: field(&raw, "Moy SEM"),
            pj: field(&raw, "PJ"),
            decision: first_nonempty(&raw, &["Decesion", "Decision"]), // site typo
            classement: field(&raw, "Classement"),
            releve_url,
            raw,
        })
        .collect()
}

pub fn parse_year_results(html: &str) -> Vec<YearResult> {
    rows_with_links(html, YEAR_SIGNATURE)
        .into_iter()
        .filter(|(raw, _)| !field(raw, "Niveau").is_empty())
        .map(|(raw, releve_url)| YearResult {
            niveau: field(&raw, "Niveau"),
            filiere: field(&raw, "Filière"),
            au: field(&raw, "AU"),
            statut: field(&raw, "Statut"),
            moy_annee: field(&raw, "Moy Année"),
            pj: field(&raw, "PJ"),
            decision: first_nonempty(&raw, &["Decesion", "Decision"]), // site typo
            classement: field(&raw, "Classement"),
            releve_url,
            raw,
        })
        .collect()
}

/// The page saying there is no diploma mark yet is a valid state, not an error.
pub fn parse_diploma(html: &str) -> DiplomaResult {
    let doc = Html::parse_document(html);
    let mut best: Option<(ElementRef, usize)> = None;
    for table in doc.select(&TABLE) {
        let rows = table.select(&TR).count();
        if best.is_none_or(|(_, most)| rows > most) {
            best = Some((table, rows));
        }
    }
    if let Some((table, _)) = best {
        let headers: Vec<String> = table.select(&TH).map(text_of).collect();
        let rows: Vec<Raw> = table
            .select(&TR)
            .map(|tr| tr.select(&TD).map(text_of).collect::<Vec<_>>())
            .filter(|tds| tds.iter().any(|c| !c.is_empty()))
            .map(|tds| {
                if headers.is_empty() {
                    tds.into_iter().enumerate().map(|(i, v)| (i.to_string(), v)).collect()
                } else {
                    row_map(&headers, &tds)
                }
            })
            .collect();
        if !rows.is_empty() {
            return DiplomaResult {
                empty: false,
                message: None,
                rows,
                raw: Raw::from([("headers".to_string(), headers.join(" | "))]),
            };
        }
    }
    let message = doc
        .root_element()
        .descendants()
        .filter_map(|node| node.value().as_text())
        .find(|text| text.contains(DIPLOMA_EMPTY_MARKER))
        .map(|text| normalize_cell(text));
    DiplomaResult { empty: true, message, rows: Vec::new(), raw: Raw::new() }
}
