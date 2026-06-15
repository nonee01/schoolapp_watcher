package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Extras

/** Human-readable one-line summaries of what changed between two Extras. */
object ExtrasDiff {
    fun summaries(old: Extras, new: Extras): List<String> {
        val out = ArrayList<String>()
        for ((k, a) in new.absences) {
            val o = old.absences[k]
            if (o == null) {
                val j = if (a.justif == "true") "justifiée" else "non justifiée"
                out.add("🚨 Absence $j - ${a.element} (${a.date} ${a.seance})")
            } else if (o.justif != a.justif && a.justif == "true") {
                out.add("✅ Absence justifiée - ${a.element} (${a.date})")
            }
        }
        for ((k, v) in new.sanctions) {
            if (old.sanctions[k] != v) out.add("⚠️ Sanction - $k: $v")
        }
        for ((k, m) in new.modules) {
            if (old.modules[k] != m) out.add("📋 Module ${m.code} - ${m.moy} (${m.dec})")
        }
        for ((k, s) in new.semesters) {
            if (old.semesters[k] != s) out.add("🎓 ${s.sem} - Moy ${s.moy}, rang ${s.rank} (${s.dec})")
        }
        return out
    }
}
