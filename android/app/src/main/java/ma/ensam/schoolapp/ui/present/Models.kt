package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.ModuleStatus

/** Where a displayed number comes from. ESTIMATED must never be styled as OFFICIAL. */
enum class GradeSource { OFFICIAL, ESTIMATED, MISSING }

/** One displayable grade cell (CC/EX/TP/Moy). value is null when not numeric. */
data class Cell(
    val label: String,
    val value: Double?,
    val display: String,
    val source: GradeSource,
)

data class ElementView(
    val code: String,
    val title: String,
    val cc: Cell?,   // null when the element does not use this column
    val ex: Cell?,
    val tp: Cell?,
    val moy: Cell,
    val decision: String,
    val fullyGraded: Boolean,
)

data class ModuleView(
    val code: String,
    val title: String,
    val average: Double?,
    val seuil: Double,
    val progressToSeuil: Float,
    val status: ModuleStatus,
    val source: GradeSource,
    val elements: List<ElementView>,
)

data class NotesView(
    val semester: String,
    val semesterAverage: Double?,
    val validatedCount: Int,
    val totalCount: Int,
    val anyEstimated: Boolean,
    val modules: List<ModuleView>,
)

data class SemesterRowView(
    val niveau: String,
    val sem: String,
    val au: String,
    val moy: String,
    val dec: String,
    val rankText: String,
    val rankPosition: Int?,
    val rankTotal: Int?,
)

data class OfficialModuleView(
    val code: String,
    val title: String,
    val au: String,
    val moy: String,
    val dec: String,
)

data class ResultsView(
    val semesters: List<SemesterRowView>,
    val officialModules: List<OfficialModuleView>,
)
