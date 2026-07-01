from ._tables import REGISTRY, extract_table, fingerprint, normalize_cell, table_by_headers
from .absences import parse_absence_summary, parse_absences, parse_sanctions
from .catalog import crawl_catalog, parse_catalog_modules, parse_catalog_options, parse_filieres
from .courses import parse_courses
from .documents import build_documents
from .grades import parse_element_grades, parse_module_grades
from .profile import parse_profile
from .results import parse_diploma, parse_semester_results, parse_year_results
from .stats import parse_mark_statistics

__all__ = [
    "REGISTRY",
    "build_documents",
    "crawl_catalog",
    "extract_table",
    "fingerprint",
    "normalize_cell",
    "parse_absence_summary",
    "parse_absences",
    "parse_catalog_modules",
    "parse_catalog_options",
    "parse_courses",
    "parse_diploma",
    "parse_element_grades",
    "parse_filieres",
    "parse_mark_statistics",
    "parse_module_grades",
    "parse_profile",
    "parse_sanctions",
    "parse_semester_results",
    "parse_year_results",
    "table_by_headers",
]
