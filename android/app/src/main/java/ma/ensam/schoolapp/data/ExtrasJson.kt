package ma.ensam.schoolapp.data

import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.json.JSONObject

/** Serializes Extras to a single JSON object string and back. Tolerant of bad input. */
object ExtrasJson {

    fun toJson(e: Extras): String {
        val root = JSONObject()
        val abs = JSONObject()
        e.absences.forEach { (k, a) ->
            abs.put(k, JSONObject()
                .put("element", a.element).put("date", a.date).put("seance", a.seance)
                .put("justif", a.justif).put("remarks", a.remarks))
        }
        val san = JSONObject(); e.sanctions.forEach { (k, v) -> san.put(k, v) }
        val mods = JSONObject()
        e.modules.forEach { (k, m) ->
            mods.put(k, JSONObject().put("code", m.code).put("au", m.au).put("moy", m.moy).put("dec", m.dec))
        }
        val sems = JSONObject()
        e.semesters.forEach { (k, s) ->
            sems.put(k, JSONObject()
                .put("niveau", s.niveau).put("sem", s.sem).put("au", s.au).put("moy", s.moy)
                .put("dec", s.dec).put("rank", s.rank).put("pj", s.pj))
        }
        return root.put("absences", abs).put("sanctions", san).put("modules", mods).put("semesters", sems).toString()
    }

    fun fromJson(s: String): Extras {
        if (s.isBlank()) return Extras()
        val root = runCatching { JSONObject(s) }.getOrNull() ?: return Extras()
        return Extras(
            absences = root.optJSONObject("absences")?.let { o ->
                o.keys().asSequence().associateBy({ it }, { k ->
                    val a = o.getJSONObject(k)
                    Absence(a.optString("element"), a.optString("date"), a.optString("seance"), a.optString("justif"), a.optString("remarks"))
                })
            } ?: emptyMap(),
            sanctions = root.optJSONObject("sanctions")?.let { o ->
                o.keys().asSequence().associateBy({ it }, { k -> o.optString(k) })
            } ?: emptyMap(),
            modules = root.optJSONObject("modules")?.let { o ->
                o.keys().asSequence().associateBy({ it }, { k ->
                    val m = o.getJSONObject(k)
                    OfficialModule(m.optString("code"), m.optString("au"), m.optString("moy"), m.optString("dec"))
                })
            } ?: emptyMap(),
            semesters = root.optJSONObject("semesters")?.let { o ->
                o.keys().asSequence().associateBy({ it }, { k ->
                    val s2 = o.getJSONObject(k)
                    SemesterResultRow(s2.optString("niveau"), s2.optString("sem"), s2.optString("au"), s2.optString("moy"), s2.optString("dec"), s2.optString("rank"), s2.optString("pj"))
                })
            } ?: emptyMap(),
        )
    }
}
