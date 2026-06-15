package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.ExtrasJson
import ma.ensam.schoolapp.domain.model.Absence
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import org.junit.Assert.assertEquals
import org.junit.Test

class ExtrasJsonTest {
    @Test fun round_trips_all_sections() {
        val extras = Extras(
            absences = mapOf("API411|2024-03-12|S1" to Absence("API411", "2024-03-12", "S1", "true", "retard")),
            sanctions = mapOf("Message" to "Avertissement"),
            modules = mapOf("API41|2023/2024" to OfficialModule("API41", "2023/2024", "13.40", "VRAC")),
            semesters = mapOf("2A|S3|2023/2024" to SemesterResultRow("2A", "S3", "2023/2024", "12.50", "V", "15/120", "--")),
        )
        val json = ExtrasJson.toJson(extras)
        val back = ExtrasJson.fromJson(json)
        assertEquals(extras.absences, back.absences)
        assertEquals(extras.sanctions, back.sanctions)
        assertEquals(extras.modules, back.modules)
        assertEquals(extras.semesters, back.semesters)
    }

    @Test fun empty_and_malformed_yield_empty() {
        assertEquals(Extras(), ExtrasJson.fromJson("{}"))
        assertEquals(Extras(), ExtrasJson.fromJson(""))
        assertEquals(Extras(), ExtrasJson.fromJson("not json"))
    }
}
