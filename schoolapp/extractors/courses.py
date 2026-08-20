from __future__ import annotations

from ..models import CourseEnrollment
from ._tables import register, row_to_dict, table_by_headers

COURSE_SIGNATURE = {"CodeElem", "Statut", "Num"}


def parse_courses(html: str) -> list[CourseEnrollment]:
    """The course-enrollment table (section/groupe/sous-groupe per element). Returns [] if the
    table or its header signature is absent."""
    found = table_by_headers(html, COURSE_SIGNATURE)
    if not found:
        return []
    headers, rows = found
    out: list[CourseEnrollment] = []
    for r in rows:
        raw = row_to_dict(headers, r)
        if not raw.get("CodeElem"):
            continue
        out.append(CourseEnrollment(
            code_elem=raw.get("CodeElem", ""),
            statut=raw.get("Statut", ""),
            section=raw.get("Section", ""),
            groupe=raw.get("Groupe", ""),
            sous_groupe=raw.get("S.Groupe", ""),
            num=raw.get("Num", ""),
            raw=raw,
        ))
    return out


register("courses", COURSE_SIGNATURE, parse_courses)
