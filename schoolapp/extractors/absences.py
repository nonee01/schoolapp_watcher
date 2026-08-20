from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Absence, Sanction
from ._tables import normalize_cell, register, row_to_dict, table_by_headers

ABSENCE_SIGNATURE = {"Element", "Date", "Seance"}
SUMMARY_SIGNATURE = {"CodeElem", "Non Justifiée", "Justifiée"}


def parse_absences(html: str) -> list[Absence]:
    """The absence log table (one row per absence event)."""
    found = table_by_headers(html, ABSENCE_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    idx = {h: i for i, h in enumerate(headers)}
    out: list[Absence] = []
    for r in rows:
        def cell(k: str) -> str:
            i = idx.get(k)
            return r[i] if i is not None and i < len(r) else ""
        element = cell("Element")
        if not element:
            continue
        raw = row_to_dict(headers, r)
        out.append(Absence(
            element=element,
            date=cell("Date").split(" ")[0],
            seance=cell("Seance"),
            justified=cell("Justif").strip().lower() in ("true", "1", "oui", "yes"),
            remarks=cell("Remarques"),
            raw=raw,
        ))
    return out


def parse_absence_summary(html: str) -> list[dict[str, str]]:
    """The per-element counts table on /absence/bilan (CodeElem · Intitulé · counts)."""
    found = table_by_headers(html, SUMMARY_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    return [row_to_dict(headers, r) for r in rows if r and r[0]]


def parse_sanctions(html: str) -> list[Sanction]:
    """Loose two-column key/value table (counts + sanction message)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        pairs: list[tuple[str, str]] = []
        for tr in t.find_all("tr"):
            tds = [normalize_cell(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if len(tds) >= 2 and tds[0]:
                pairs.append((tds[0], tds[1]))
        if pairs:
            return [Sanction(key=k, value=v, raw={"key": k, "value": v}) for k, v in pairs]
    return []


register("absences", ABSENCE_SIGNATURE, parse_absences)
register("absence_summary", SUMMARY_SIGNATURE, parse_absence_summary)
