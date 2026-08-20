from __future__ import annotations

from collections.abc import Callable, Iterable

from bs4 import BeautifulSoup

from ..models import CatalogElement, CatalogModule, Filiere
from ._tables import normalize_cell, row_to_dict, table_by_headers

CATALOG_PATH = "/plan-etudes-view/modules"
FILIERES_PATH = "/plan-etudes-view/filieres"

FILIERE_SIGNATURE = {"Code", "Intitule", "Departement"}

# module row cells carry a leading expand-button column the headers don't have
_MODULE_HEADERS = ["CodeMod", "Intitule", "Descriptif", "Niveau", "Semestre",
                   "VHMOD", "CoefMod", "Seuil", "Eliminatoire"]


def parse_catalog_options(html: str) -> dict:
    """The three jQuery-driven selects + the page CSRF token."""
    soup = BeautifulSoup(html, "html.parser")
    options: dict[str, list[str]] = {}
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if name:
            options[name] = [o.get("value") for o in sel.find_all("option") if o.get("value")]
    csrf = soup.select_one('input[name="_csrf"]')
    value = csrf.get("value") if csrf else None
    return {
        "niveau": options.get("niveau", []),
        "filiere": options.get("filiere", []),
        "semestre": options.get("semestre", []),
        "csrf": value if isinstance(value, str) else "",
    }


def parse_catalog_modules(html: str, filiere: str = "") -> list[CatalogModule]:
    """The POST response: module rows alternating with nested element tables.

    Niveau/semestre come from the response cells (the server maps the posted
    year-relative semestre to the absolute one, e.g. 2A+S1 → S3).
    """
    soup = BeautifulSoup(html, "html.parser")
    outer = None
    for t in soup.find_all("table"):
        own_th = {normalize_cell(th.get_text(" ", strip=True))
                  for th in t.find_all("th") if th.find_parent("table") is t}
        if {"CodeMod", "Intitule", "CoefMod"} <= own_th:
            outer = t
            break
    if outer is None:
        return []

    body = outer.find("tbody") or outer
    out: list[CatalogModule] = []
    current: CatalogModule | None = None
    for tr in body.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        nested = tr.find("table")
        if nested is None:
            cells = [normalize_cell(td.get_text(" ", strip=True)) for td in tds]
            values = cells[1:]  # skip the expand-button column
            raw = row_to_dict(_MODULE_HEADERS, values)
            if not raw.get("CodeMod"):
                continue  # the empty-combo placeholder row
            current = CatalogModule(
                code_mod=raw["CodeMod"],
                intitule=raw.get("Intitule", ""),
                descriptif=raw.get("Descriptif", ""),
                niveau=raw.get("Niveau", ""),
                semestre=raw.get("Semestre", ""),
                vh_mod=raw.get("VHMOD", ""),
                coef_mod=raw.get("CoefMod", ""),
                seuil=raw.get("Seuil", ""),
                eliminatoire=raw.get("Eliminatoire", ""),
                filiere=filiere,
                raw=raw,
            )
            out.append(current)
        elif current is not None:
            headers = [normalize_cell(th.get_text(" ", strip=True)) for th in nested.find_all("th")]
            for ntr in nested.find_all("tr"):
                ntds = [normalize_cell(td.get_text(" ", strip=True)) for td in ntr.find_all("td")]
                if not ntds or not ntds[0]:
                    continue
                nraw = row_to_dict(headers, ntds)
                current.elements.append(CatalogElement(
                    code=nraw.get("CodeElem", ""),
                    intitule=nraw.get("Intitule", ""),
                    vh_ctd=nraw.get("VHCTD", ""),
                    vh_tp=nraw.get("VHTP", ""),
                    vh_eval=nraw.get("VHEVAL", ""),
                    coef_cc=nraw.get("CoefCC", ""),
                    coef_ex=nraw.get("CoefEX", ""),
                    coef_ecrit=nraw.get("CoefEcrit", ""),
                    coef_tp=nraw.get("CoefTP", ""),
                    coef_eelem=nraw.get("CoefEelem", ""),
                    raw=nraw,
                ))
    return out


def parse_filieres(html: str) -> list[Filiere]:
    """The /plan-etudes-view/filieres table. Returns [] if the table or its header signature is absent."""
    found = table_by_headers(html, FILIERE_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    out: list[Filiere] = []
    for r in rows:
        raw = row_to_dict(headers, r)
        if not raw.get("Code"):
            continue
        out.append(Filiere(code=raw["Code"], label=raw.get("Intitule", ""), raw=raw))
    return out


def crawl_catalog(client, niveaux: Iterable[str] | None = None,
                  filieres: Iterable[str] | None = None,
                  semestres: Iterable[str] | None = None,
                  on_combo: Callable | None = None) -> list[CatalogModule]:
    """Iterate the (niveau, filière, semestre) product; dedupe; a combo error never aborts the crawl.

    `on_combo(niveau, filiere, semestre, fresh_modules | None, error | None)` is called after each
    combo — the hook for incremental (resumable) persistence and progress logging.
    """
    opts = client.catalog_options()
    niveaux = list(niveaux) if niveaux else opts["niveau"]
    filieres = list(filieres) if filieres else opts["filiere"]
    semestres = list(semestres) if semestres else opts["semestre"]
    csrf = opts["csrf"]

    seen: set[tuple[str, str, str, str]] = set()
    out: list[CatalogModule] = []
    for f in filieres:
        for n in niveaux:
            for s in semestres:
                try:
                    mods = client.catalog_modules(n, f, s, csrf=csrf)
                except Exception as exc:  # noqa: BLE001 — log and continue (spec §11)
                    if on_combo:
                        on_combo(n, f, s, None, exc)
                    continue
                fresh = []
                for m in mods:
                    key = (m.code_mod, m.niveau, m.semestre, m.filiere)
                    if key not in seen:
                        seen.add(key)
                        fresh.append(m)
                        out.append(m)
                if on_combo:
                    on_combo(n, f, s, fresh, None)
    return out
