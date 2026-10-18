//! The /notes-stat popups (`schoolapp/extractors/stats.py`).

use std::sync::LazyLock;

use scraper::{Html, Selector};

use super::tables::{TABLE, TR, text_of};
use crate::models::{MarkStatistics, Raw};

fn selector(css: &str) -> Selector {
    Selector::parse(css).expect("static selector")
}

static STAT: LazyLock<Selector> = LazyLock::new(|| selector("div.stat"));
static P: LazyLock<Selector> = LazyLock::new(|| selector("p"));
static CELL: LazyLock<Selector> = LazyLock::new(|| selector("th, td"));

/// `div.stat` holding a `<p>` title and a th/td statistics table; `None` when
/// the popup has neither.
pub fn parse_mark_statistics(html: &str, element: &str, eval_kind: &str, au: &str, note: &str) -> Option<MarkStatistics> {
    let doc = Html::parse_document(html);
    let scope = doc.select(&STAT).next().unwrap_or_else(|| doc.root_element());
    let title = scope.select(&P).next().map(text_of).unwrap_or_default();
    let rows: Vec<Vec<String>> = scope
        .select(&TABLE)
        .next()
        .map(|table| {
            table
                .select(&TR)
                .map(|tr| tr.select(&CELL).map(text_of).collect::<Vec<_>>())
                .filter(|cells| cells.iter().any(|c| !c.is_empty()))
                .collect()
        })
        .unwrap_or_default();
    if rows.is_empty() && title.is_empty() {
        return None;
    }
    Some(MarkStatistics {
        element: element.into(),
        eval_kind: eval_kind.into(),
        au: au.into(),
        note: note.into(),
        raw: Raw::from([("title".to_string(), title.clone())]),
        title,
        rows,
    })
}
