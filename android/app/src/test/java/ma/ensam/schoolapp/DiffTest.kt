package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Diff
import ma.ensam.schoolapp.domain.model.Snapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DiffTest {
    private val headers = listOf("CodeElem", "CC", "EX", "Moy", "Dec")
    private fun snap(rows: List<List<String>>) = Snapshot(headers, rows, "fp")

    @Test fun detects_new_element() {
        val old = snap(emptyList())
        val new = snap(listOf(listOf("API411", "12", "14", "13.4", "VORD")))
        val changes = Diff.compute(old, new, "S4")
        assertEquals(1, changes.size)
        assertEquals("API411", changes[0].code)
        assertTrue(changes[0].isNew)
    }

    @Test fun detects_changed_field() {
        val old = snap(listOf(listOf("API411", "12", "10", "10.6", "NV")))
        val new = snap(listOf(listOf("API411", "12", "16", "14.8", "VORD")))
        val changes = Diff.compute(old, new, "S4")
        assertEquals(1, changes.size)
        assertEquals(false, changes[0].isNew)
        // EX 10->16, Moy 10.6->14.8, Dec NV->VORD
        assertEquals("16", changes[0].fields["EX"]!!.second)
        assertEquals("10", changes[0].fields["EX"]!!.first)
        assertTrue(changes[0].fields.containsKey("Dec"))
    }

    @Test fun no_change_yields_empty() {
        val rows = listOf(listOf("API411", "12", "16", "14.8", "VORD"))
        assertTrue(Diff.compute(snap(rows), snap(rows), "S4").isEmpty())
    }

    @Test fun foreign_semester_elements_ignored() {
        val old = snap(emptyList())
        val new = snap(listOf(listOf("API311", "12", "14", "13.4", "VORD"))) // S3 elem under S4
        assertTrue(Diff.compute(old, new, "S4").isEmpty())
    }
}
