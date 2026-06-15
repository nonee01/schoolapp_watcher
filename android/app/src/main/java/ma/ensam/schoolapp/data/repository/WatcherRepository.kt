package ma.ensam.schoolapp.data.repository

import kotlinx.coroutines.flow.Flow
import ma.ensam.schoolapp.data.ExtrasJson
import ma.ensam.schoolapp.data.Fingerprint
import ma.ensam.schoolapp.data.db.HistoryEntity
import ma.ensam.schoolapp.data.db.SnapshotEntity
import ma.ensam.schoolapp.data.db.WatcherDao
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.data.remote.TelegramNotifier
import ma.ensam.schoolapp.domain.Diff
import ma.ensam.schoolapp.domain.ElementChange
import ma.ensam.schoolapp.domain.ExtrasDiff
import ma.ensam.schoolapp.domain.model.Extras
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
        val newExtras = runCatching { client.fetchExtras() }.getOrDefault(Extras())

        val old = dao.getSnapshot(semester)
        val oldSnapshot = old?.let { Snapshot(jsonToHeaders(it.headersJson), jsonToRows(it.rowsJson), it.fingerprint) }
        val oldExtras = old?.let { ExtrasJson.fromJson(it.extrasJson) } ?: Extras()

        val gradesChanged = oldSnapshot == null ||
            Fingerprint.marksState(oldSnapshot.headers, oldSnapshot.rows, semester) !=
            Fingerprint.marksState(snap.headers, snap.rows, semester)
        val extrasMsgs = if (old != null) ExtrasDiff.summaries(oldExtras, newExtras) else emptyList()

        dao.upsertSnapshot(
            SnapshotEntity(
                semester = semester,
                headersJson = headersToJson(snap.headers),
                rowsJson = rowsToJson(snap.rows),
                fingerprint = snap.fingerprint,
                extrasJson = ExtrasJson.toJson(newExtras),
                updatedAt = System.currentTimeMillis(),
            )
        )

        val firstRun = oldSnapshot == null
        if (firstRun) return CheckResult(false, "Initialized $semester snapshot")

        val changed = gradesChanged || extrasMsgs.isNotEmpty()
        if (!changed) return CheckResult(false, "No change")

        val now = System.currentTimeMillis()
        val parts = ArrayList<String>()

        if (gradesChanged) {
            val changes = Diff.compute(oldSnapshot!!, snap, semester)
            val names = changes.take(3).joinToString(", ") { it.code }
            val gradeSummary = "Grades updated ($semester): ${names.ifEmpty { "changes detected" }}"
            dao.insertHistory(HistoryEntity(timestamp = now, type = "grades", semester = semester, summary = gradeSummary))
            parts.add(gradeSummary)
            telegramGrades(gradeSummary, changes)
        }
        for (msg in extrasMsgs) {
            val type = when {
                msg.contains("Absence") || msg.contains("Sanction") -> "absences"
                msg.contains("Module") -> "modules"
                msg.contains("🎓") -> "semesters"
                else -> "extras"
            }
            dao.insertHistory(HistoryEntity(timestamp = now, type = type, semester = semester, summary = msg))
            parts.add(msg)
        }
        if (extrasMsgs.isNotEmpty()) telegramText(extrasMsgs.joinToString("\n"))

        val summary = parts.firstOrNull() ?: "SchoolApp update ($semester)"
        return CheckResult(true, summary)
    }

    private fun telegramGrades(summary: String, changes: List<ElementChange>) {
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

    private fun telegramText(text: String) {
        val token = prefs.telegramToken
        val chat = prefs.telegramChatId
        if (token.isBlank() || chat.isBlank()) return
        runCatching { telegram.send(token, chat, text) }
    }

    suspend fun latestSnapshot(semester: String): Snapshot? {
        val e = dao.getSnapshot(semester) ?: return null
        return Snapshot(jsonToHeaders(e.headersJson), jsonToRows(e.rowsJson), e.fingerprint)
    }

    suspend fun latestExtras(semester: String): Extras {
        val e = dao.getSnapshot(semester) ?: return Extras()
        return ExtrasJson.fromJson(e.extrasJson)
    }

    fun historyFlow(limit: Int): Flow<List<HistoryEntity>> = dao.historyFlow(limit)

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
