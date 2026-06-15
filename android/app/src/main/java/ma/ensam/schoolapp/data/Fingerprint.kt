package ma.ensam.schoolapp.data

import ma.ensam.schoolapp.domain.Presets
import java.security.MessageDigest

object Fingerprint {

    private val STATE_FIELDS = listOf("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    /**
     * Mirrors _marks_state in watcher.py: per-element grade values for the
     * semester's modules, ignoring row order and cosmetic columns. Returns a
     * map of CodeElem -> (field -> value). If there is no CodeElem column,
     * falls back to the raw row list under "__rows__".
     */
    fun marksState(headers: List<String>, rows: List<List<String>>, semester: String): Map<String, Map<String, String>> {
        val codeIdx = headers.indexOf("CodeElem")
        if (codeIdx < 0) {
            // No CodeElem column: represent the whole table positionally.
            val fallback = LinkedHashMap<String, Map<String, String>>()
            rows.forEachIndexed { i, r -> fallback["__row_$i"] = mapOf("raw" to r.joinToString("")) }
            return fallback
        }
        val idx = headers.withIndex().associate { (i, h) -> h to i }
        val prefixes = runCatching { Presets.modulesForSemester(semester).flatMap { it.elements }.map { it.code.uppercase() } }
            .getOrDefault(emptyList())

        val state = sortedMapOf<String, Map<String, String>>() // sorted -> order independent
        for (r in rows) {
            if (r.size <= codeIdx) continue
            val code = r[codeIdx].trim()
            if (code.isEmpty()) continue
            if (prefixes.isNotEmpty() && prefixes.none { code.uppercase() == it }) continue
            val cells = LinkedHashMap<String, String>()
            for (field in STATE_FIELDS) {
                val i = idx[field]
                cells[field] = if (i != null && i < r.size) r[i].trim() else ""
            }
            state[code] = cells
        }
        return state
    }

    /** SHA-256 over canonical JSON of the marks-state. Equal state => equal hash. */
    fun of(headers: List<String>, rows: List<List<String>>, semester: String): String {
        val state = marksState(headers, rows, semester)
        val canonical = canonicalJson(state)
        val digest = MessageDigest.getInstance("SHA-256").digest(canonical.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun canonicalJson(state: Map<String, Map<String, String>>): String {
        val sb = StringBuilder("{")
        state.entries.sortedBy { it.key }.forEachIndexed { i, (code, cells) ->
            if (i > 0) sb.append(",")
            sb.append(quote(code)).append(":{")
            cells.entries.sortedBy { it.key }.forEachIndexed { j, (k, v) ->
                if (j > 0) sb.append(",")
                sb.append(quote(k)).append(":").append(quote(v))
            }
            sb.append("}")
        }
        return sb.append("}").toString()
    }

    private fun quote(s: String): String {
        val b = StringBuilder("\"")
        for (c in s) when (c) {
            '"' -> b.append("\\\"")
            '\\' -> b.append("\\\\")
            '\n' -> b.append("\\n")
            '\r' -> b.append("\\r")
            '\t' -> b.append("\\t")
            else -> b.append(c)
        }
        return b.append("\"").toString()
    }
}
