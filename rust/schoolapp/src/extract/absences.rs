//! Absences, the per-element summary and sanctions (`schoolapp/extractors/absences.py`).

use scraper::Html;

use super::tables::{TABLE, TD, TR, row_map, table_by_headers, text_of};
use crate::models::{Absence, Raw, Sanction};

pub const ABSENCE_SIGNATURE: &[&str] = &["Element", "Date", "Seance"];
pub const SUMMARY_SIGNATURE: &[&str] = &["CodeElem", "Non Justifiée", "Justifiée"];

/// The absence log table, one row per absence event.
pub fn parse_absences(html: &str) -> Vec<Absence> {
    let Some((headers, rows)) = table_by_headers(html, ABSENCE_SIGNATURE) else {
        return Vec::new();
    };
    // `{h: i for i, h in enumerate(headers)}`: the last column of a name wins.
    let cell = |row: &[String], key: &str| -> String {
        headers
            .iter()
            .rposition(|h| h == key)
            .and_then(|i| row.get(i).cloned())
            .unwrap_or_default()
    };
    rows.iter()
        .filter(|r| !cell(r, "Element").is_empty())
        .map(|r| {
            let justif = cell(r, "Justif").trim().to_lowercase();
            Absence {
                element: cell(r, "Element"),
                date: cell(r, "Date").split(' ').next().unwrap_or_default().to_string(),
                seance: cell(r, "Seance"),
                justified: matches!(justif.as_str(), "true" | "1" | "oui" | "yes"),
                remarks: cell(r, "Remarques"),
                raw: row_map(&headers, r),
            }
        })
        .collect()
}

/// The per-element counts table on /absence/bilan (CodeElem, Intitulé, counts).
pub fn parse_absence_summary(html: &str) -> Vec<Raw> {
    let Some((headers, rows)) = table_by_headers(html, SUMMARY_SIGNATURE) else {
        return Vec::new();
    };
    rows.iter()
        .filter(|r| r.first().is_some_and(|c| !c.is_empty()))
        .map(|r| row_map(&headers, r))
        .collect()
}

/// Loose two-column key/value table (counts and the sanction message).
pub fn parse_sanctions(html: &str) -> Vec<Sanction> {
    let doc = Html::parse_document(html);
    for table in doc.select(&TABLE) {
        let pairs: Vec<(String, String)> = table
            .select(&TR)
            .filter_map(|tr| {
                let tds: Vec<String> = tr.select(&TD).map(text_of).collect();
                (tds.len() >= 2 && !tds[0].is_empty()).then(|| (tds[0].clone(), tds[1].clone()))
            })
            .collect();
        if !pairs.is_empty() {
            return pairs
                .into_iter()
                .map(|(key, value)| Sanction {
                    raw: Raw::from([("key".to_string(), key.clone()), ("value".to_string(), value.clone())]),
                    key,
                    value,
                })
                .collect();
        }
    }
    Vec::new()
}
