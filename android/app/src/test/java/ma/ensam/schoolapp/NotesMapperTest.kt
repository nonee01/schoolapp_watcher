package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.ModuleStatus
import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.Snapshot
import ma.ensam.schoolapp.ui.present.GradeSource
import ma.ensam.schoolapp.ui.present.NotesMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NotesMapperTest {

    private val api42 = listOf(Presets.PRESET_2A_S4.first { it.code == "API42" })
    private val headers = listOf("CodeElem", "CC", "EX", "TP", "Moy", "Dec", "RAT")
    private fun snap(vararg rows: List<String>) = Snapshot(headers, rows.toList(), "fp")

    @Test fun null_snapshot_is_all_missing() {
        val v = NotesMapper.toNotesView(null, Extras(), api42, "S4")
        assertEquals(GradeSource.MISSING, v.modules.single().source)
        assertNull(v.semesterAverage)
        assertEquals(0, v.validatedCount)
        assertEquals(1, v.totalCount)
    }

    @Test fun scraped_marks_without_official_is_estimated() {
        val v = NotesMapper.toNotesView(
            snap(listOf("API421", "10", "20", "--", "--", "", "--")),
            Extras(), api42, "S4",
        )
        val m = v.modules.single()
        assertEquals(GradeSource.ESTIMATED, m.source)
        assertEquals(17.0, m.average!!, 0.0001)
        assertEquals(ModuleStatus.VORD, m.status)
        assertEquals(1.0f, m.progressToSeuil, 0.0001f) // 17/11 clamped to 1.0
        assertTrue(v.anyEstimated)
        assertEquals(1, v.validatedCount)
        // The single element uses CC and EX but not TP (coefTp == 0) -> tp cell hidden.
        val el = m.elements.single()
        assertEquals(10.0, el.cc!!.value!!, 0.0001)
        assertNull(el.tp)
    }

    @Test fun official_module_overrides_with_portal_value() {
        val extras = Extras(
            modules = mapOf("API42|2024/2025" to OfficialModule("API42", "2024/2025", "9.90", "NV")),
        )
        val v = NotesMapper.toNotesView(
            snap(listOf("API421", "10", "20", "--", "--", "", "--")),
            extras, api42, "S4",
        )
        val m = v.modules.single()
        assertEquals(GradeSource.OFFICIAL, m.source)
        assertEquals(9.90, m.average!!, 0.0001)        // portal moy, not the computed 17.0
        assertEquals(ModuleStatus.NV, m.status)
        assertEquals(0.9f, m.progressToSeuil, 0.0001f) // 9.9/11
        assertEquals(false, v.anyEstimated)
        assertEquals(0, v.validatedCount)
    }
}
