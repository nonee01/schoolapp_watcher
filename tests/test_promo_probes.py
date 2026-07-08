"""Semester & année rank probes reuse the elemstat mechanism."""
import requests
from schoolapp.client import SCHOOLAPP_BASE, SchoolAppClient


def _popup(rank: int, effectif: int) -> str:
    # Synthetic /notes-stat popup: div.stat > p title + a th/td table. No PII.
    return (
        '<div class="stat"><p>Statistiques</p><table>'
        '<tr><th>Votre note</th><td>10.0</td></tr>'
        '<tr><th>Moyenne promo</th><td>12.05</td></tr>'
        '<tr><th>Max</th><td>16.85</td></tr>'
        '<tr><th>Min</th><td>0.25</td></tr>'
        '<tr><th>Ecart type</th><td>1.91</td></tr>'
        f'<tr><th>Effectif</th><td>{effectif}</td></tr>'
        f'<tr><th>Votre classement</th><td>{rank}</td></tr>'
        '</table></div>'
    )


class RankSession:
    """Serves a popup whose rank = 1 + #students strictly above the probed note.
    Distribution: notes [0, 5, 5, 12, 20] over effectif=5."""
    NOTES = [0.0, 5.0, 5.0, 12.0, 20.0]

    def __init__(self):
        self.logged_in = True
        self.calls = []

    def get(self, url, params=None, timeout=None):
        path = url.replace(SCHOOLAPP_BASE, "")
        self.calls.append((path, dict(params or {})))
        note = float(params.get("note", 0))
        rank = 1 + sum(1 for n in self.NOTES if n > note)
        return _Resp(_popup(rank, len(self.NOTES)))

    def post(self, url, data=None, timeout=None):
        return _Resp("<html>bienvenue</html>")


class _Resp:
    def __init__(self, text): self.text, self.status_code, self.headers = text, 200, {"Content-Type": "text/html"}
    def raise_for_status(self): pass


def _client():
    s = RankSession()
    c = SchoolAppClient(session=s)
    c._email, c._password = "e", "p"  # skip login network
    return c, s


def test_rank_for_note_sem_hits_semsat_with_all_params():
    c, s = _client()
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", 12.0) == (2, 5)
    path, params = s.calls[-1]
    assert path == "/notes-stat/semsat"
    assert params == {"eval": "MoySem", "niveau": "1A", "filiere": "API-MPT",
                      "semestre": "S1", "au": "2024-2025", "note": "12.0"}


def test_rank_for_note_year_hits_anneesat_with_all_params():
    c, s = _client()
    assert c.rank_for_note_year("2A", "API-MPT", "2025-2026", 20.0) == (1, 5)
    path, params = s.calls[-1]
    assert path == "/notes-stat/anneesat"
    assert params == {"eval": "MoyAn", "niveau": "2A", "filiere": "API-MPT",
                      "au": "2025-2026", "note": "20.0"}


def test_rank_is_monotonic_bracketing_the_promotion():
    c, s = _client()
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", -1)[0] == 6   # below all
    assert c.rank_for_note_sem("1A", "API-MPT", "S1", "2024-2025", 20.5)[0] == 1  # above all


def test_stat_probe_returns_full_aggregate_dict():
    c, s = _client()
    d = c._stat_probe("/notes-stat/semsat",
                      {"eval": "MoySem", "niveau": "1A", "filiere": "API-MPT",
                       "semestre": "S1", "au": "2024-2025", "note": "10"})
    assert d["Effectif"] == "5" and d["Moyenne promo"] == "12.05"
    assert d["Min"] == "0.25" and d["Max"] == "16.85" and d["Ecart type"] == "1.91"
