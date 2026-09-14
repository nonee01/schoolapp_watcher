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


def niveau_for_semester(semester: str) -> str:
    """Year label the portal's absolute semester belongs to: S1/S2 -> 1A ... S5/S6 -> 3A.

    The bars differ across the prépa/cycle ingénieur line, so a default of "2A"
    quietly applied 11/7/11 to a 3A table. The semester is already in hand
    everywhere this matters, and it answers the question exactly.
    """
    raw = (semester or "").strip().upper().lstrip("S")
    try:
        n = int(raw)
    except ValueError:
        return "2A"
    return f"{max(1, (n + 1) // 2)}A"


# The 0.3/0.7 split is only the common case. The plan d'études publishes CoefCC
# and CoefEX per element and they really do vary: 3A GE-DI S1 has 0.0/1.0 for
# RDM, Mécanique des structures, Elts. et arch. des machines and Digital Skills
# (no contrôle continu at all) and 0.4/0.6 for the two language elements.
# Hardcoding 0.3 silently invented a CC contribution for every one of those.
DEFAULT_CC_W = Decimal("0.3")
DEFAULT_EX_W = Decimal("0.7")


def element_moy_so(*, cc: Decimal | None, ex: Decimal | None, tp: Decimal | None,
                   c1: Decimal, c2: Decimal,
                   cc_w: Decimal | None = None, ex_w: Decimal | None = None) -> Decimal:
    """Art. 4: (C1·(CoefCC·CC + CoefEX·EX) + C2·TP) / (C1 + C2).

    cc_w/ex_w are the element's CoefCC/CoefEX from the plan d'études; they
    default to the usual 0.3/0.7 when the catalog has not been fetched.
    """
    cw = DEFAULT_CC_W if cc_w is None else cc_w
    xw = DEFAULT_EX_W if ex_w is None else ex_w
    base = cw * (cc or Decimal(0)) + xw * (ex or Decimal(0))
    if tp is None or c2 == 0:
        return base
    return (c1 * base + c2 * tp) / (c1 + c2)


def element_moy_sr(*, moy_so: Decimal | None, cc: Decimal | None, rat: Decimal,
                   cc_w: Decimal | None = None, ex_w: Decimal | None = None) -> Decimal:
    """Art. 7: Sup[SO ; Sup[(CoefCC·CC + CoefEX·Rat) ; Rat]] - TP never rattrapé (Art. 8).

    An element with CoefCC = 0 carries no CC into rattrapage: the expression
    collapses to Rat, which is what the portal does.
    """
    cw = DEFAULT_CC_W if cc_w is None else cc_w
    xw = DEFAULT_EX_W if ex_w is None else ex_w
    if cc is None or cw == 0:
        rat_session = rat
    else:
        rat_session = max(cw * cc + xw * rat, rat)
    return max(moy_so if moy_so is not None else Decimal(0), rat_session)





def element_shares(e) -> dict[str, float]:
    """What fraction of an element each assessment actually decides.

    Art. 4 is (CoefEcrit·(CoefCC·CC + CoefEX·EX) + CoefTP·TP) / CoefElem, so
    the written part splits by CoefCC/CoefEX and the TP takes CoefTP outright.
    Returns shares that sum to 1 — the raw coefficients do not, which is why
    "CoefCC 0.3" alone never told you how much a test was worth.

    PEI111 for instance: CoefCC 0.3, CoefEX 0.7, CoefEcrit 1.0, CoefTP 0.5 on
    CoefElem 1.5 -> test 20%, exam 47%, TP 33%.
    """
    total = e.coef_eelem or 1.0
    ecrit = e.coef_ecrit / total
    return {
        "test": ecrit * e.coef_cc,
        "exam": ecrit * e.coef_ex,
        "tp": e.coef_tp / total,
    }

