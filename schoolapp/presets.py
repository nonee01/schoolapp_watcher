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


def modules_for_semester(semester: str) -> list[ModuleDef]:
    sem = semester.strip().upper()
    if sem == "S3":
        return PRESET_2A_S3
    if sem == "S4":
        return PRESET_2A_S4
    raise ValueError(f"Unsupported semester '{semester}'. Expected S3 or S4.")
