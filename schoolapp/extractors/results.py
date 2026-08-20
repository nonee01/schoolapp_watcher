from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import DiplomaResult, SemesterResult, YearResult
from ._tables import normalize_cell, register, row_to_dict

SEMESTER_SIGNATURE = {"Semestre", "Moy SEM"}
YEAR_SIGNATURE = {"Niveau", "AU", "Moy Année"}
DIPLOMA_EMPTY_MARKER = "Vous n'avez pas de note de diplome"


def _rows_with_links(html: str, wanted: set[str]) -> tuple[list[str], list[tuple[dict[str, str], str]]]:
    """Header-signature table walk that also captures the row's first <a href> (relevé PDF link)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        headers = [normalize_cell(th.get_text(" ", strip=True)) for th in t.find_all("th")]
        if not wanted.issubset(set(headers)):
            continue
        rows: list[tuple[dict[str, str], str]] = []
        for tr in t.find_all("tr"):
            tds = tr.find_all("td")
            cells = [normalize_cell(td.get_text(" ", strip=True)) for td in tds]
            if not cells or not any(cells):
                continue
            raw = row_to_dict(headers, cells)
            a = tr.find("a", href=True)
            rows.append((raw, a["href"] if a else ""))
        return headers, rows
    return [], []


def parse_semester_results(html: str) -> list[SemesterResult]:
    """The per-semester results table (Niveau/Semestre/Moy SEM/Decision + relevé link).
    Returns [] if the table or its header signature is absent."""
    _, rows = _rows_with_links(html, SEMESTER_SIGNATURE)
    out: list[SemesterResult] = []
    for raw, href in rows:
        if not raw.get("Semestre"):
            continue
        out.append(SemesterResult(
            niveau=raw.get("Niveau", ""),
            semestre=raw.get("Semestre", ""),
            au=raw.get("AU", ""),
            moy_sem=raw.get("Moy SEM", ""),
            pj=raw.get("PJ", ""),
            decision=raw.get("Decesion") or raw.get("Decision", ""),  # site typo
            classement=raw.get("Classement", ""),
            releve_url=href,
            raw=raw,
        ))
    return out


def parse_year_results(html: str) -> list[YearResult]:
    """The per-year results table (Niveau/AU/Moy Année/Decision + relevé link).
    Returns [] if the table or its header signature is absent."""
    _, rows = _rows_with_links(html, YEAR_SIGNATURE)
    out: list[YearResult] = []
    for raw, href in rows:
        if not raw.get("Niveau"):
            continue
        out.append(YearResult(
            niveau=raw.get("Niveau", ""),
            filiere=raw.get("Filière", ""),
            au=raw.get("AU", ""),
            statut=raw.get("Statut", ""),
            moy_annee=raw.get("Moy Année", ""),
            pj=raw.get("PJ", ""),
            decision=raw.get("Decesion") or raw.get("Decision", ""),  # site typo
            classement=raw.get("Classement", ""),
            releve_url=href,
            raw=raw,
        ))
    return out


def parse_diploma(html: str) -> DiplomaResult:
    """Empty page ("Vous n'avez pas de note de diplome...") is a valid state, not an error."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if tables:
        best = max(tables, key=lambda t: len(t.find_all("tr")))
        headers = [normalize_cell(th.get_text(" ", strip=True)) for th in best.find_all("th")]
        rows: list[dict[str, str]] = []
        for tr in best.find_all("tr"):
            tds = [normalize_cell(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if not tds or not any(tds):
                continue
            if headers:
                rows.append(row_to_dict(headers, tds))
            else:
                rows.append({str(i): v for i, v in enumerate(tds)})
        if rows:
            return DiplomaResult(empty=False, message=None, rows=rows,
                                 raw={"headers": " | ".join(headers)})
    node = soup.find(string=lambda s: s and DIPLOMA_EMPTY_MARKER in s)
    message = normalize_cell(str(node)) if node else None
    return DiplomaResult(empty=True, message=message, rows=[], raw={})


register("semester_results", SEMESTER_SIGNATURE, parse_semester_results)
register("year_results", YEAR_SIGNATURE, parse_year_results)
