package ma.ensam.schoolapp.domain.model

/** One absence row from /student/absence/bilan. Key = "element|date|seance". */
data class Absence(
    val element: String,
    val date: String,
    val seance: String,
    val justif: String,   // "true"/"false"/raw lowercased
    val remarks: String,
)

/** One official module result from /student/notesmod-encours. Key = "code|au". */
data class OfficialModule(
    val code: String,
    val au: String,
    val moy: String,
    val dec: String,
)

/** One semester result from /student/notessem. Key = "niveau|sem|au". */
data class SemesterResultRow(
    val niveau: String,
    val sem: String,
    val au: String,
    val moy: String,
    val dec: String,
    val rank: String,
    val pj: String,
)

/** All extra watched pages for one check. sanctions is a flat key->value map. */
data class Extras(
    val absences: Map<String, Absence> = emptyMap(),
    val sanctions: Map<String, String> = emptyMap(),
    val modules: Map<String, OfficialModule> = emptyMap(),
    val semesters: Map<String, SemesterResultRow> = emptyMap(),
)
