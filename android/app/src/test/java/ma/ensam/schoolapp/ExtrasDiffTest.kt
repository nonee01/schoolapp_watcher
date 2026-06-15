package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.ExtrasDiff
import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtrasDiffTest {
    @Test fun new_absence_is_reported() {
        val old = Extras()
        val new = Extras(absences = mapOf("API411|2024-03-12|S1" to Absence("API411", "2024-03-12", "S1", "false", "")))
        val msgs = ExtrasDiff.summaries(old, new)
        assertEquals(1, msgs.size)
        assertTrue(msgs[0].contains("API411"))
    }

    @Test fun unchanged_yields_nothing() {
        val e = Extras(sanctions = mapOf("Message" to "Avertissement"))
        assertTrue(ExtrasDiff.summaries(e, e).isEmpty())
    }

    @Test fun changed_module_decision_reported() {
        val old = Extras(modules = mapOf("API41|2023/2024" to ma.ensam.schoolapp.domain.model.OfficialModule("API41", "2023/2024", "9.0", "NV")))
        val new = Extras(modules = mapOf("API41|2023/2024" to ma.ensam.schoolapp.domain.model.OfficialModule("API41", "2023/2024", "13.4", "VRAC")))
        val msgs = ExtrasDiff.summaries(old, new)
        assertTrue(msgs.any { it.contains("API41") })
    }
}
