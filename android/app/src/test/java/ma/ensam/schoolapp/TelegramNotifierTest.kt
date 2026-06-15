package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.TelegramNotifier
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class TelegramNotifierTest {
    private lateinit var server: MockWebServer
    @Before fun setUp() { server = MockWebServer(); server.start() }
    @After fun tearDown() { server.shutdown() }

    @Test fun posts_message_with_html_parse_mode() {
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))
        val notifier = TelegramNotifier(apiBase = server.url("/").toString().trimEnd('/'))
        notifier.send(token = "T", chatId = "C", message = "<b>hi</b>")

        val req = server.takeRequest()
        assertTrue(req.path!!.contains("/botT/sendMessage"))
        val body = req.body.readUtf8()
        assertTrue(body.contains("\"chat_id\":\"C\""))
        assertTrue(body.contains("\"parse_mode\":\"HTML\""))
        assertTrue(body.contains("<b>hi</b>"))
    }

    @Test(expected = IllegalStateException::class)
    fun api_error_throws() {
        server.enqueue(MockResponse().setBody("""{"ok":false,"description":"bad"}"""))
        TelegramNotifier(apiBase = server.url("/").toString().trimEnd('/'))
            .send(token = "T", chatId = "C", message = "x")
    }

    @Test(expected = IllegalArgumentException::class)
    fun blank_token_throws() {
        TelegramNotifier().send(token = "", chatId = "C", message = "x")
    }
}
