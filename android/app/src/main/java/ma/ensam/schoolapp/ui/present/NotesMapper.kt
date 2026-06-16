package ma.ensam.schoolapp.ui.present

import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.ModuleStatus
import ma.ensam.schoolapp.domain.SnapshotMarks
import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.ModuleDef
import ma.ensam.schoolapp.domain.model.Snapshot

object NotesMapper {

    fun toNotesView(
        snapshot: Snapshot?,
        extras: Extras,
        modules: List<ModuleDef>,
        semester: String,
    ): NotesView {
        if (snapshot == null) {
            return NotesView(
                semester = semester,
                semesterAverage = null,
                validatedCount = 0,
                totalCount = modules.size,
                anyEstimated = false,
                modules = modules.map(::missingModule),
            )
        }

        val idx = snapshot.headers.withIndex().associate { (i, h) -> h to i }
        val codeIdx = idx["CodeElem"] ?: -1
        val byCode: Map<String, List<String>> =
            if (codeIdx >= 0)
                snapshot.rows.filter { it.size > codeIdx && it[codeIdx].isNotBlank() }
                    .associateBy { it[codeIdx].trim() }
            else emptyMap()

        val calc = Calculator.computeSemester(modules, SnapshotMarks.fromSnapshot(snapshot))
        val resultByCode = calc.modules.associateBy { it.code }

        val moduleViews = modules.map { mod ->
            val elements = mod.elements.map { el -> elementView(el, byCode[el.code], idx) }
            val official = extras.modules.values.firstOrNull { it.code == mod.code }
            val hasMarks = elements.any { e ->
                e.cc?.source == GradeSource.OFFICIAL || e.ex?.source == GradeSource.OFFICIAL ||
                    e.tp?.source == GradeSource.OFFICIAL || e.moy.source == GradeSource.OFFICIAL
            }
            val computed = resultByCode[mod.code]

            val source: GradeSource
            val average: Double?
            val status: ModuleStatus
            when {
                official != null -> {
                    source = GradeSource.OFFICIAL
                    average = Calculator.parseMarkString(official.moy)
                    status = statusFromDecision(official.dec)
                }
                hasMarks && computed != null -> {
                    source = GradeSource.ESTIMATED
                    average = computed.averageFinal
                    status = computed.status
                }
                else -> {
                    source = GradeSource.MISSING
                    average = null
                    status = ModuleStatus.NV
                }
            }
            val progress =
                if (average != null && mod.seuil > 0) (average / mod.seuil).toFloat().coerceIn(0f, 1f) else 0f

            ModuleView(
                code = mod.code, title = mod.title, average = average, seuil = mod.seuil,
                progressToSeuil = progress, status = status, source = source, elements = elements,
            )
        }

        val anyGraded = moduleViews.any { it.source != GradeSource.MISSING }
        return NotesView(
            semester = semester,
            semesterAverage = if (anyGraded) calc.semesterAverageFinal else null,
            validatedCount = moduleViews.count { it.source != GradeSource.MISSING && it.status != ModuleStatus.NV },
            totalCount = modules.size,
            anyEstimated = moduleViews.any { it.source == GradeSource.ESTIMATED },
            modules = moduleViews,
        )
    }

    private fun missingModule(mod: ModuleDef) = ModuleView(
        code = mod.code, title = mod.title, average = null, seuil = mod.seuil,
        progressToSeuil = 0f, status = ModuleStatus.NV, source = GradeSource.MISSING,
        elements = mod.elements.map {
            ElementView(it.code, it.title, null, null, null, Cell("Moy", null, "—", GradeSource.MISSING), "", false)
        },
    )

    private fun elementView(el: ElementDef, row: List<String>?, idx: Map<String, Int>): ElementView {
        fun raw(key: String): String =
            row?.let { r -> idx[key]?.let { if (it < r.size) r[it].trim() else "" } } ?: ""
        fun cell(label: String, key: String, used: Boolean): Cell? {
            if (!used) return null
            val r = raw(key)
            return Cell(label, Calculator.parseMarkString(r), r.ifBlank { "—" },
                if (r.isNotBlank()) GradeSource.OFFICIAL else GradeSource.MISSING)
        }
        val moyRaw = raw("Moy")
        return ElementView(
            code = el.code, title = el.title,
            cc = cell("CC", "CC", el.coefCc > 0),
            ex = cell("EX", "EX", el.coefEx > 0),
            tp = cell("TP", "TP", el.coefTp > 0),
            moy = Cell("Moy", Calculator.parseMarkString(moyRaw), moyRaw.ifBlank { "—" },
                if (moyRaw.isNotBlank()) GradeSource.OFFICIAL else GradeSource.MISSING),
            decision = raw("Dec"),
            fullyGraded = moyRaw.isNotBlank(),
        )
    }

    private fun statusFromDecision(dec: String): ModuleStatus {
        val d = dec.trim().uppercase()
        return when {
            d.startsWith("VRAT") || d.startsWith("RAT") -> ModuleStatus.RAT
            d.startsWith("V") -> ModuleStatus.VORD
            else -> ModuleStatus.NV
        }
    }
}
