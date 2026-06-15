package ma.ensam.schoolapp.data.remote

import ma.ensam.schoolapp.data.Fingerprint
import ma.ensam.schoolapp.domain.model.Snapshot
import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

class SchoolAppClient(
    private val baseUrl: String = "https://schoolapp.ensam-umi.ac.ma",
    private val timeoutSeconds: Long = 20,
) {
    private val cookieJar = InMemoryCookieJar()
    private val http = OkHttpClient.Builder()
        .cookieJar(cookieJar)
        .followRedirects(true)
        .followSslRedirects(true)
        .connectTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .readTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .build()

    private val loginUrl get() = "$baseUrl/login"
    private val marksUrl get() = "$baseUrl/student/noteselem-encours"

    private fun get(url: String): String {
        val req = Request.Builder().url(url)
            .header("User-Agent", "schoolapp-android/1.0").build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("GET $url failed: HTTP ${resp.code}")
            return resp.body?.string().orEmpty()
        }
    }

    private fun login(email: String, password: String) {
        val page = get(loginUrl)
        val csrf = SchoolAppParsing.extractCsrf(page)
            ?: error("Login page changed: CSRF token missing")
        val form = FormBody.Builder()
            .add("email", email).add("password", password).add("_csrf", csrf).build()
        val req = Request.Builder().url(loginUrl).post(form)
            .header("Referer", loginUrl)
            .header("User-Agent", "schoolapp-android/1.0").build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("Login POST failed: HTTP ${resp.code}")
        }
    }

    /**
     * Mirrors check_once login handling: fetch marks; if it looks like the
     * login page, authenticate and retry once. Returns a Snapshot of the table.
     */
    fun checkOnce(email: String, password: String, semester: String): Snapshot {
        var html = get(marksUrl)
        if (SchoolAppParsing.looksLikeLoginPage(html)) {
            login(email, password)
            html = get(marksUrl)
            if (SchoolAppParsing.looksLikeLoginPage(html)) {
                error("Login failed: verify email/password")
            }
        }
        val (headers, rows) = SchoolAppParsing.extractTable(html)
        return Snapshot(
            headers = headers,
            rows = rows,
            fingerprint = Fingerprint.of(headers, rows, semester),
        )
    }

    private val absenceUrl get() = "$baseUrl/student/absence/bilan"
    private val sanctionsUrl get() = "$baseUrl/student/absence/sanctions"
    private val modulesUrl get() = "$baseUrl/student/notesmod-encours"
    private val semestersUrl get() = "$baseUrl/student/notessem"

    /**
     * Fetch the four extra pages. Assumes the session is already authenticated
     * (call checkOnce first in the same client). A page that fails or looks like
     * the login page yields an empty section (caller carries old state forward).
     */
    fun fetchExtras(): ma.ensam.schoolapp.domain.model.Extras {
        fun safe(url: String): String? = try {
            val html = get(url)
            if (SchoolAppParsing.looksLikeLoginPage(html)) null else html
        } catch (e: Exception) { null }

        val abs = safe(absenceUrl)?.let { SchoolAppExtrasParsing.parseAbsenceLog(it) } ?: emptyMap()
        val san = safe(sanctionsUrl)?.let { SchoolAppExtrasParsing.parseSanctions(it) } ?: emptyMap()
        val mods = safe(modulesUrl)?.let { SchoolAppExtrasParsing.parseModulesEncours(it) } ?: emptyMap()
        val sems = safe(semestersUrl)?.let { SchoolAppExtrasParsing.parseSemesterResults(it) } ?: emptyMap()
        return ma.ensam.schoolapp.domain.model.Extras(abs, san, mods, sems)
    }
}
