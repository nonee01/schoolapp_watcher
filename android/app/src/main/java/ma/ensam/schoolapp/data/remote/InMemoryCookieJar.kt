package ma.ensam.schoolapp.data.remote

import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

/** Simple per-host in-memory cookie store; survives across requests in one client. */
class InMemoryCookieJar : CookieJar {
    private val store = HashMap<String, MutableList<Cookie>>()

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val host = url.host
        val list = store.getOrPut(host) { mutableListOf() }
        for (c in cookies) {
            list.removeAll { it.name == c.name }
            list.add(c)
        }
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        val list = store[url.host] ?: return emptyList()
        list.removeAll { it.expiresAt < now }
        return list.toList()
    }

    @Synchronized
    fun clear() = store.clear()
}
