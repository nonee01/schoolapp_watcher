from __future__ import annotations

from pathlib import Path

from .. import store
from ..models import CatalogElement, CatalogModule
from ..presets import ElementDef, ModuleDef

CATALOG_RESOURCE = "catalog/modules"


def _f(value: str | float | None) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def to_module_def(m: CatalogModule) -> ModuleDef:
    """Catalog module -> presets.ModuleDef, element weights included (the catalog exposes them)."""
    elements = [
        ElementDef(
            code=e.code,
            title=e.intitule,
            coef_cc=_f(e.coef_cc),
            coef_ex=_f(e.coef_ex),
            coef_ecrit=_f(e.coef_ecrit),
            coef_tp=_f(e.coef_tp),
            coef_eelem=_f(e.coef_eelem),
        )
        for e in m.elements
    ]
    return ModuleDef(
        code=m.code_mod,
        title=m.intitule,
        niveau=m.niveau,
        semestre=m.semestre,
        coef_mod=_f(m.coef_mod),
        seuil=_f(m.seuil),
        eliminatoire=_f(m.eliminatoire),
        elements=elements,
    )


def _from_dict(d: dict) -> CatalogModule:
    elements = [CatalogElement(**e) for e in d.get("elements", [])]
    fields = {k: v for k, v in d.items() if k != "elements"}
    return CatalogModule(**fields, elements=elements)


def load_catalog_modules(directory: Path | None = None) -> list[CatalogModule]:
    envelope = store.load_resource(CATALOG_RESOURCE, directory)
    if not envelope:
        return []
    return [_from_dict(d) for d in envelope["data"]]


def module_defs(niveau: str, filiere: str, semestre: str,
                modules: list[CatalogModule] | None = None,
                directory: Path | None = None) -> list[ModuleDef]:
    """Module definitions for any filière, from the crawled catalog (cached unless `modules` given).

    `semestre` is the absolute semester as the catalog reports it (e.g. "S3" for 2A).
    """
    if modules is None:
        modules = load_catalog_modules(directory)
    wanted = (niveau.strip().upper(), filiere.strip().upper(), semestre.strip().upper())
    return [
        to_module_def(m)
        for m in modules
        if (m.niveau.strip().upper(), m.filiere.strip().upper(), m.semestre.strip().upper()) == wanted
    ]


def reconcile(catalog_defs: list[ModuleDef], preset_defs: list[ModuleDef]) -> list[str]:
    """Human-readable coef/seuil mismatches between catalog and presets.py (spec §11.1)."""
    by_code = {d.code: d for d in preset_defs}
    mismatches: list[str] = []
    for c in catalog_defs:
        p = by_code.get(c.code)
        if p is None:
            continue
        for attr in ("coef_mod", "seuil", "eliminatoire"):
            cv, pv = getattr(c, attr), getattr(p, attr)
            if cv != pv:
                mismatches.append(f"{c.code}.{attr}: catalog={cv} presets={pv}")
    return mismatches
