package ma.ensam.schoolapp.domain.model

data class ElementDef(
    val code: String,
    val title: String,
    val coefCc: Double,
    val coefEx: Double,
    val coefEcrit: Double,
    val coefTp: Double,
    val coefEelem: Double,
)

data class ModuleDef(
    val code: String,
    val title: String,
    val niveau: String,
    val semestre: String,
    val coefMod: Double,
    val seuil: Double,
    val eliminatoire: Double,
    val elements: List<ElementDef>,
)

/** A parsed marks table. Mirrors the Python Snapshot (headers/rows/fingerprint). */
data class Snapshot(
    val headers: List<String>,
    val rows: List<List<String>>,
    val fingerprint: String,
)
