package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.SchoolAppExtrasParsing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SchoolAppExtrasParsingTest {

    @Test fun parses_absence_log() {
        val html = """
            <table>
              <tr><th>Element</th><th>Date</th><th>Seance</th><th>Justif</th><th>Remarques</th></tr>
              <tr><td>API411</td><td>2024-03-12 08:00</td><td>S1</td><td>True</td><td>retard</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseAbsenceLog(html)
        assertEquals(1, out.size)
        val a = out["API411|2024-03-12|S1"]!!
        assertEquals("API411", a.element)
        assertEquals("2024-03-12", a.date)
        assertEquals("S1", a.seance)
        assertEquals("true", a.justif)
        assertEquals("retard", a.remarks)
    }

    @Test fun parses_sanctions_first_nonempty_table() {
        val html = """<table><tr><td>Message</td><td>Avertissement</td></tr>
                      <tr><td>Niveau</td><td>1</td></tr></table>"""
        val out = SchoolAppExtrasParsing.parseSanctions(html)
        assertEquals("Avertissement", out["Message"])
        assertEquals("1", out["Niveau"])
    }

    @Test fun parses_official_modules() {
        val html = """
            <table>
              <tr><th>CodeMod</th><th>AU</th><th>Moy</th><th>Dec</th></tr>
              <tr><td>API41</td><td>2023/2024</td><td>13.40</td><td>VRAC</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseModulesEncours(html)
        val m = out["API41|2023/2024"]!!
        assertEquals("API41", m.code)
        assertEquals("13.40", m.moy)
        assertEquals("VRAC", m.dec)
    }

    @Test fun parses_semester_results_with_decision_typo() {
        val html = """
            <table>
              <tr><th>Niveau</th><th>Semestre</th><th>AU</th><th>Moy SEM</th><th>Decesion</th><th>Classement</th><th>PJ</th></tr>
              <tr><td>2A</td><td>S3</td><td>2023/2024</td><td>12.50</td><td>V</td><td>15/120</td><td>--</td></tr>
            </table>"""
        val out = SchoolAppExtrasParsing.parseSemesterResults(html)
        val s = out["2A|S3|2023/2024"]!!
        assertEquals("12.50", s.moy)
        assertEquals("V", s.dec)
        assertEquals("15/120", s.rank)
    }

    @Test fun missing_table_yields_empty() {
        assertTrue(SchoolAppExtrasParsing.parseAbsenceLog("<div/>").isEmpty())
        assertTrue(SchoolAppExtrasParsing.parseModulesEncours("<div/>").isEmpty())
        assertTrue(SchoolAppExtrasParsing.parseSemesterResults("<div/>").isEmpty())
    }
}
