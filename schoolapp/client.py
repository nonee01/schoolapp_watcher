from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup

SCHOOLAPP_BASE = "https://schoolapp.ensam-umi.ac.ma"
LOGIN_PATH = "/login"


def extract_csrf(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    token = soup.select_one('input[name="_csrf"]')
    if not token:
        return None
    value = token.get("value")
    return value if isinstance(value, str) and value else None


def looks_like_login_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one('form[action="/login"]') and soup.select_one('input[name="password"]'))


class SchoolAppClient:
    """Authenticated session facade. Owns all HTTP/login I/O; re-auths once on expiry."""

    def __init__(self, base_url: str = SCHOOLAPP_BASE, session: requests.Session | None = None,
                 timeout: int = 20, min_interval: float = 0.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.min_interval = min_interval
        self._email: str | None = None
        self._password: str | None = None
        self._last_request = 0.0

    def _throttle(self) -> None:
        if self.min_interval > 0:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()

    def login(self, email: str, password: str) -> None:
        self._email, self._password = email, password
        self._do_login()

    def _do_login(self) -> None:
        self._throttle()
        r = self.session.get(self.base_url + LOGIN_PATH, timeout=self.timeout)
        r.raise_for_status()
        csrf = extract_csrf(r.text)
        if not csrf:
            raise RuntimeError("Login page changed: CSRF token missing")
        self._throttle()
        payload = {"email": self._email, "password": self._password, "_csrf": csrf}
        page = self.session.post(self.base_url + LOGIN_PATH, data=payload, timeout=self.timeout)
        page.raise_for_status()
        if looks_like_login_page(page.text):
            raise RuntimeError("Login failed: verify email/password")

    def _get(self, path: str, **params: str) -> str:
        return self._request("GET", path, params=params)

    def _post(self, path: str, data: dict) -> str:
        return self._request("POST", path, data=data)

    def _request(self, method: str, path: str, params: dict | None = None,
                 data: dict | None = None, _retried: bool = False) -> str:
        self._throttle()
        url = self.base_url + path
        if method == "GET":
            resp = self.session.get(url, params=params or {}, timeout=self.timeout)
        else:
            resp = self.session.post(url, data=data or {}, timeout=self.timeout)
        resp.raise_for_status()
        if looks_like_login_page(resp.text):
            if _retried or not self._email:
                raise RuntimeError("Session expired and re-authentication failed")
            self._do_login()
            return self._request(method, path, params=params, data=data, _retried=True)
        return resp.text
