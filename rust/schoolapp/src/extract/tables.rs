//! Table walking shared by every extractor (`schoolapp/extractors/_tables.py`).

use std::sync::LazyLock;

use anyhow::{Result, bail};
use scraper::{ElementRef, Html, Selector};
use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::json::to_python_compact_json;
use crate::models::Raw;

pub type Table = (Vec<String>, Vec<Vec<String>>);

fn selector(css: &str) -> Selector {
    Selector::parse(css).expect("static selector")
}

pub(crate) static TABLE: LazyLock<Selector> = LazyLock::new(|| selector("table"));
pub(crate) static TR: LazyLock<Selector> = LazyLock::new(|| selector("tr"));
pub(crate) static TH: LazyLock<Selector> = LazyLock::new(|| selector("th"));
pub(crate) static TD: LazyLock<Selector> = LazyLock::new(|| selector("td"));

/// `{h: row[i] if i < len(row) else "" for i, h in enumerate(headers)}`: a repeated
/// header keeps its first position and takes the last value, like a Python dict.
pub(crate) fn row_map(headers: &[String], row: &[String]) -> Raw {
    headers
        .iter()
        .enumerate()
        .map(|(i, h)| (h.clone(), row.get(i).cloned().unwrap_or_default()))
        .collect()
}

/// `raw.get(key, "")`.
pub(crate) fn field(raw: &Raw, key: &str) -> String {
    raw.get(key).cloned().unwrap_or_default()
}

/// `raw.get("Dec") or raw.get("Decision", "")`: an empty `Dec` falls through too.
pub(crate) fn first_nonempty(raw: &Raw, keys: &[&str]) -> String {
    let (last, rest) = keys.split_last().expect("at least one key");
    rest.iter()
        .find_map(|k| raw.get(*k).filter(|v| !v.is_empty()).cloned())
        .unwrap_or_else(|| field(raw, last))
}

/// `" ".join(text.split())`: trim and collapse every whitespace run, `&nbsp;` included.
pub fn normalize_cell(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// BeautifulSoup's `get_text(" ", strip=True)` followed by `normalize_cell`.
/// Like bs4, text inside `<script>`, `<style>` and `<template>` is left out.
pub fn text_of(element: ElementRef) -> String {
    let root = element.id();
    let joined = element
        .descendants()
        .filter_map(|node| {
            let text = node.value().as_text()?;
            let hidden = node.ancestors().take_while(|a| a.id() != root).any(|a| {
                a.value()
                    .as_element()
                    .is_some_and(|e| matches!(e.name(), "script" | "style" | "template"))
            });
            (!hidden).then_some(&**text)
        })
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
