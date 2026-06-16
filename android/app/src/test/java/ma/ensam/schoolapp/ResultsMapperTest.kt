package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.OfficialModule
import ma.ensam.schoolapp.domain.model.SemesterResultRow
import ma.ensam.schoolapp.ui.present.ResultsMapper
import org.junit.Assert.assertEquals
import org.junit.Test

class ResultsMapperTest {

    @Test fun maps_titles_and_rank() {
        val extras = Extras(
            modules = mapOf("API43|2024/2025" to OfficialModule("API43", "2024/2025", "13.40", "VRAC")),
            semesters = mapOf("2A|S3|2023/2024" to SemesterResultRow("2A", "S3", "2023/2024", "12.50", "V", "15/120", "--")),
        )
        val v = ResultsMapper.toResultsView(extras)
        assertEquals("Eléments de machine", v.officialModules.single().title)
        val s = v.semesters.single()
        assertEquals("15ᵉ / 120", s.rankText)
        assertEquals(15, s.rankPosition)
        assertEquals(120, s.rankTotal)
    }

    @Test fun unknown_module_falls_back_to_code() {
        val extras = Extras(modules = mapOf("XYZ99|2020/2021" to OfficialModule("XYZ99", "2020/2021", "10.0", "V")))
        assertEquals("XYZ99", ResultsMapper.toResultsView(extras).officialModules.single().title)
    }

    @Test fun rank_parsing_is_graceful() {
        assertEquals(15 to 120, ResultsMapper.parseRank("15/120"))
        assertEquals(null to null, ResultsMapper.parseRank(""))
        assertEquals(null to null, ResultsMapper.parseRank("N/A/x"))
    }

    @Test fun first_place_uses_premier_ordinal() {
        val extras = Extras(semesters = mapOf("2A|S4|2024/2025" to SemesterResultRow("2A", "S4", "2024/2025", "14.0", "V", "1/300", "--")))
        assertEquals("1ᵉʳ / 300", ResultsMapper.toResultsView(extras).semesters.single().rankText)
    }
}
