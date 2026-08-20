from __future__ import annotations

from ..models import ElementGrade, ModuleGrade
from ._tables import register, row_to_dict, table_by_headers

ELEMENT_SIGNATURE = {"CodeElem", "AU", "Moy"}
MODULE_SIGNATURE = {"CodeMod", "AU", "Moy"}


def parse_element_grades(html: str) -> list[ElementGrade]:
    """Element marks table — same shape on /noteselem-encours (`Dec`) and /noteselem (`Decision`)."""
    found = table_by_headers(html, ELEMENT_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    out: list[ElementGrade] = []
    for r in rows:
        raw = row_to_dict(headers, r)
        if not raw.get("CodeElem"):
            continue
        out.append(ElementGrade(
            code=raw.get("CodeElem", ""),
            au=raw.get("AU", ""),
            cc=raw.get("CC", ""),
            ex=raw.get("EX", ""),
            tp=raw.get("TP", ""),
            moy_so=raw.get("MoySO", ""),
            rat=raw.get("RAT", ""),
            moy_sr=raw.get("MoySR", ""),
            moy=raw.get("Moy", ""),
            decision=raw.get("Dec") or raw.get("Decision", ""),
            raw=raw,
        ))
    return out


def parse_module_grades(html: str) -> list[ModuleGrade]:
    """Module results — /notesmod-encours (`Dec`) and /notesmod (`Decision`, extra `PJ` kept in raw)."""
    found = table_by_headers(html, MODULE_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    out: list[ModuleGrade] = []
    for r in rows:
        raw = row_to_dict(headers, r)
        if not raw.get("CodeMod"):
            continue
        out.append(ModuleGrade(
            code=raw.get("CodeMod", ""),
            au=raw.get("AU", ""),
            moy=raw.get("Moy", ""),
            decision=raw.get("Dec") or raw.get("Decision", ""),
            raw=raw,
        ))
    return out


register("element_grades", ELEMENT_SIGNATURE, parse_element_grades)
register("module_grades", MODULE_SIGNATURE, parse_module_grades)
