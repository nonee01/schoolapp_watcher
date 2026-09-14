from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElementDef:
    code: str
    title: str
    coef_cc: float
    coef_ex: float
    coef_ecrit: float
    coef_tp: float
    coef_eelem: float


@dataclass(frozen=True)
class ModuleDef:
    code: str
    title: str
    niveau: str
    semestre: str
    coef_mod: float
    seuil: float
    eliminatoire: float
    elements: list[ElementDef]


PRESET_2A_S3: list[ModuleDef] = [
    ModuleDef(
        code="API31",
        title="Analyse 3",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[ElementDef("API311", "Analyse 3", 0.3, 0.7, 5.0, 0.0, 5.0)],
    ),
    ModuleDef(
        code="API32",
        title="Chimie organique et métallurgie",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API321", "Chimie organique", 0.3, 0.7, 2.5, 0.5, 3.0),
            ElementDef("API322", "Métallurgie", 0.0, 1.0, 1.5, 0.5, 2.0),
        ],
    ),
    ModuleDef(
        code="API33",
        title="Mécanique du solide et usinage",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API331", "Mécanique du solide appliquée", 0.3, 0.7, 3.0, 0.0, 3.0),
            ElementDef("API332", "Usinage 2", 0.0, 1.0, 1.5, 0.5, 2.0),
        ],
    ),
    ModuleDef(
        code="API34",
        title="Automatique et RDM",
        niveau="2A",
        semestre="S3",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API341", "Automatique des systèmes", 0.3, 0.7, 2.25, 0.5, 2.75),
            ElementDef("API342", "RDM", 0.0, 1.0, 1.75, 0.5, 2.25),
        ],
    ),
    ModuleDef(
        code="API35",
        title="Programmation et Probabilités",
        niveau="2A",
        semestre="S3",
        coef_mod=4.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API351", "Programmation C++ et Algorithmique", 0.3, 0.7, 2.25, 0.0, 2.25),
            ElementDef("API352", "Calcul des Probabilités", 0.3, 0.7, 1.75, 0.0, 1.75),
        ],
    ),
    ModuleDef(
        code="API36",
        title="Langues 3",
        niveau="2A",
        semestre="S3",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API361", "Initiation à la communication", 0.3, 0.7, 1.5, 0.0, 1.5),
            ElementDef("API362", "English for International communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ],
    ),
    ModuleDef(
        code="API37",
        title="Culture et Arts",
        niveau="2A",
        semestre="S3",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[ElementDef("API371", "Culture et Arts", 0.3, 0.7, 3.0, 0.0, 3.0)],
    ),
]

