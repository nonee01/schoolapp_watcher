package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.SnapshotMarks
import ma.ensam.schoolapp.domain.model.Snapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SnapshotMarksTest {
    @Test fun maps_cc_ex_tp_rat_and_aliases_ex_to_ecrit() {
        val snap = Snapshot(
            headers = listOf("CodeElem", "CC", "EX", "TP", "RAT"),
            rows = listOf(
                listOf("API411", "14", "8", "--", "--"),
                listOf("API421", "12.5", "--", "--", "16"),
            ),
            fingerprint = "fp",
        )
        val m = SnapshotMarks.fromSnapshot(snap)
        assertEquals(14.0, m["API411.cc"]!!, 0.0001)
        assertEquals(8.0, m["API411.ex"]!!, 0.0001)
        assertEquals(8.0, m["API411.ecrit"]!!, 0.0001)
        assertEquals(16.0, m["API421.rat"]!!, 0.0001)
        assertNull(m["API421.ex"])   // "--" is not numeric
    }

    @Test fun no_code_column_yields_empty() {
        val snap = Snapshot(listOf("CC", "EX"), listOf(listOf("10", "12")), "fp")
        assertEquals(emptyMap<String, Double>(), SnapshotMarks.fromSnapshot(snap))
    }
}
