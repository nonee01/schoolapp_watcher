package ma.ensam.schoolapp.data.remote

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class TelegramNotifier(
    private val apiBase: String = "https://api.telegram.org",
) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private fun jsonEscape(s: String): String = buildString {
        for (c in s) when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> append(c)
        }
    }

    fun send(token: String, chatId: String, message: String) {
        require(token.isNotBlank() && chatId.isNotBlank()) {
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set"
        }
        val payload = """{"chat_id":"${jsonEscape(chatId)}","text":"${jsonEscape(message)}","parse_mode":"HTML"}"""
        val body = payload.toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url("$apiBase/bot$token/sendMessage").post(body).build()
        http.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful || !text.contains("\"ok\":true")) {
                error("Telegram API error: HTTP ${resp.code} $text")
            }
        }
    }
}
