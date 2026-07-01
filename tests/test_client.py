import pytest

from schoolapp.client import SchoolAppClient, extract_csrf, looks_like_login_page

LOGIN_HTML = '<form action="/login"><input name="password"><input name="_csrf" value="TOK"></form>'
DASH_HTML = "<h1>Bienvenue</h1>"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    """Serves queued responses; records every request as (method, url, data)."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def _next(self, method, url, data):
        self.calls.append((method, url, data))
        return FakeResponse(self._script.pop(0))

    def get(self, url, params=None, timeout=None):
        return self._next("GET", url, None)

    def post(self, url, data=None, timeout=None):
        return self._next("POST", url, data)


def test_extract_csrf_and_login_page_detection():
    assert extract_csrf(LOGIN_HTML) == "TOK"
    assert extract_csrf(DASH_HTML) is None
    assert looks_like_login_page(LOGIN_HTML) is True
    assert looks_like_login_page(DASH_HTML) is False


def test_login_posts_csrf_token():
    session = FakeSession([LOGIN_HTML, DASH_HTML])  # GET login page, POST -> dashboard
    client = SchoolAppClient(session=session)
    client.login("me@example.test", "pw")
    method, url, data = session.calls[1]
    assert method == "POST"
    assert url.endswith("/login")
    assert data == {"email": "me@example.test", "password": "pw", "_csrf": "TOK"}


def test_login_failure_raises():
    session = FakeSession([LOGIN_HTML, LOGIN_HTML])  # POST still returns login page
    client = SchoolAppClient(session=session)
    with pytest.raises(RuntimeError, match="Login failed"):
        client.login("me@example.test", "bad")


def test_get_reauths_once_on_session_expiry():
    # login (2), then _get: first hit returns login page -> re-login (2) -> retry returns content
    session = FakeSession([LOGIN_HTML, DASH_HTML, LOGIN_HTML, LOGIN_HTML, DASH_HTML, "PAYLOAD"])
    client = SchoolAppClient(session=session)
    client.login("me@example.test", "pw")
    assert client._get("/student/notessem") == "PAYLOAD"


def test_min_interval_throttles(monkeypatch):
    sleeps = []
    monkeypatch.setattr("schoolapp.client.time.sleep", lambda s: sleeps.append(s))
    session = FakeSession([LOGIN_HTML, DASH_HTML])
    client = SchoolAppClient(session=session, min_interval=5.0)
    client.login("me@example.test", "pw")
    assert any(s > 0 for s in sleeps)  # throttled between the GET and POST
