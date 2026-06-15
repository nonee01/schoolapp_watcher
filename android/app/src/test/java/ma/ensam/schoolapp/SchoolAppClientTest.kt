package ma.ensam.schoolapp

import kotlinx.coroutines.runBlocking
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SchoolAppClientTest {
    private lateinit var server: MockWebServer

    @Before fun setUp() { server = MockWebServer(); server.start() }
    @After fun tearDown() { server.shutdown() }

    private fun baseUrl() = server.url("/").toString().trimEnd('/')

    private fun loginPage(csrf: String) =
        """<form action="/login"><input name="_csrf" value="$csrf"/><input name="password"/></form>"""

    private val tableHtml =
        """<table>
             <tr><th>CodeElem</th><th>CC</th><th>Moy</th></tr>
             <tr><td>API411</td><td>12</td><td>13.4</td></tr>
           </table>"""

    @Test fun valid_session_returns_table_directly() = runBlocking {
        server.enqueue(MockResponse().setBody(tableHtml))

        val client = SchoolAppClient(baseUrl = baseUrl())
        val snap = client.checkOnce(email = "me@x.ma", password = "pw", semester = "S4")

        assertEquals(listOf("CodeElem", "CC", "Moy"), snap.headers)
        assertEquals(1, snap.rows.size)
        assertEquals("API411", snap.rows[0][0])
        assertEquals(64, snap.fingerprint.length)

        val req = server.takeRequest()
        assertEquals("/student/noteselem-encours", req.path)
    }

    @Test fun reauthenticates_when_session_expired() = runBlocking {
        server.enqueue(MockResponse().setBody(loginPage("tokA"))) // GET marks -> login page
        server.enqueue(MockResponse().setBody(loginPage("tokB"))) // GET /login (inside login())
        server.enqueue(MockResponse().setBody("ok"))               // POST /login
        server.enqueue(MockResponse().setBody(tableHtml))          // GET marks -> real table

        val client = SchoolAppClient(baseUrl = baseUrl())
        val snap = client.checkOnce(email = "me@x.ma", password = "pw", semester = "S4")
        assertEquals("API411", snap.rows[0][0])

        server.takeRequest() // GET marks
        val getLogin = server.takeRequest()
        assertEquals("/login", getLogin.path)
        val post = server.takeRequest()
        assertEquals("POST", post.method)
        assertTrue(post.body.readUtf8().contains("_csrf=tokB"))
    }

    @Test(expected = IllegalStateException::class)
    fun bad_credentials_throw() = runBlocking {
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET marks -> login page
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET /login
        server.enqueue(MockResponse().setBody("ok"))            // POST /login
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET marks -> STILL login -> throw
        SchoolAppClient(baseUrl = baseUrl()).checkOnce("me@x.ma", "wrong", "S4")
        Unit
    }
}
