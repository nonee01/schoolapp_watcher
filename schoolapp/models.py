from __future__ import annotations

from dataclasses import dataclass, field

PASS_THRESHOLD = 11.0


@dataclass
class StudentProfile:
    code: str = ""
    cne_masar: str = ""
    nom: str = ""
    prenom: str = ""
    nom_ar: str = ""
    prenom_ar: str = ""
    cin: str = ""
    sexe: str = ""
    date_naissance: str = ""
    email: str = ""
    filiere: str = ""
    niveau: str = ""
    statut: str = ""
    section: str = ""
    groupe: str = ""
    sous_groupe: str = ""
    photo_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class ElementGrade:
    code: str = ""
    au: str = ""
    cc: str = ""
    ex: str = ""
    tp: str = ""
    moy_so: str = ""
    rat: str = ""
    moy_sr: str = ""
    moy: str = ""
    decision: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def is_estimated(self) -> bool:
        return self.moy.endswith("*")

    @property
    def validated(self) -> bool | None:
        m = self.moy.rstrip("*")
        if m in ("", "--"):
            return None
        try:
            return float(m) >= PASS_THRESHOLD
        except ValueError:
            return None


@dataclass
class ModuleGrade:
    code: str = ""
    au: str = ""
    moy: str = ""
    decision: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class SemesterResult:
    niveau: str = ""
    semestre: str = ""
    au: str = ""
    moy_sem: str = ""
    pj: str = ""
    decision: str = ""
    classement: str = ""
    releve_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class YearResult:
    niveau: str = ""
    filiere: str = ""
    au: str = ""
    statut: str = ""
    moy_annee: str = ""
    pj: str = ""
    decision: str = ""
    classement: str = ""
    releve_url: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class DiplomaResult:
    empty: bool = True
    message: str | None = None
    rows: list[dict[str, str]] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Absence:
    element: str = ""
    date: str = ""
    seance: str = ""
    justified: bool = False
    remarks: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Sanction:
    key: str = ""
    value: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class CourseEnrollment:
    code_elem: str = ""
    statut: str = ""
    section: str = ""
    groupe: str = ""
    sous_groupe: str = ""
    num: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class MarkStatistics:
    element: str = ""
    eval_kind: str = ""
    au: str = ""
    note: str = ""
    title: str = ""
    rows: list[list[str]] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class CatalogModule:
    code_mod: str = ""
    intitule: str = ""
    descriptif: str = ""
    niveau: str = ""
    semestre: str = ""
    vh_mod: str = ""
    coef_mod: str = ""
    seuil: str = ""
    eliminatoire: str = ""
    filiere: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Filiere:
    code: str = ""
    label: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class Document:
    kind: str = ""
    url: str = ""
    params: dict[str, str] = field(default_factory=dict)
    filename: str = ""
    content_type: str = ""


@dataclass
class StudentData:
    profile: StudentProfile | None = None
    element_grades: list[ElementGrade] = field(default_factory=list)
    module_grades: list[ModuleGrade] = field(default_factory=list)
    semester_results: list[SemesterResult] = field(default_factory=list)
    year_results: list[YearResult] = field(default_factory=list)
    diploma: DiplomaResult | None = None
    absences: list[Absence] = field(default_factory=list)
    absence_summary: list[dict[str, str]] = field(default_factory=list)
    sanctions: list[Sanction] = field(default_factory=list)
    courses: list[CourseEnrollment] = field(default_factory=list)
    stats: list[MarkStatistics] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    fetched_at: str = ""
    errors: dict[str, str] = field(default_factory=dict)
