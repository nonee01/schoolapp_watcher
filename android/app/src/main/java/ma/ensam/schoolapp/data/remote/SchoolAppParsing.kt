package ma.ensam.schoolapp.data.remote

import org.jsoup.Jsoup

/** Pure HTML-parsing helpers, translated from BeautifulSoup logic in watcher.py. */
object SchoolAppParsing {

    fun normalizeCell(text: String): String =
        text.trim().replace(Regex("\\s+"), " ")

    fun extractCsrf(html: String): String? {
        val token = Jsoup.parse(html).selectFirst("input[name=_csrf]") ?: return null
        val value = token.attr("value")
        return value.ifEmpty { null }
    }

    fun looksLikeLoginPage(html: String): Boolean {
        val doc = Jsoup.parse(html)
        return doc.selectFirst("form[action=/login]") != null &&
            doc.selectFirst("input[name=password]") != null
    }

    /** Largest <table> by row count -> (headers, rows). Mirrors _extract_table. */
    fun extractTable(html: String): Pair<List<String>, List<List<String>>> {
        val doc = Jsoup.parse(html)
        val tables = doc.select("table")
        if (tables.isEmpty()) error("No table found on marks page")

        val best = tables.maxByOrNull { it.select("tr").size }!!
        val headers = best.select("th").map { normalizeCell(it.text()) }

        val rows = ArrayList<List<String>>()
        for (tr in best.select("tr")) {
            val tds = tr.select("td")
            if (tds.isEmpty()) continue
            val row = tds.map { normalizeCell(it.text()) }
            if (row.any { it.isNotEmpty() }) rows.add(row)
        }
        return headers to rows
    }
}
