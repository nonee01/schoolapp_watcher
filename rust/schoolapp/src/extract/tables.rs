//! Table walking shared by every extractor (`schoolapp/extractors/_tables.py`).

use std::sync::LazyLock;

use anyhow::{Result, bail};
use scraper::{ElementRef, Html, Selector};
use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::json::to_python_compact_json;

pub type Table = (Vec<String>, Vec<Vec<String>>);

fn selector(css: &str) -> Selector {
    Selector::parse(css).expect("static selector")
}

static TABLE: LazyLock<Selector> = LazyLock::new(|| selector("table"));
static TR: LazyLock<Selector> = LazyLock::new(|| selector("tr"));
static TH: LazyLock<Selector> = LazyLock::new(|| selector("th"));
static TD: LazyLock<Selector> = LazyLock::new(|| selector("td"));

/// `" ".join(text.split())`: trim and collapse every whitespace run, `&nbsp;` included.
pub fn normalize_cell(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// BeautifulSoup's `get_text(" ", strip=True)` followed by `normalize_cell`.
pub fn text_of(element: ElementRef) -> String {
    let joined = element
        .text()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join(" ");
    normalize_cell(&joined)
}

fn headers_of(table: ElementRef) -> Vec<String> {
    table.select(&TH).map(text_of).collect()
}

/// Rows with at least one `<td>` and at least one non-empty cell.
fn rows_of(table: ElementRef) -> Vec<Vec<String>> {
    table
        .select(&TR)
        .map(|tr| tr.select(&TD).map(text_of).collect::<Vec<_>>())
        .filter(|cells| cells.iter().any(|c| !c.is_empty()))
        .collect()
}

/// The table with the most rows (the first one on ties), as headers and cell rows.
pub fn extract_table(html: &str) -> Result<Table> {
    let doc = Html::parse_document(html);
    let mut best: Option<(ElementRef, usize)> = None;
    for table in doc.select(&TABLE) {
        let rows = table.select(&TR).count();
        if best.is_none_or(|(_, most)| rows > most) {
            best = Some((table, rows));
        }
    }
    match best {
        Some((table, _)) => Ok((headers_of(table), rows_of(table))),
        None => bail!("No table found on marks page"),
    }
}

/// The first table whose header row contains every `wanted` column.
pub fn table_by_headers(html: &str, wanted: &[&str]) -> Option<Table> {
    let doc = Html::parse_document(html);
    doc.select(&TABLE).find_map(|table| {
        let headers = headers_of(table);
        wanted
            .iter()
            .all(|w| headers.iter().any(|h| h == w))
            .then(|| (headers, rows_of(table)))
    })
}

/// SHA-256 of `json.dumps({"headers", "rows"}, ensure_ascii=False, sort_keys=True)`.
pub fn fingerprint(headers: &[String], rows: &[Vec<String>]) -> String {
    #[derive(Serialize)]
    struct Payload<'a> {
        headers: &'a [String],
        rows: &'a [Vec<String>],
    }
    let text = to_python_compact_json(&Payload { headers, rows });
    hex::encode(Sha256::digest(text.as_bytes()))
}
