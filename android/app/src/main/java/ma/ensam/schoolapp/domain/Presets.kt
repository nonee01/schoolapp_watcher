package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.ModuleDef

object Presets {

    private fun el(
        code: String, title: String,
        coefCc: Double, coefEx: Double, coefEcrit: Double, coefTp: Double, coefEelem: Double,
    ) = ElementDef(code, title, coefCc, coefEx, coefEcrit, coefTp, coefEelem)

    private fun mod(
        code: String, title: String, coefMod: Double, elements: List<ElementDef>,
        niveau: String = "2A", semestre: String, seuil: Double = 11.0, eliminatoire: Double = 7.0,
    ) = ModuleDef(code, title, niveau, semestre, coefMod, seuil, eliminatoire, elements)

    val PRESET_2A_S3: List<ModuleDef> = listOf(
        mod("API31", "Analyse 3", 5.0, listOf(
            el("API311", "Analyse 3", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S3"),
        mod("API32", "Chimie organique et métallurgie", 5.0, listOf(
            el("API321", "Chimie organique", 0.3, 0.7, 2.5, 0.5, 3.0),
            el("API322", "Métallurgie", 0.0, 1.0, 1.5, 0.5, 2.0),
        ), semestre = "S3"),
        mod("API33", "Mécanique du solide et usinage", 5.0, listOf(
            el("API331", "Mécanique du solide appliquée", 0.3, 0.7, 3.0, 0.0, 3.0),
            el("API332", "Usinage 2", 0.0, 1.0, 1.5, 0.5, 2.0),
        ), semestre = "S3"),
        mod("API34", "Automatique et RDM", 5.0, listOf(
            el("API341", "Automatique des systèmes", 0.3, 0.7, 2.25, 0.5, 2.75),
            el("API342", "RDM", 0.0, 1.0, 1.75, 0.5, 2.25),
        ), semestre = "S3"),
        mod("API35", "Programmation et Probabilités", 4.0, listOf(
            el("API351", "Programmation C++ et Algorithmique", 0.3, 0.7, 2.25, 0.0, 2.25),
            el("API352", "Calcul des Probabilités", 0.3, 0.7, 1.75, 0.0, 1.75),
        ), semestre = "S3"),
        mod("API36", "Langues 3", 3.0, listOf(
            el("API361", "Initiation à la communication", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API362", "English for International communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S3"),
        mod("API37", "Culture et Arts", 3.0, listOf(
            el("API371", "Culture et Arts", 0.3, 0.7, 3.0, 0.0, 3.0)
        ), semestre = "S3"),
    )

    val PRESET_2A_S4: List<ModuleDef> = listOf(
        mod("API41", "Analyse 4", 5.0, listOf(
            el("API411", "Analyse 4", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API42", "Algèbre 2", 5.0, listOf(
            el("API421", "Algèbre 2", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API43", "Eléments de machine", 5.0, listOf(
            el("API431", "Eléments de machine", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API44", "Electromagnétisme et Optique", 5.0, listOf(
            el("API441", "Electromagnétisme", 0.3, 0.7, 2.75, 0.25, 3.0),
            el("API442", "Optique physique", 0.0, 1.0, 1.75, 0.25, 2.0),
        ), semestre = "S4"),
        mod("API45", "Programmation avancée et méthodes numériques", 4.0, listOf(
            el("API451", "Méthodes numériques", 0.0, 1.0, 1.0, 0.75, 1.75),
            el("API452", "Programmation Avancée", 0.3, 0.7, 1.0, 0.0, 1.0),
        ), semestre = "S4"),
        mod("API46", "Langues 4", 3.0, listOf(
            el("API461", "Techniques d'écriture", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API462", "English for International Communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S4"),
        mod("API47", "Savoir être, Développement personnel", 3.0, listOf(
            el("API471", "Développement personnel", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API472", "Savoir être", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S4"),
    )

    fun modulesForSemester(semester: String): List<ModuleDef> =
        when (semester.trim().uppercase()) {
            "S3" -> PRESET_2A_S3
            "S4" -> PRESET_2A_S4
            else -> throw IllegalArgumentException(
                "Unsupported semester '$semester'. Expected S3 or S4."
            )
        }
}