PRESET_2A_S4: list[ModuleDef] = [
    ModuleDef(
        code="API41",
        title="Analyse 4",
        niveau="2A",
        semestre="S4",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[ElementDef("API411", "Analyse 4", 0.3, 0.7, 5.0, 0.0, 5.0)],
    ),
    ModuleDef(
        code="API42",
        title="Algèbre 2",
        niveau="2A",
        semestre="S4",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[ElementDef("API421", "Algèbre 2", 0.3, 0.7, 5.0, 0.0, 5.0)],
    ),
    ModuleDef(
        code="API43",
        title="Eléments de machine",
        niveau="2A",
        semestre="S4",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[ElementDef("API431", "Eléments de machine", 0.3, 0.7, 5.0, 0.0, 5.0)],
    ),
    ModuleDef(
        code="API44",
        title="Electromagnétisme et Optique",
        niveau="2A",
        semestre="S4",
        coef_mod=5.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API441", "Electromagnétisme", 0.3, 0.7, 2.75, 0.25, 3.0),
            ElementDef("API442", "Optique physique", 0.0, 1.0, 1.75, 0.25, 2.0),
        ],
    ),
    ModuleDef(
        code="API45",
        title="Programmation avancée et méthodes numériques",
        niveau="2A",
        semestre="S4",
        coef_mod=4.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API451", "Méthodes numériques", 0.0, 1.0, 1.0, 0.75, 1.75),
            ElementDef("API452", "Programmation Avancée", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="API46",
        title="Langues 4",
        niveau="2A",
        semestre="S4",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API461", "Techniques d'écriture", 0.3, 0.7, 1.5, 0.0, 1.5),
            ElementDef("API462", "English for International Communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ],
    ),
    ModuleDef(
        code="API47",
        title="Savoir être, Développement personnel",
        niveau="2A",
        semestre="S4",
        coef_mod=3.0,
        seuil=11.0,
        eliminatoire=7.0,
        elements=[
            ElementDef("API471", "Développement personnel", 0.3, 0.7, 1.5, 0.0, 1.5),
            ElementDef("API472", "Savoir être", 0.3, 0.7, 1.5, 0.0, 1.5),
        ],
    ),
]


# ── 3A GE-DI (cycle ingénieur: seuil 12, éliminatoire 8) ──────────────────
# Relevé le 2026-09-13 sur /plan-etudes-view/modules (Niveau 3A, Filière
# GE-DI). CoefCC is NOT a constant 0.3 here: it is 0.0 for the elements with
# no contrôle continu and 0.4 for the two language elements.
#
# NOTE ON THE LABELS. Two different numberings are in play. The student's
# marks pages number semesters absolutely across the whole cursus, so 1A is
# S1/S2, 2A is S3/S4 and 3A is S5/S6 — that is what `schoolapp s5` and the
# calculator use, and it is how these presets are keyed. The plan d'études
# page reports this same 3A GE-DI programme as "S1"/"S2" (the cycle
# ingénieur restarting its own count), which is why `catalog show 3A GE-DI
# S1` takes S1 while everything else here says S5.

PRESET_3A_S5: list[ModuleDef] = [
    ModuleDef(
        code="LE1",
        title="Langues Etrangères (Anglais, Français)",
        niveau="3A",
        semestre="S5",
        coef_mod=3.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("LE11", "Langue Anglaise", 0.4, 0.6, 1.0, 0.0, 1.0),
            ElementDef("LE12", "Langue française", 0.4, 0.6, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="PEI11",
        title="Electronique de puissance et Electrotechnique",
        niveau="3A",
        semestre="S5",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI111", "Electronique de puissance", 0.3, 0.7, 1.0, 0.5, 1.5),
            ElementDef("PEI112", "Electrotechnique", 0.3, 0.7, 1.0, 0.5, 1.5),
        ],
    ),
    ModuleDef(
        code="PEI12",
        title="Traitement de signal et Automatique",
        niveau="3A",
        semestre="S5",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI121", "Traitement de signal", 0.3, 0.7, 1.0, 0.5, 1.5),
            ElementDef("PEI122", "Automatique", 0.3, 0.7, 1.0, 0.5, 1.5),
        ],
    ),
    ModuleDef(
        code="PEI13",
        title="Dimensionnement des structures",
        niveau="3A",
        semestre="S5",
        coef_mod=4.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI131", "Mécanique des structures", 0.0, 1.0, 1.0, 0.5, 1.5),
            ElementDef("PEI132", "RDM", 0.0, 1.0, 1.0, 0.5, 1.5),
        ],
    ),
    ModuleDef(
        code="PEI14",
        title="Eléments et architectures de machines et Fabrication Additive et MMC",
        niveau="3A",
        semestre="S5",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI141", "Eléments et architectures de machines", 0.0, 1.0, 1.0, 0.0, 1.0),
            ElementDef("PEI142", "Fabrication additive et soudage", 0.3, 0.7, 1.0, 0.0, 1.0),
            ElementDef("PEI143", "Mécanique des milieux continus", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="PS1",
        title="Digital Skills - Excel Avancé",
        niveau="3A",
        semestre="S5",
        coef_mod=3.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PS1", "Digital Skills - Excel Avancé", 0.0, 1.0, 1.0, 1.0, 2.0),
        ],
    ),
    ModuleDef(
        code="TC11",
        title="Méthodes numériques et Statistiques",
        niveau="3A",
        semestre="S5",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("TC111", "Méthodes numériques", 0.3, 0.7, 1.5, 0.5, 2.0),
            ElementDef("TC112", "Statistique", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
]

PRESET_3A_S6: list[ModuleDef] = [
    ModuleDef(
        code="LE2",
        title="Langues Etrangères (Anglais, Français)",
        niveau="3A",
        semestre="S6",
        coef_mod=3.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("LE21", "Langue Anglaise", 0.0, 1.0, 1.0, 1.0, 2.0),
            ElementDef("LE22", "Langue Française", 0.0, 1.0, 1.0, 1.0, 2.0),
        ],
    ),
    ModuleDef(
        code="PEI21",
        title="Electronique et POO",
        niveau="3A",
        semestre="S6",
        coef_mod=4.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI211", "Electronique", 0.3, 0.7, 1.0, 0.5, 1.5),
            ElementDef("PEI212", "Programmation orientée objet", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="PEI22",
        title="Transmissions mécaniques et actionneurs",
        niveau="3A",
        semestre="S6",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI221", "Transmissions mécaniques et actionneurs", 0.0, 1.0, 0.6, 0.4, 1.0),
        ],
    ),
    ModuleDef(
        code="PEI23",
        title="Matériaux industriels",
        niveau="3A",
        semestre="S6",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PEI231", "Matériaux Métalliques", 0.3, 0.7, 1.0, 0.0, 1.0),
            ElementDef("PEI232", "Plastiques et composites", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="PS2",
        title="Culture and Art Skills",
        niveau="3A",
        semestre="S6",
        coef_mod=3.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("PS21", "Arts", 0.0, 1.0, 1.0, 0.5, 1.5),
            ElementDef("PS22", "Culture", 0.0, 1.0, 1.0, 0.5, 1.5),
        ],
    ),
    ModuleDef(
        code="TC21",
        title="Modélisation statistique et RO",
        niveau="3A",
        semestre="S6",
        coef_mod=5.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("TC211", "Modélisation Statistique", 0.3, 0.7, 2.0, 0.5, 2.5),
            ElementDef("TC212", "Recherche Opérationnelle", 0.3, 0.7, 1.0, 0.0, 1.0),
        ],
    ),
    ModuleDef(
        code="TC23",
        title="Mécanique des fluides et machines thermiques",
        niveau="3A",
        semestre="S6",
        coef_mod=4.0,
        seuil=12.0,
        eliminatoire=8.0,
        elements=[
            ElementDef("TC231", "Mécanique des fluides", 0.3, 0.7, 1.5, 0.5, 2.0),
            ElementDef("TC232", "Machines thermiques", 0.0, 1.0, 1.0, 0.0, 1.0),
        ],
    ),
]

_PRESETS: dict[str, list[ModuleDef]] = {
    "S3": PRESET_2A_S3,
    "S4": PRESET_2A_S4,
    "S5": PRESET_3A_S5,
    "S6": PRESET_3A_S6,
}


def available_semesters() -> tuple[str, ...]:
    """Every semester the presets describe, oldest label first.

    Callers that used to hardcode ("S3", "S4") went stale the moment the
    student moved up a year: titles stopped resolving and the digests fell
    back to bare element codes.
    """
    return tuple(sorted(_PRESETS))


def modules_for_semester(semester: str) -> list[ModuleDef]:
    sem = semester.strip().upper()
    try:
        return _PRESETS[sem]
    except KeyError:
        raise ValueError(
            f"Unsupported semester '{semester}'. "
            f"Expected one of {', '.join(sorted(_PRESETS))}."
        ) from None
