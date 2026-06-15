package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.Fingerprint
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class FingerprintTest {
    private val headers = listOf("CodeElem", "AU", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    private fun row(code: String, cc: String, ex: String, moy: String, dec: String) =
        listOf(code, "2024", cc, ex, "--", "--", "--", "--", moy, dec)

    @Test fun reordering_rows_does_not_change_state() {
        val r1 = row("API411", "12", "14", "13.4", "VORD")
        val r2 = row("API421", "10", "11", "10.7", "NV")
        val a = Fingerprint.marksState(headers, listOf(r1, r2), "S4")
        val b = Fingerprint.marksState(headers, listOf(r2, r1), "S4")
        assertEquals(a, b)
        assertEquals(Fingerprint.of(headers, listOf(r1, r2), "S4"), Fingerprint.of(headers, listOf(r2, r1), "S4"))
    }

    @Test fun changing_a_grade_changes_state() {
        val a = Fingerprint.marksState(headers, listOf(row("API411", "12", "14", "13.4", "VORD")), "S4")
        val b = Fingerprint.marksState(headers, listOf(row("API411", "12", "16", "14.8", "VORD")), "S4")
        assertNotEquals(a, b)
    }

    @Test fun elements_outside_semester_are_ignored() {
        // API311 is an S3 element; under S4 it must be filtered out of the state.
        val withForeign = Fingerprint.marksState(
            headers,
            listOf(row("API411", "12", "14", "13.4", "VORD"), row("API311", "9", "9", "9", "NV")),
            "S4",
        )
        val withoutForeign = Fingerprint.marksState(
            headers,
            listOf(row("API411", "12", "14", "13.4", "VORD")),
            "S4",
        )
        assertEquals(withoutForeign, withForeign)
    }

    @Test fun sha256_is_hex_64_chars() {
        val fp = Fingerprint.of(headers, listOf(row("API411", "12", "14", "13.4", "VORD")), "S4")
        assertEquals(64, fp.length)
        assertEquals(true, fp.all { it in "0123456789abcdef" })
    }
}
