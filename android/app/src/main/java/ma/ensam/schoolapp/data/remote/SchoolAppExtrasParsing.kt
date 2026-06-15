package ma.ensam.schoolapp.data.remote

import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.jsoup.Jsoup
import org.jsoup.nodes.Element

/** Pure parsers for the extra watched pages, translated from watcher.py. */
object SchoolAppExtrasParsing {

    private fun norm(s: String) = s.trim().replace(Regex("\\s+"), " ")

    /** First <table> whose <th> set contains all wanted columns -> (headers, rows). */
    private fun tableByHeaders(html: String, wanted: Set<String>): Pair<List<String>, List<List<String>>>? {
        for (t in Jsoup.parse(html).select("table")) {
            val headers = t.select("th").map { norm(it.text()) }
            if (headers.toSet().containsAll(wanted)) {
                val rows = ArrayList<List<String>>()
                for (tr in t.select("tr")) {
                    val tds = tr.select("td").map { norm(it.text()) }
                    if (tds.isNotEmpty() && tds.any { it.isNotEmpty() }) rows.add(tds)
                }
                return headers to rows
            }
        }
        return null
    }

    private fun List<String>.idx(): Map<String, Int> = withIndex().associate { (i, h) -> h to i }
    private fun cell(row: List<String>, idx: Map<String, Int>, key: String): String {
        val i = idx[key] ?: return ""
        return if (i < row.size) row[i] else ""
    }

    fun parseAbsenceLog(html: String): Map<String, Absence> {
        val found = tableByHeaders(html, setOf("Element", "Date", "Seance")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, Absence>()
        for (r in rows) {
            val date = cell(r, idx, "Date").split(" ").firstOrNull().orEmpty()
            val elem = cell(r, idx, "Element")
            if (elem.isEmpty()) continue
            val seance = cell(r, idx, "Seance")
            out["$elem|$date|$seance"] = Absence(
                element = elem,
                date = date,
                seance = seance,
                justif = cell(r, idx, "Justif").lowercase(),
                remarks = cell(r, idx, "Remarques"),
            )
        }
        return out
    }

    fun parseSanctions(html: String): Map<String, String> {
        for (t: Element in Jsoup.parse(html).select("table")) {
            val out = LinkedHashMap<String, String>()
            for (tr in t.select("tr")) {
                val tds = tr.select("td").map { norm(it.text()) }
                if (tds.size >= 2 && tds[0].isNotEmpty()) out[tds[0]] = tds[1]
            }
            if (out.isNotEmpty()) return out
        }
        return emptyMap()
    }

    fun parseModulesEncours(html: String): Map<String, OfficialModule> {
        val found = tableByHeaders(html, setOf("CodeMod", "Moy", "Dec")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, OfficialModule>()
        for (r in rows) {
            val code = cell(r, idx, "CodeMod")
            if (code.isEmpty()) continue
            val au = cell(r, idx, "AU")
            out["$code|$au"] = OfficialModule(code, au, cell(r, idx, "Moy"), cell(r, idx, "Dec"))
        }
        return out
    }

    fun parseSemesterResults(html: String): Map<String, SemesterResultRow> {
        val found = tableByHeaders(html, setOf("Semestre", "Moy SEM")) ?: return emptyMap()
        val (headers, rows) = found
        val idx = headers.idx()
        val out = LinkedHashMap<String, SemesterResultRow>()
        for (r in rows) {
            val sem = cell(r, idx, "Semestre")
            if (sem.isEmpty()) continue
            val niveau = cell(r, idx, "Niveau")
            val au = cell(r, idx, "AU")
            val dec = cell(r, idx, "Decesion").ifEmpty { cell(r, idx, "Decision") } // site typo
            out["$niveau|$sem|$au"] = SemesterResultRow(
                niveau = niveau, sem = sem, au = au,
                moy = cell(r, idx, "Moy SEM"), dec = dec,
                rank = cell(r, idx, "Classement"), pj = cell(r, idx, "PJ"),
            )
        }
        return out
    }
}
