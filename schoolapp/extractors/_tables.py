from __future__ import annotations

import hashlib
import json

from bs4 import BeautifulSoup


def normalize_cell(text: str) -> str:
    return " ".join(text.split())


def extract_table(html: str) -> tuple[list[str], list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No table found on marks page")

    best = max(tables, key=lambda t: len(t.find_all("tr")))
    headers = [normalize_cell(th.get_text(" ", strip=True)) for th in best.find_all("th")]

    rows: list[list[str]] = []
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [normalize_cell(td.get_text(" ", strip=True)) for td in tds]
        if any(row):
            rows.append(row)

    return headers, rows


def table_by_headers(html: str, wanted: set[str]) -> tuple[list[str], list[list[str]]] | None:
    """Find the first table whose header row contains all `wanted` columns."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        headers = [normalize_cell(th.get_text(" ", strip=True)) for th in t.find_all("th")]
        if wanted.issubset(set(headers)):
            rows = []
            for tr in t.find_all("tr"):
                tds = [normalize_cell(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
                if tds and any(tds):
                    rows.append(tds)
            return headers, rows
    return None


def fingerprint(headers: list[str], rows: list[list[str]]) -> str:
    payload = json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
