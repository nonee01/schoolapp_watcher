package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Snapshot

/** Extracts a marks map ("CODE.cc"/".ex"/".ecrit"/".tp"/".rat" -> Double) from a scraped snapshot. */
object SnapshotMarks {
    fun fromSnapshot(snap: Snapshot): Map<String, Double> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val marks = HashMap<String, Double>()
        fun get(row: List<String>, key: String): Double? {
            val i = idx[key] ?: return null
            if (i >= row.size) return null
            return Calculator.parseMarkString(row[i])
        }
        for (row in snap.rows) {
            if (codeIdx >= row.size) continue
            val code = row[codeIdx].trim()
            if (code.isEmpty()) continue
            get(row, "CC")?.let { marks["$code.cc"] = it }
            get(row, "EX")?.let { marks["$code.ecrit"] = it; marks["$code.ex"] = it }
            get(row, "TP")?.let { marks["$code.tp"] = it }
            get(row, "RAT")?.let { marks["$code.rat"] = it }
        }
        return marks
    }
}
