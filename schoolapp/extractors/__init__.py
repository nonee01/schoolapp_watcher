from ._tables import REGISTRY, extract_table, fingerprint, normalize_cell, table_by_headers
from .absences import parse_absence_summary, parse_absences, parse_sanctions
from .courses import parse_courses
from .documents import build_documents
from .grades import parse_element_grades, parse_module_grades
from .profile import parse_profile
from .results import parse_diploma, parse_semester_results, parse_year_results
from .stats import parse_mark_statistics

__all__ = [
    "REGISTRY",
    "build_documents",
    "extract_table",
    "fingerprint",
    "normalize_cell",
    "parse_absence_summary",
    "parse_absences",
    "parse_courses",
    "parse_diploma",
    "parse_element_grades",
    "parse_mark_statistics",
    "parse_module_grades",
    "parse_profile",
    "parse_sanctions",
    "parse_semester_results",
    "parse_year_results",
    "table_by_headers",
]
