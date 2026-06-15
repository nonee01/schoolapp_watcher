package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Snapshot

/** A single element that changed between two snapshots. */
data class ElementChange(
    val code: String,
    val isNew: Boolean,
    /** field name -> (oldValue, newValue) */
    val fields: Map<String, Pair<String, String>>,
)

object Diff {

    private val FIELDS = listOf("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    fun compute(old: Snapshot, new: Snapshot, semester: String): List<ElementChange> {
        val prefixes = runCatching { Presets.modulesForSemester(semester).map { it.code.uppercase() } }
            .getOrDefault(emptyList())

        val oldByCode = byCode(old)
        val newByCode = byCode(new)
        val changes = ArrayList<ElementChange>()

        for ((code, newCells) in newByCode) {
            if (prefixes.isNotEmpty() && prefixes.none { code.uppercase().startsWith(it) }) continue
            val oldCells = oldByCode[code]
            if (oldCells == null) {
                changes.add(ElementChange(code, isNew = true, fields = emptyMap()))
                continue
            }
            val diffed = LinkedHashMap<String, Pair<String, String>>()
            for (f in FIELDS) {
                val o = oldCells[f] ?: "--"
                val n = newCells[f] ?: "--"
                if (o != n && !(o == "--" && n == "--")) diffed[f] = o to n
            }
            if (diffed.isNotEmpty()) changes.add(ElementChange(code, isNew = false, fields = diffed))
        }
        return changes.sortedBy { it.code }
    }

    private fun byCode(snap: Snapshot): Map<String, Map<String, String>> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val out = LinkedHashMap<String, Map<String, String>>()
        for (r in snap.rows) {
            if (r.size <= codeIdx) continue
            val code = r[codeIdx].trim()
            if (code.isEmpty()) continue
            val cells = LinkedHashMap<String, String>()
            for (f in FIELDS) {
                val i = idx[f]
                cells[f] = if (i != null && i < r.size) r[i].trim() else "--"
            }
            out[code] = cells
        }
        return out
    }
}
