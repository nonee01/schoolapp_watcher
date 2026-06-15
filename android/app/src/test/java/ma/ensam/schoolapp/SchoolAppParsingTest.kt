package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.SchoolAppParsing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SchoolAppParsingTest {

    @Test fun extracts_csrf_token() {
        val html = """<form action="/login"><input name="_csrf" value="abc123"/></form>"""
        assertEquals("abc123", SchoolAppParsing.extractCsrf(html))
    }

    @Test fun missing_csrf_returns_null() {
        assertNull(SchoolAppParsing.extractCsrf("<form action=\"/login\"></form>"))
    }

    @Test fun detects_login_page() {
        val html = """<form action="/login"><input name="password" type="password"/></form>"""
        assertTrue(SchoolAppParsing.looksLikeLoginPage(html))
    }

    @Test fun marks_page_is_not_login_page() {
        val html = "<table><tr><th>CodeElem</th></tr></table>"
        assertFalse(SchoolAppParsing.looksLikeLoginPage(html))
    }

    @Test fun normalize_collapses_whitespace() {
        assertEquals("a b c", SchoolAppParsing.normalizeCell("  a\n  b\t c  "))
    }

    @Test fun extracts_largest_table_headers_and_rows() {
        val html = """
            <table><tr><th>x</th></tr><tr><td>1</td></tr></table>
            <table>
              <tr><th>CodeElem</th><th>CC</th><th>Moy</th></tr>
              <tr><td>API411</td><td>12</td><td>13.4</td></tr>
              <tr><td>API421</td><td>10</td><td>10.7</td></tr>
            </table>
        """.trimIndent()
        val (headers, rows) = SchoolAppParsing.extractTable(html)
        assertEquals(listOf("CodeElem", "CC", "Moy"), headers)
        assertEquals(2, rows.size)
        assertEquals(listOf("API411", "12", "13.4"), rows[0])
    }

    @Test fun extract_table_throws_when_no_table() {
        try {
            SchoolAppParsing.extractTable("<div>no tables here</div>")
            throw AssertionError("expected exception")
        } catch (e: IllegalStateException) {
            assertTrue(e.message!!.contains("No table"))
        }
    }
}
