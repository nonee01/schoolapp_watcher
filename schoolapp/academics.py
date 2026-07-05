"""Règlement engine - evaluation rules CE 2019-10-22 / CU 2019-12-25.

Pure Decimal functions (the portal rounds half-up: 9.075 -> 9.08; binary floats
would give 15.02 where it publishes 15.03). Computed values only ever FILL GAPS
the portal has not published yet, and display strings carry a `*` marker.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PREPA_NIVEAUX = {"1A", "2A"}


def parse_note(value: str | None) -> Decimal | None:
    raw = (value or "").strip().rstrip("*").replace(",", ".")
    if not raw or raw == "--":
        return None
    try:
        return Decimal(raw)
    except ArithmeticError:
        return None


def fmt_note(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Bars:
    """Art. 6/7/9 thresholds. prépa (1A/2A): 11/7/11 - cycle ingénieur: 12/8/12."""
    module_pass: Decimal
    element_floor: Decimal
    keep: Decimal


def bars_for(niveau: str) -> Bars:
    if (niveau or "").strip().upper()[:2] in PREPA_NIVEAUX:
        return Bars(Decimal("11"), Decimal("7"), Decimal("11"))
    return Bars(Decimal("12"), Decimal("8"), Decimal("12"))


def element_moy_so(*, cc: Decimal | None, ex: Decimal | None, tp: Decimal | None,
                   c1: Decimal, c2: Decimal) -> Decimal:
    """Art. 4: (C1·(0.3·CC + 0.7·EX) + C2·TP) / (C1 + C2)."""
    base = Decimal("0.3") * (cc or Decimal(0)) + Decimal("0.7") * (ex or Decimal(0))
    if tp is None or c2 == 0:
        return base
    return (c1 * base + c2 * tp) / (c1 + c2)


def element_moy_sr(*, moy_so: Decimal | None, cc: Decimal | None, rat: Decimal) -> Decimal:
    """Art. 7: Sup[SO ; Sup[(0.3·CC + 0.7·Rat) ; Rat]] - TP never rattrapé (Art. 8)."""
    rat_session = max(Decimal("0.3") * cc + Decimal("0.7") * rat, rat) if cc is not None else rat
    return max(moy_so if moy_so is not None else Decimal(0), rat_session)


# ── module resolution (presets -> catalog store) ──────────────────────────

def _preset_defs():
    from .presets import modules_for_semester
    out = []
    for sem in ("S3", "S4"):
        out.extend(modules_for_semester(sem))
    return out


def module_def_for(element_code: str):
    """ModuleDef owning an element: presets (S3/S4) first, then the catalog store."""
    code = (element_code or "").strip().upper()
    if not code:
        return None
    for mdef in _preset_defs():
        if any(e.code.upper() == code for e in mdef.elements):
            return mdef
    for mdef in _catalog_defs():
        if any(e.code.upper() == code for e in mdef.elements):
            return mdef
    return None


def _catalog_defs():
    """Catalog envelopes -> ModuleDefs (weights captured by the crawl, spec §11.1)."""
    from . import store
    from .presets import ElementDef, ModuleDef

    env = store.load_resource("catalog/modules")
    if not env or not isinstance(env.get("data"), list):
        return []
    out = []
    for m in env["data"]:
        elems = [
            ElementDef(
                code=str(e.get("code", "")),
                title=str(e.get("intitule", "")),
                coef_cc=float(parse_note(e.get("coef_cc")) or 0.3),
                coef_ex=float(parse_note(e.get("coef_ex")) or 0.7),
                coef_ecrit=float(parse_note(e.get("coef_ecrit")) or 1.0),
                coef_tp=float(parse_note(e.get("coef_tp")) or 0.0),
                coef_eelem=float(parse_note(e.get("coef_eelem")) or 1.0),
            )
            for e in (m.get("elements") or [])
        ]
        if elems:
            out.append(ModuleDef(
                code=str(m.get("code_mod", "")), title=str(m.get("intitule", "")),
                niveau=str(m.get("niveau", "")), semestre=str(m.get("semestre", "")),
                coef_mod=float(parse_note(m.get("coef_mod")) or 1.0),
                seuil=float(parse_note(m.get("seuil")) or 11.0),
                eliminatoire=float(parse_note(m.get("eliminatoire")) or 7.0),
                elements=elems,
            ))
    return out


# ── module rollup (Art. 5/6/9) ───────────────────────────────────────────

@dataclass
class ModuleOutcome:
    code: str
    moy: str             # weighted moyenne, pre-cap (Art. 5)
    final: str           # displayed note (Art. 9 cap when validated)
    decision: str        # "VRAT" | "NV"
    coeff_assumed: bool


def module_after_rat(mdef, notes: dict[str, Decimal], niveau: str) -> ModuleOutcome:
    """Art. 5 weighted moyenne over effective notes, Art. 6 validation, Art. 9 cap.

    `notes` maps element code -> effective moyenne (SR where rattrapé else SO).
    Elements of the module missing from `notes` are ignored (coeff_assumed=True).
    """
    bars = Bars(Decimal(str(mdef.seuil)), Decimal(str(mdef.eliminatoire)),
                Decimal(str(mdef.seuil))) if mdef is not None else bars_for(niveau)
    assumed = mdef is None
    if mdef is not None:
        weights = {e.code.upper(): Decimal(str(e.coef_eelem)) for e in mdef.elements}
        missing = set(weights) - {c.upper() for c in notes}
        if missing:
            assumed = True
        pairs = [(notes[c], weights.get(c.upper(), Decimal(1))) for c in notes]
        code = mdef.code
    else:
        pairs = [(v, Decimal(1)) for v in notes.values()]
        code = ""
    total_w = sum(w for _, w in pairs) or Decimal(1)
    moy = sum(v * w for v, w in pairs) / total_w
    validated = moy >= bars.module_pass and all(v >= bars.element_floor for v, _ in pairs)
    final = bars.module_pass if validated else moy   # Art. 9
    return ModuleOutcome(code=code, moy=fmt_note(moy), final=fmt_note(final),
                         decision="VRAT" if validated else "NV", coeff_assumed=assumed)


# ── StudentData annotation (gap-fill only; official values always win) ───

def annotate_student_data(data) -> list[str]:
    """Fill *_computed fields for rattrapé elements the portal hasn't rolled up.

    Returns human lines for digests: one per computed element.
    """
    niveau = (data.profile.niveau if data.profile else "") or "2A"
    # group candidates: same AU + same module
    pending: dict[tuple[str, str], list] = {}
    for g in data.element_grades:
        rat = parse_note(g.rat)
        if rat is None or parse_note(g.moy_sr) is not None:
            continue
        mdef = module_def_for(g.code)
        mod_code = mdef.code.upper() if mdef else (g.code.strip().upper()[:-1] or g.code)
        pending.setdefault((mod_code, g.au), []).append(g)

    lines: list[str] = []
    for (mod_code, au), rattrapes in pending.items():
        mdef = module_def_for(rattrapes[0].code)
        # effective notes for every element of this module visible in this AU
        notes: dict[str, Decimal] = {}
        srs: dict[str, Decimal] = {}
        member = ({e.code.upper() for e in mdef.elements} if mdef
                  else {g.code.upper() for g in rattrapes})
        for g in data.element_grades:
            if g.au != au or g.code.upper() not in member:
                continue
            rat = parse_note(g.rat)
            official_sr = parse_note(g.moy_sr)
            so = parse_note(g.moy) or parse_note(g.moy_so)
            if official_sr is not None:
                notes[g.code] = official_sr
            elif rat is not None:
                sr = element_moy_sr(moy_so=so, cc=parse_note(g.cc), rat=rat)
                notes[g.code] = srs[g.code] = sr
            elif so is not None:
                notes[g.code] = so
        if not srs:
            continue
        outcome = module_after_rat(mdef, notes, niveau)
        for g in rattrapes:
            if g.code not in srs:
                continue
            g.moy_sr_computed = fmt_note(srs[g.code])
            g.decision_computed = outcome.decision
            lines.append(
                f"{g.code}: RAT {g.rat} -> Moy SR {g.moy_sr_computed}* -> "
                f"module {mod_code}: {outcome.decision} ({outcome.final}*)")
        for m in data.module_grades:
            if m.code.upper() == mod_code and m.au == au and parse_note(m.moy) is None \
                    and m.decision.strip() in ("", "--", "RAT"):
                m.moy_computed = outcome.final
                m.decision_computed = outcome.decision
                m.coeff_assumed = outcome.coeff_assumed
    return lines
