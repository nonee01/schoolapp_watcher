//! The portal's resources, field for field the dataclasses of `schoolapp/models.py`.
//!
//! Field order and names are part of the store format: the store serializes
//! these structs in declaration order, so they must stay in the Python order.
//! `raw` maps keep the portal's table-header order.

use indexmap::IndexMap;
use serde::Serialize;

/// Header-ordered cells of one table row, or another insertion-ordered string map.
pub type Raw = IndexMap<String, String>;

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct StudentProfile {
    pub code: String,
    pub cne_masar: String,
    pub nom: String,
    pub prenom: String,
    pub nom_ar: String,
    pub prenom_ar: String,
    pub cin: String,
    pub sexe: String,
    pub date_naissance: String,
    pub email: String,
    pub filiere: String,
    pub niveau: String,
    pub statut: String,
    pub section: String,
    pub groupe: String,
    pub sous_groupe: String,
    pub photo_url: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct ElementGrade {
    pub code: String,
    pub au: String,
    pub cc: String,
    pub ex: String,
    pub tp: String,
    pub moy_so: String,
    pub rat: String,
    pub moy_sr: String,
    pub moy: String,
    pub decision: String,
    /// Règlement Art. 7, filled only when the portal lags.
    pub moy_sr_computed: String,
    /// "VRAT"/"NV" from the module rollup (Art. 6/9).
    pub decision_computed: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct ModuleGrade {
    pub code: String,
    pub au: String,
    pub moy: String,
    pub decision: String,
    /// Art. 9 final (capped at the bar when validated).
    pub moy_computed: String,
    pub decision_computed: String,
    /// True when coefficients were guessed (equal weights).
    pub coeff_assumed: bool,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct SemesterResult {
    pub niveau: String,
    pub semestre: String,
    pub au: String,
    pub moy_sem: String,
    pub pj: String,
    pub decision: String,
    pub classement: String,
    pub releve_url: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct YearResult {
    pub niveau: String,
    pub filiere: String,
    pub au: String,
    pub statut: String,
    pub moy_annee: String,
    pub pj: String,
    pub decision: String,
    pub classement: String,
    pub releve_url: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DiplomaResult {
    pub empty: bool,
    pub message: Option<String>,
    pub rows: Vec<Raw>,
    pub raw: Raw,
}

impl Default for DiplomaResult {
    fn default() -> Self {
        Self { empty: true, message: None, rows: Vec::new(), raw: Raw::new() }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Absence {
    pub element: String,
    pub date: String,
    pub seance: String,
    pub justified: bool,
    pub remarks: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Sanction {
    pub key: String,
    pub value: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct CourseEnrollment {
    pub code_elem: String,
    pub statut: String,
    pub section: String,
    pub groupe: String,
    pub sous_groupe: String,
    pub num: String,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct MarkStatistics {
    pub element: String,
    pub eval_kind: String,
    pub au: String,
    pub note: String,
    pub title: String,
    pub rows: Vec<Vec<String>>,
    pub raw: Raw,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Document {
    pub kind: String,
    pub url: String,
    pub params: Raw,
    pub filename: String,
    pub content_type: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct StudentData {
    pub profile: Option<StudentProfile>,
    pub element_grades: Vec<ElementGrade>,
    pub module_grades: Vec<ModuleGrade>,
    pub semester_results: Vec<SemesterResult>,
    pub year_results: Vec<YearResult>,
    pub diploma: Option<DiplomaResult>,
    pub absences: Vec<Absence>,
    pub absence_summary: Vec<Raw>,
    pub sanctions: Vec<Sanction>,
    pub courses: Vec<CourseEnrollment>,
    pub stats: Vec<MarkStatistics>,
    pub documents: Vec<Document>,
    pub fetched_at: String,
    pub errors: Raw,
}
