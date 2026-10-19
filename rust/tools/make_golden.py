"""Write the golden files the Rust tests compare against.

The Python implementation is the reference: this script runs it on the
sanitized portal pages in tests/fixtures/ and on a few synthetic pages, and
serializes every result the way the resource store does. Regenerate with

    .venv/bin/python rust/tools/make_golden.py

from the repo root; never edit the output by hand.
"""
import json
import shutil
import sys
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from schoolapp import academics, client as client_mod, models, store  # noqa: E402
from schoolapp.extractors import (  # noqa: E402
    build_documents,
    extract_table,
    fingerprint,
    parse_absence_summary,
    parse_absences,
    parse_courses,
    parse_diploma,
    parse_element_grades,
    parse_mark_statistics,
    parse_module_grades,
    parse_profile,
    parse_sanctions,
    parse_semester_results,
    parse_year_results,
)
from tests.test_fetch_all import FakeSession  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"
OUT = REPO / "rust" / "schoolapp" / "tests" / "golden"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def dump(value) -> str:
    return json.dumps(store._jsonable(value), ensure_ascii=False, indent=1)


def write(rel: str, text: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


MODEL_CLASSES = [
    models.StudentProfile, models.ElementGrade, models.ModuleGrade, models.SemesterResult,
    models.YearResult, models.DiplomaResult, models.Absence, models.Sanction,
    models.CourseEnrollment, models.MarkStatistics, models.Document, models.StudentData,
]

EXTRACT_CASES = [
    ("elements_encours", "parse_element_grades", parse_element_grades),
    ("elements_history", "parse_element_grades", parse_element_grades),
    ("modules_encours", "parse_module_grades", parse_module_grades),
    ("modules_history", "parse_module_grades", parse_module_grades),
    ("semesters", "parse_semester_results", parse_semester_results),
    ("years", "parse_year_results", parse_year_results),
    ("diploma", "parse_diploma", parse_diploma),
    ("absences", "parse_absences", parse_absences),
    ("absences", "parse_absence_summary", parse_absence_summary),
    ("sanctions", "parse_sanctions", parse_sanctions),
    ("courses", "parse_courses", parse_courses),
    ("profile", "parse_profile", parse_profile),
    ("stats", "parse_mark_statistics",
     lambda html: parse_mark_statistics(html, element="ELEM1", eval_kind="MoyElem",
                                        au="2025/2026", note="12.50")),
]

SYNTHETIC = {
    "ragged_rows": (
        "<html><body><table>"
        "<tr><th>CodeElem</th><th>AU</th><th>CC</th><th>EX</th><th>TP</th><th>Moy</th></tr>"
        "<tr><td>E101</td><td>2025/2026</td><td>12</td><td>14</td><td>--</td><td>13,20</td></tr>"
        "<tr><td>E102</td><td>2025/2026</td><td>9</td></tr>"
        "<tr><td> </td><td></td><td>\n</td><td></td><td></td><td></td></tr>"
        "</table></body></html>",
        [("parse_element_grades", parse_element_grades)],
    ),
    "script_in_cell": (
        "<html><body><table>"
        "<tr><th>CodeElem</th><th>AU</th><th>Moy</th><th>Dec</th></tr>"
        "<tr><td>E301<script>var x = 1;</script></td><td>2025/2026</td>"
        "<td>14,00<style>.a { color: red }</style></td><td>V<template><b>t</b></template></td></tr>"
        "</table></body></html>",
        [("parse_element_grades", parse_element_grades)],
    ),
    # No malformed-table case: html.parser nests unclosed <th>/<td> and finds no
    # rows at all, while html5ever closes them like a browser. The Rust side pins
    # the browser behaviour in tests/extract_tables.rs instead.
    "duplicate_labels": (
        "<html><body><img src='/img/logo-ensam.png'><img src='/photos/E1.jpg'>"
        "<table><tr><th>Nom</th><td>Doe</td></tr>"
        "<tr><th>Lieu_Naissance</th><td>Meknès</td></tr>"
        "<tr><th>Lieu_Naissance</th><td>مكناس</td></tr>"
        "<tr><th>Email</th><td>a@b.c</td></tr>"
        "<tr><th>Email</th><td>a@b.c</td></tr></table></body></html>",
        [("parse_profile", parse_profile)],
    ),
    "arabic_profile": (
        "<html><body><table>"
        "<tr><th>Nom</th><td>Doe</td></tr><tr><th>Prénom</th><td>Jane</td></tr>"
        "<tr><th>Nom Arabe</th><td>دو</td></tr><tr><th>Prénom Arabe</th><td>جين</td></tr>"
        "<tr><th>Filière</th><td>Génie Électromécanique</td></tr>"
        "</table></body></html>",
        [("parse_profile", parse_profile)],
    ),
    "empty_diploma": (
        "<html><body><div class='alert'><p>  Vous n'avez pas de note de diplome\n pour le moment.</p>"
        "</div></body></html>",
        [("parse_diploma", parse_diploma)],
    ),
}


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is not None else NOW.replace(tzinfo=None)


def store_tree(rel: str, *, fail_paths=(), **fetch_kwargs) -> None:
    session = FakeSession(fail_paths=fail_paths)
    c = client_mod.SchoolAppClient(session=session)
    c.login("e", "p")
    data = c.fetch_all(**fetch_kwargs)
    store.save_student_data(data, source="fetch_all", directory=OUT / rel)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)

    for cls in MODEL_CLASSES:
        assert is_dataclass(cls) and fields(cls)
        write(f"models/{cls.__name__}.json", dump(cls()))

    for name, parser_name, parser in EXTRACT_CASES:
        write(f"extract/{name}__{parser_name}.json", dump(parser(fixture(name))))
    headers, rows = extract_table(fixture("elements_encours"))
    write("extract/elements_encours__extract_table.json", dump({"headers": headers, "rows": rows}))
    write("extract/elements_encours__fingerprint.txt", fingerprint(headers, rows) + "\n")
    write("extract/documents.json", dump(build_documents(
        parse_year_results(fixture("years")), parse_semester_results(fixture("semesters")))))

    for case, (html, parsers) in SYNTHETIC.items():
        write(f"synthetic/{case}.html", html)
        for parser_name, parser in parsers:
            write(f"synthetic/{case}__{parser_name}.json", dump(parser(html)))

    # Plan 2 ports the academics annotation; until then the goldens leave the
    # computed fields at their defaults, and the clock is fixed.
    academics.annotate_student_data = lambda data: None
    client_mod.datetime = FixedDatetime
    store.datetime = FixedDatetime
    store_tree("store_default")
    store_tree("store_stats_nohistory", include_history=False, include_stats=True)
    store_tree("store_fail_semesters", fail_paths={"/student/notessem"})

    print(f"wrote {sum(1 for p in OUT.rglob('*') if p.is_file())} files to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