def semester_weights(defs) -> list[dict]:
    """Each element's real share of the semester, heaviest first.

    An element's weight is coef_mod x (CoefElem / sum of CoefElem in its
    module) — a module's coefficient is split between its elements by their
    CoefElem, not shared equally. Summed over a semester this returns the
    total coefficient (30 for 3A GE-DI S1).

    `banked` says what is already decided before the exam session:
    CC+TP, CC, TP, or "" when nothing is (CoefCC 0 and CoefTP 0) — that last
    case is the only kind of element for which revision before December
    deposits nothing at all.
    """
    out: list[dict] = []
    for mdef in defs:
        total = sum(e.coef_eelem for e in mdef.elements)
        if not total:
            continue
        for e in mdef.elements:
            tp_share = (e.coef_tp / e.coef_eelem) if e.coef_eelem else 0.0
            if e.coef_cc > 0 and e.coef_tp > 0:
                banked = "CC+TP"
            elif e.coef_cc > 0:
                banked = "CC"
            elif e.coef_tp > 0:
                banked = "TP"
            else:
                banked = ""
            out.append({
                "code": e.code,
                "title": e.title,
                "module": mdef.code,
                "coef_mod": mdef.coef_mod,
                "weight": mdef.coef_mod * (e.coef_eelem / total),
                "coef_cc": e.coef_cc,
                "coef_ex": e.coef_ex,
                "coef_tp": e.coef_tp,
                "tp_share": tp_share,
                "banked": banked,
            })
    out.sort(key=lambda r: (-r["weight"], r["code"]))
    return out

# ── module resolution (presets -> catalog store) ──────────────────────────

def _preset_defs():
    from .presets import _PRESETS
    out = []
    for mods in _PRESETS.values():
        out.extend(mods)
    return out


def element_def_for(element_code: str):
    """ElementDef for a code: presets first, then the catalog store."""
    code = (element_code or "").strip().upper()
    if not code:
        return None
    for mdef in list(_preset_defs()) + list(_catalog_defs()):
        for e in mdef.elements:
            if e.code.upper() == code:
                return e
    return None


def elem_weights(element_code: str) -> tuple[Decimal | None, Decimal | None]:
    """(CoefCC, CoefEX) for an element, or (None, None) to fall back to 0.3/0.7.

    Not every element is 0.3/0.7: 3A GE-DI S1 publishes 0.0/1.0 for four of its
    fourteen elements and 0.4/0.6 for the two language ones.
    """
    edef = element_def_for(element_code)
    if edef is None:
        return None, None
    return Decimal(str(edef.coef_cc)), Decimal(str(edef.coef_ex))


def module_def_for(element_code: str):
    """ModuleDef owning an element: presets first, then the catalog store."""
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


def _coef(value, default: float) -> float:
    """A published coefficient, or `default` when the portal left it blank.

    `parse_note` returns Decimal("0.0") for a real zero and that is falsy, so
    `parse_note(x) or default` quietly replaced every legitimate 0 with the
    default - turning CoefCC=0 elements (no contrôle continu) into 0.3 ones.
    """
    parsed = parse_note(value)
    return float(default if parsed is None else parsed)


