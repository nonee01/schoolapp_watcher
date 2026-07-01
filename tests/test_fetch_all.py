import requests

from schoolapp.client import SCHOOLAPP_BASE, SchoolAppClient
from tests.conftest import FIXTURES

LOGIN_FORM = ('<html><form action="/login"><input name="_csrf" value="tok"/>'
              '<input name="password"/></form></html>')

PAGES = {
    "/index": "profile",
    "/student/noteselem-encours": "elements_encours",
    "/student/noteselem": "elements_history",
    "/student/notesmod-encours": "modules_encours",
    "/student/notesmod": "modules_history",
    "/student/notessem": "semesters",
    "/student/notesannee": "years",
    "/student/notesdiplome": "diploma",
    "/student/absence/bilan": "absences",
    "/student/absence/sanctions": "sanctions",
    "/student/inscriptioncours": "courses",
    "/notes-stat/elemevalsat": "stats",
}


class FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    """Serves the sanitized fixtures; requires a login POST first, like the portal."""

    def __init__(self, fail_paths=()):
        self.fail_paths = set(fail_paths)
        self.logged_in = False
        self.requests: list[str] = []

    def _page(self, path: str) -> FakeResponse:
        if path == "/login" or not self.logged_in:
            return FakeResponse(LOGIN_FORM)
        name = PAGES.get(path)
        if name is None:
            return FakeResponse("<html><body>rien</body></html>")
        return FakeResponse((FIXTURES / f"{name}.html").read_text(encoding="utf-8"))

    def get(self, url, params=None, timeout=None):
        path = url.replace(SCHOOLAPP_BASE, "")
        self.requests.append(path)
        if path in self.fail_paths:
            raise requests.ConnectionError(f"boom {path}")
        return self._page(path)

    def post(self, url, data=None, timeout=None):
        path = url.replace(SCHOOLAPP_BASE, "")
        self.requests.append(path)
        if path == "/login":
            self.logged_in = True
            return FakeResponse("<html><body>bienvenue</body></html>")
        return self._page(path)


def make_client(fail_paths=()):
    session = FakeSession(fail_paths)
    client = SchoolAppClient(session=session)
    client.login("student@example.test", "hunter2")
    return client, session


def test_fetch_all_populates_every_resource():
    client, _ = make_client()
    data = client.fetch_all()
    assert data.errors == {}
    assert data.profile is not None and data.profile.nom == "Doe"
    assert len(data.element_grades) == 46  # 24 current + 22 history, no (code, au) overlap
    assert len(data.module_grades) == 28
    assert len(data.semester_results) == 3
    assert len(data.year_results) == 1
    assert data.diploma is not None and data.diploma.empty is True
    assert len(data.absences) == 6
    assert len(data.absence_summary) == 23
    assert len(data.sanctions) == 4
    assert len(data.courses) == 23
    assert len(data.documents) == 5
    assert data.stats == []  # include_stats defaults to False
    assert data.fetched_at


def test_fetch_all_without_history():
    client, session = make_client()
    data = client.fetch_all(include_history=False)
    assert len(data.element_grades) == 24
    assert len(data.module_grades) == 14
    assert "/student/noteselem" not in session.requests
    assert "/student/notesmod" not in session.requests


def test_fetch_all_isolates_resource_failures():
    client, _ = make_client(fail_paths={"/student/absence/bilan"})
    data = client.fetch_all()
    assert "absences" in data.errors and "boom" in data.errors["absences"]
    assert data.absences == [] and data.absence_summary == []
    # every other resource still populated
    assert data.profile is not None
    assert len(data.element_grades) == 46
    assert len(data.sanctions) == 4


def test_fetch_all_with_stats_fetches_current_elements_only():
    client, session = make_client()
    data = client.fetch_all(include_stats=True)
    popups = [p for p in session.requests if p == "/notes-stat/elemevalsat"]
    with_moy = [g for g in data.element_grades[:24] if g.moy and g.moy != "--"]
    assert len(popups) == len(with_moy) > 0
    assert len(data.stats) == len(popups)
    assert data.stats[0].eval_kind == "MoyElem"


def test_mark_statistics_for_one_element():
    client, _ = make_client()
    stats = client.mark_statistics("api311", eval_kind="moy")
    assert len(stats) == 1
    assert stats[0].element == "API311"
    assert ["Votre note", "14.93"] in stats[0].rows


def test_mark_statistics_unknown_element_is_empty():
    client, _ = make_client()
    assert client.mark_statistics("ZZZ999") == []
