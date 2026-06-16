package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow

object ResultsMapper {

    fun toResultsView(extras: Extras): ResultsView {
        val semesters = extras.semesters.values
            .sortedWith(compareByDescending<SemesterResultRow> { it.au }.thenByDescending { it.sem })
            .map { s ->
                val (pos, total) = parseRank(s.rank)
                SemesterRowView(
                    niveau = s.niveau, sem = s.sem, au = s.au, moy = s.moy, dec = s.dec,
                    rankText = rankText(pos, total, s.rank), rankPosition = pos, rankTotal = total,
                )
            }
        val modules = extras.modules.values
            .sortedWith(compareByDescending<OfficialModule> { it.au }.thenBy { it.code })
            .map { m ->
                OfficialModuleView(
                    code = m.code, title = Presets.moduleTitle(m.code) ?: m.code,
                    au = m.au, moy = m.moy, dec = m.dec,
                )
            }
        return ResultsView(semesters, modules)
    }

    /** "15/120" -> (15, 120); blank/malformed -> (null, null). */
    fun parseRank(rank: String): Pair<Int?, Int?> {
        val parts = rank.trim().split("/")
        if (parts.size != 2) return null to null
        return parts[0].trim().toIntOrNull() to parts[1].trim().toIntOrNull()
    }

    private fun rankText(pos: Int?, total: Int?, raw: String): String {
        if (pos == null || total == null) return raw.ifBlank { "-" }
        val ord = if (pos == 1) "1ᵉʳ" else "${pos}ᵉ"
        return "$ord / $total"
    }
}