def _first_note(*values) -> Decimal | None:
    """The first value that parses as a note, ignoring the ones that are blank.

    Same trap as _coef: a real 0 parses to Decimal("0.0"), which is falsy, so
    `parse_note(a) or parse_note(b)` silently read column b whenever column a
    held a legitimate zero - and a zero is exactly what an absence scores.
    """
    for value in values:
        note = parse_note(value)
        if note is not None:
            return note
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
                coef_cc=_coef(e.get("coef_cc"), 0.3),
                coef_ex=_coef(e.get("coef_ex"), 0.7),
                coef_ecrit=_coef(e.get("coef_ecrit"), 1.0),
                coef_tp=_coef(e.get("coef_tp"), 0.0),
                coef_eelem=_coef(e.get("coef_eelem"), 1.0),
            )
            for e in (m.get("elements") or [])
        ]
        if elems:
            out.append(ModuleDef(
                code=str(m.get("code_mod", "")), title=str(m.get("intitule", "")),
                niveau=str(m.get("niveau", "")), semestre=str(m.get("semestre", "")),
                coef_mod=_coef(m.get("coef_mod"), 1.0),
                seuil=_coef(m.get("seuil"), 11.0),
                eliminatoire=_coef(m.get("eliminatoire"), 7.0),
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
            so = _first_note(g.moy_so, g.moy)
            if official_sr is not None:
                notes[g.code] = official_sr
            elif rat is not None:
                _cw, _xw = elem_weights(g.code)
                sr = element_moy_sr(moy_so=so, cc=parse_note(g.cc), rat=rat,
                                    cc_w=_cw, ex_w=_xw)
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


# ── year validation (Art. 11/12; Art. 16 S5 not distinguishable here) ────

def year_outcome(modules: list[dict], niveau: str) -> dict:
    """Art. 11 (prépa) / Art. 12 (cycle ingénieur years) condition check over
    module envelope rows. Uses *_computed values when official ones are absent
    (and flags `computed: True`). Purely informative - the jury decides."""
    bars = bars_for(niveau)
    nv_max = 2 if (niveau or "").strip().upper()[:2] in PREPA_NIVEAUX else 3

    used_computed = False
    weighted: list[tuple[Decimal, Decimal]] = []
    non_valides: list[str] = []
    floor_breach: list[str] = []
    for m in modules:
        moy = parse_note(m.get("moy"))
        dec = (m.get("decision") or "").strip()
        if moy is None and m.get("moy_computed"):
            moy, used_computed = parse_note(m.get("moy_computed")), True
        if not dec and m.get("decision_computed"):
            dec, used_computed = m["decision_computed"], True
        if moy is None:
            continue
        mdef = None
        for md in _preset_defs() + _catalog_defs():
            if md.code.upper() == str(m.get("code", "")).upper():
                mdef = md
                break
        coef = Decimal(str(mdef.coef_mod)) if mdef else Decimal(1)
        weighted.append((moy, coef))
        if dec.upper().startswith("NV"):
            non_valides.append(str(m.get("code", "")))
        if moy < bars.element_floor:
            floor_breach.append(str(m.get("code", "")))

    total = sum(w for _, w in weighted) or Decimal(1)
    year_moy = sum(v * w for v, w in weighted) / total
    conditions = {
        "moyenne": year_moy >= bars.module_pass,
        "nv_count": len(non_valides) <= nv_max,
        "floor": not floor_breach,
    }
    return {"moy": fmt_note(year_moy), "non_valides": non_valides,
            "floor_breach": floor_breach, "conditions": conditions,
            "would_validate": all(conditions.values()), "computed": used_computed}


# ── explanation (schoolapp explain CODE) ─────────────────────────────────

def _so_formula(element_code: str) -> str:
    """The Art. 4 formula string with this element's published coefficients."""
    cw, xw = elem_weights(element_code)
    if cw is None:
        return "0.3·CC + 0.7·EX (pondérée TP le cas échéant)"
    if cw == 0:
        return "EX seul - pas de contrôle continu (CoefCC = 0)"
    return f"{cw}·CC + {xw}·EX (pondérée TP le cas échéant)"


def _sr_formula(element_code: str) -> str:
    """The Art. 7 formula string with this element's published coefficients.

    The value beside it is computed from elem_weights, so printing a fixed
    0.3/0.7 split claimed a contrôle continu contribution that elements with
    CoefCC = 0 do not have, and that the number itself never included.
    """
    cw, xw = elem_weights(element_code)
    if cw is None:
        return "max(SO, max(0.3·CC + 0.7·Rat, Rat))"
    if cw == 0:
        return "max(SO, Rat) - pas de contrôle continu (CoefCC = 0)"
    return f"max(SO, max({cw}·CC + {xw}·Rat, Rat))"


def explain_element(code: str, items: list[dict]) -> dict | None:
    """Règlement walkthrough for one element, built from store envelope dicts.
    Picks the latest AU row for the code (prefers one with a RAT note)."""
    code_up = (code or "").strip().upper()
    rows = [g for g in items if str(g.get("code", "")).upper() == code_up]
    if not rows:
        return None
    rows.sort(key=lambda g: (bool(parse_note(g.get("rat"))), str(g.get("au", ""))))
    g = rows[-1]

    # MoySO first: on a rattrapé element "Moy" is the post-rattrapage value
    # (Art. 9), so reading it as the session ordinaire printed the wrong
    # number under Art. 4 and fed max(SO, ...) a note the session never had.
    so = _first_note(g.get("moy_so"), g.get("moy"))
    steps = [{
        "article": "Art. 4", "label": "Moyenne session ordinaire",
        "formula": _so_formula(code_up),
        "value": fmt_note(so) if so is not None else "--", "official": True,
    }]
    rat = parse_note(g.get("rat"))
    if rat is not None:
        official_sr = parse_note(g.get("moy_sr"))
        if official_sr is not None:
            sr_val, official = fmt_note(official_sr), True
        else:
            _cw, _xw = elem_weights(code_up)
            sr_val = g.get("moy_sr_computed") or fmt_note(
                element_moy_sr(moy_so=so, cc=parse_note(g.get("cc")), rat=rat,
                               cc_w=_cw, ex_w=_xw))
            official = False
        steps.append({
            "article": "Art. 7", "label": "Moyenne après rattrapage",
            "formula": _sr_formula(code_up),
            "value": sr_val, "official": official,
        })
        mdef = module_def_for(code_up)
        if mdef is not None and g.get("decision_computed"):
            bar = fmt_note(Decimal(str(mdef.seuil)))
            steps.append({
                "article": "Art. 5/6/9", "label": f"Module {mdef.code}",
                "formula": (f"Σ Ci·élément / Σ Ci ≥ {bar} et chaque élément ≥ "
                            f"{fmt_note(Decimal(str(mdef.eliminatoire)))} -> "
                            f"validé plafonné à {bar}"),
                "value": f"{g['decision_computed']} ({bar}*)"
                         if g["decision_computed"] == "VRAT" else g["decision_computed"],
                "official": False,
            })
    return {
        "code": code_up, "au": str(g.get("au", "")),
        "inputs": {k: str(g.get(k) or "") for k in
                   ("cc", "ex", "tp", "moy_so", "rat", "moy_sr", "decision")},
        "steps": steps,
    }


# ── legacy snapshot-table overlay (s3/s4 consolidated table) ─────────────

def overlay_snapshot_rows(headers: list[str], rows: list[list[str]], semester: str,
                          niveau: str | None = None) -> tuple[list[list[str]], list[str]]:
    """Gap-fill MoySR/Moy/Dec cells (as "15.03*" / "VRAT*") on a copy of the rows."""
    niveau = niveau or niveau_for_semester(semester)
    idx = {h: i for i, h in enumerate(headers)}
    needed = {"CodeElem", "CC", "MoySO", "RAT", "MoySR", "Moy", "Dec"}
    if not needed <= set(idx):
        return rows, []

    def cell(row, key):
        i = idx[key]
        return row[i].strip() if i < len(row) else ""

    out = [list(r) for r in rows]
    # candidate elements grouped by module
    pending: dict[str, list[int]] = {}
    for n, r in enumerate(out):
        if parse_note(cell(r, "RAT")) is None or parse_note(cell(r, "MoySR")) is not None:
            continue
        code = cell(r, "CodeElem").upper()
        if not code:
            continue
        mdef = module_def_for(code)
        pending.setdefault(mdef.code.upper() if mdef else code[:-1], []).append(n)

    lines: list[str] = []
    for mod_code, row_idx in pending.items():
        mdef = module_def_for(cell(out[row_idx[0]], "CodeElem"))
        member = ({e.code.upper() for e in mdef.elements} if mdef
                  else {cell(out[n], "CodeElem").upper() for n in row_idx})
        notes: dict[str, Decimal] = {}
        srs: dict[int, Decimal] = {}
        for n, r in enumerate(out):
            code = cell(r, "CodeElem").upper()
            if code not in member:
                continue
            official_sr, rat = parse_note(cell(r, "MoySR")), parse_note(cell(r, "RAT"))
            so = _first_note(cell(r, "MoySO"), cell(r, "Moy"))
            if official_sr is not None:
                notes[code] = official_sr
            elif rat is not None:
                _cw, _xw = elem_weights(code)
                sr = element_moy_sr(moy_so=so, cc=parse_note(cell(r, "CC")), rat=rat,
                                    cc_w=_cw, ex_w=_xw)
                notes[code] = sr
                srs[n] = sr
            elif so is not None:
                notes[code] = so
        if not srs:
            continue
        outcome = module_after_rat(mdef, notes, niveau)
        for n, sr in srs.items():
            marked = fmt_note(sr) + "*"
            out[n][idx["MoySR"]] = marked
            out[n][idx["Moy"]] = marked
            out[n][idx["Dec"]] = outcome.decision + "*"
            lines.append(
                f"{cell(out[n], 'CodeElem')}: RAT {cell(out[n], 'RAT')} -> Moy SR {marked} -> "
                f"module {mod_code}: {outcome.decision} ({outcome.final}*)")
    return out, lines
