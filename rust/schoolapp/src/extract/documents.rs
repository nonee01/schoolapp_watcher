//! Downloadable document descriptors (`schoolapp/extractors/documents.py`).
//! Downloading itself is a separate, explicit step.

use crate::models::{Document, Raw, SemesterResult, YearResult};

pub const ATTESTATION_PATH: &str = "/student/documents/attestation-scolarite";

fn pdf(kind: &str, url: &str, params: Raw, filename: String) -> Document {
    Document { kind: kind.into(), url: url.into(), params, filename, content_type: "application/pdf".into() }
}

pub fn build_documents(year_results: &[YearResult], semester_results: &[SemesterResult]) -> Vec<Document> {
    let mut docs = vec![pdf("attestation-scolarite", ATTESTATION_PATH, Raw::new(), "attestation-scolarite.pdf".into())];
    for yr in year_results.iter().filter(|yr| !yr.releve_url.is_empty()) {
        docs.push(pdf(
            "releve-annee",
            &yr.releve_url,
            Raw::from([("niveau".to_string(), yr.niveau.clone())]),
            format!("releve-{}-{}.pdf", yr.niveau, yr.au),
        ));
    }
    for sr in semester_results.iter().filter(|sr| !sr.releve_url.is_empty()) {
        docs.push(pdf(
            "releve-semestre",
            &sr.releve_url,
            Raw::from([("niveau".to_string(), sr.niveau.clone()), ("semestre".to_string(), sr.semestre.clone())]),
            format!("releve-{}-{}-{}.pdf", sr.niveau, sr.semestre, sr.au),
        ));
    }
    docs
}
