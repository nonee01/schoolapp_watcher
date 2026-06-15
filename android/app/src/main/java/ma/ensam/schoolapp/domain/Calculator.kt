package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.ModuleDef

enum class ModuleStatus { VORD, RAT, NV }

data class ModuleResult(
    val code: String,
    val title: String,
    val averageOrdinaire: Double,
    val averageRattrapage: Double,
    val averageFinal: Double,
    val status: ModuleStatus,
)

data class SemesterResult(
    val modules: List<ModuleResult>,
    val semesterAverageOrdinaire: Double,
    val semesterAverageFinal: Double,
    val nonValidatedCodes: List<String>,
)

object Calculator {

    private const val MISSING_MARK = "--"

    /**
     * Parses a scraped mark string to a Double, or null if blank / "--" / non-numeric.
     * Parsing helper used by upstream layers (e.g. the snapshot -> marks mapping).
     */
    fun parseMarkString(value: String): Double? {
        val raw = value.trim()
        if (raw.isEmpty() || raw == MISSING_MARK) return null
        return raw.toDoubleOrNull()
    }

    /** Mirrors _calc_element_grade in calculator.py. */
    fun calcElementGrade(defn: ElementDef, marks: Map<String, Double>): Double {
        val cc = marks["${defn.code}.cc"] ?: 0.0
        val ex: Double = if (marks.containsKey("${defn.code}.ecrit") || marks.containsKey("${defn.code}.tp")) {
            val ecrit = marks["${defn.code}.ecrit"] ?: 0.0
            val tp = marks["${defn.code}.tp"] ?: 0.0
            val denom = defn.coefEcrit + defn.coefTp
            if (denom > 0) (ecrit * defn.coefEcrit + tp * defn.coefTp) / denom else 0.0
        } else {
            marks["${defn.code}.ex"] ?: 0.0
        }
        return cc * defn.coefCc + ex * defn.coefEx
    }

    /** Mirrors _calc_element_rattrapage in calculator.py. */
    fun calcElementRattrapage(defn: ElementDef, marks: Map<String, Double>, ordinaryGrade: Double): Double {
        val rat = marks["${defn.code}.rat"] ?: return ordinaryGrade
        val cc = marks["${defn.code}.cc"] ?: 0.0
        val weightedRat = cc * defn.coefCc + rat * defn.coefEx
        val ratSession = maxOf(weightedRat, rat)
        return maxOf(ordinaryGrade, ratSession)
    }

    /** Mirrors the per-module + semester loop in run_calculator (calculator.py). */
    fun computeSemester(modules: List<ModuleDef>, marks: Map<String, Double>): SemesterResult {
        val results = ArrayList<ModuleResult>()
        var semPointsOrd = 0.0
        var semPointsFinal = 0.0
        val semWeight = modules.sumOf { it.coefMod }.takeIf { it > 0 } ?: 1.0
        val nonValidated = ArrayList<String>()

        for (mod in modules) {
            var ptsOrd = 0.0
            var ptsRatt = 0.0
            var ptsFinal = 0.0
            for (el in mod.elements) {
                val ord = calcElementGrade(el, marks)
                val ratt = calcElementRattrapage(el, marks, ord)
                val finalG = maxOf(ord, ratt)
                ptsOrd += ord * el.coefEelem
                ptsRatt += ratt * el.coefEelem
                ptsFinal += finalG * el.coefEelem
            }
            val coef = if (mod.coefMod > 0) mod.coefMod else 1.0
            val avgOrd = ptsOrd / coef
            val avgRatt = ptsRatt / coef
            var avgFinal = ptsFinal / coef
            if (avgOrd < mod.seuil && mod.seuil <= avgRatt) avgFinal = mod.seuil

            semPointsOrd += avgOrd * mod.coefMod
            semPointsFinal += avgFinal * mod.coefMod

            val status = when {
                avgOrd >= mod.seuil -> ModuleStatus.VORD
                avgRatt >= mod.seuil -> ModuleStatus.RAT
                else -> ModuleStatus.NV
            }
            if (status == ModuleStatus.NV) nonValidated.add(mod.code)
            results.add(ModuleResult(mod.code, mod.title, avgOrd, avgRatt, avgFinal, status))
        }

        return SemesterResult(
            modules = results,
            semesterAverageOrdinaire = semPointsOrd / semWeight,
            semesterAverageFinal = semPointsFinal / semWeight,
            nonValidatedCodes = nonValidated,
        )
    }
}
