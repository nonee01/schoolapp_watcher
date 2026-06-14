package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class PresetsTest {
    @Test fun s3_has_seven_modules() {
        assertEquals(7, Presets.modulesForSemester("S3").size)
    }

    @Test fun s4_has_seven_modules() {
        assertEquals(7, Presets.modulesForSemester("s4").size)
    }

    @Test fun s3_first_module_is_analyse3() {
        val m = Presets.modulesForSemester("S3").first()
        assertEquals("API31", m.code)
        assertEquals(5.0, m.coefMod, 0.0001)
        assertEquals("API311", m.elements.first().code)
        assertEquals(0.3, m.elements.first().coefCc, 0.0001)
        assertEquals(0.7, m.elements.first().coefEx, 0.0001)
    }

    @Test fun s4_api45_prog_avancee_coefficients() {
        val mod = Presets.modulesForSemester("S4").first { it.code == "API45" }
        val prog = mod.elements.first { it.code == "API452" }
        assertEquals(0.3, prog.coefCc, 0.0001)
        assertEquals(1.0, prog.coefEcrit, 0.0001)
        assertEquals(1.0, prog.coefEelem, 0.0001)
    }

    @Test fun unsupported_semester_throws() {
        assertThrows(IllegalArgumentException::class.java) {
            Presets.modulesForSemester("S5")
        }
    }

    @Test fun total_coef_mod_s4_is_30() {
        val total = Presets.modulesForSemester("S4").sumOf { it.coefMod }
        assertTrue(total in 29.9..30.1)
    }
}
