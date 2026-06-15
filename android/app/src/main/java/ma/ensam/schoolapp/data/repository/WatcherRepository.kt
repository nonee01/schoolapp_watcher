package ma.ensam.schoolapp.data.repository

import ma.ensam.schoolapp.data.Fingerprint
import ma.ensam.schoolapp.data.db.HistoryEntity
import ma.ensam.schoolapp.data.db.SnapshotEntity
import ma.ensam.schoolapp.data.db.WatcherDao
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.data.remote.TelegramNotifier
import ma.ensam.schoolapp.domain.Diff
import ma.ensam.schoolapp.domain.model.Snapshot
import org.json.JSONArray
import javax.inject.Inject

data class CheckResult(val changed: Boolean, val summary: String)

class WatcherRepository @Inject constructor(
    private val client: SchoolAppClient,
    private val dao: WatcherDao,
    private val prefs: EncryptedPrefs,
    private val telegram: TelegramNotifier,
) {
    suspend fun runCheck(): CheckResult {
        val email = prefs.email
        val password = prefs.password
        val semester = prefs.semester
        check(email.isNotBlank() && password.isNotBlank()) { "Credentials not configured" }

        val snap = client.checkOnce(email, password, semester)
        val old = dao.getSnapshot(semester)
        val oldSnapshot = old?.let { Snapshot(jsonToHeaders(it.headersJson), jsonToRows(it.rowsJson), it.fingerprint) }

        val changed = oldSnapshot == null ||
            Fingerprint.marksState(oldSnapshot.headers, oldSnapshot.rows, semester) !=
            Fingerprint.marksState(snap.headers, snap.rows, semester)

        val extrasJson = old?.extrasJson ?: "{}"
        dao.upsertSnapshot(
            SnapshotEntity(
                semester = semester,
                headersJson = headersToJson(snap.headers),
                rowsJson = rowsToJson(snap.rows),
                fingerprint = snap.fingerprint,
                extrasJson = extrasJson,
                updatedAt = System.currentTimeMillis(),
            )
        )

        if (!changed) return CheckResult(false, "No change")

        val changes = if (oldSnapshot != null) Diff.compute(oldSnapshot, snap, semester) else emptyList()
        val names = changes.take(3).joinToString(", ") { it.code }
        val summary = if (oldSnapshot == null) "Initialized $semester snapshot"
            else "Grades updated ($semester): ${names.ifEmpty { "changes detected" }}"

        if (oldSnapshot != null) {
            dao.insertHistory(HistoryEntity(timestamp = System.currentTimeMillis(), type = "grades", semester = semester, summary = summary))
            notify(summary, changes)
        }
        return CheckResult(oldSnapshot != null, summary)
    }

    private fun notify(summary: String, changes: List<ma.ensam.schoolapp.domain.ElementChange>) {
        val token = prefs.telegramToken
        val chat = prefs.telegramChatId
        if (token.isBlank() || chat.isBlank()) return
        val body = buildString {
            append("📚 <b>$summary</b>\n")
            changes.take(10).forEach { c ->
                val kind = if (c.isNew) "NOUVEAU" else "MODIFIÉ"
                append("\n<b>${c.code}</b> ($kind)")
                c.fields.entries.take(4).forEach { (f, ov) -> append("\n$f: ${ov.first}->${ov.second}") }
            }
        }
        runCatching { telegram.send(token, chat, body) }
    }

    private fun headersToJson(h: List<String>) = JSONArray(h).toString()
    private fun rowsToJson(rows: List<List<String>>): String {
        val outer = JSONArray()
        rows.forEach { outer.put(JSONArray(it)) }
        return outer.toString()
    }
    private fun jsonToHeaders(s: String): List<String> {
        val a = JSONArray(s); return (0 until a.length()).map { a.getString(it) }
    }
    private fun jsonToRows(s: String): List<List<String>> {
        val outer = JSONArray(s)
        return (0 until outer.length()).map { i ->
            val inner = outer.getJSONArray(i)
            (0 until inner.length()).map { inner.getString(it) }
        }
    }
}
