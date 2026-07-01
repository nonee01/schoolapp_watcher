from __future__ import annotations

from collections.abc import Iterable

from ..models import Document, SemesterResult, YearResult

ATTESTATION_PATH = "/student/documents/attestation-scolarite"


def build_documents(year_results: Iterable[YearResult] = (),
                    semester_results: Iterable[SemesterResult] = ()) -> list[Document]:
    """Descriptors only - downloading is a separate, explicit step (spec §5/Phase 5)."""
    docs = [Document(kind="attestation-scolarite", url=ATTESTATION_PATH, params={},
                     filename="attestation-scolarite.pdf", content_type="application/pdf")]
    for yr in year_results:
        if yr.releve_url:
            docs.append(Document(
                kind="releve-annee", url=yr.releve_url,
                params={"niveau": yr.niveau},
                filename=f"releve-{yr.niveau}-{yr.au}.pdf",
                content_type="application/pdf",
            ))
    for sr in semester_results:
        if sr.releve_url:
            docs.append(Document(
                kind="releve-semestre", url=sr.releve_url,
                params={"niveau": sr.niveau, "semestre": sr.semestre},
                filename=f"releve-{sr.niveau}-{sr.semestre}-{sr.au}.pdf",
                content_type="application/pdf",
            ))
    return docs
