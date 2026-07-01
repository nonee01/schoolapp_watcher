#!/usr/bin/env python3
"""Capture sanitized SchoolApp HTML fixtures.

Logs in from code (.env credentials - never a browser form), fetches every
per-student page, scrubs PII in memory (real values learned from /index plus a
regex pass), verifies nothing survived, and only then writes
tests/fixtures/*.html. Raw HTML never touches disk; output prints labels and
byte counts, never values.

Usage: .venv/bin/python tests/fixtures/_capture.py
"""
from __future__ import annotations

import html as htmllib
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from schoolapp.client import SchoolAppClient  # noqa: E402

FIXTURES = Path(__file__).resolve().parent
ENV_FILE = FIXTURES.parents[1] / ".env"

PAGES = {
    "profile": "/index",
    "elements_encours": "/student/noteselem-encours",
    "elements_history": "/student/noteselem",
    "modules_encours": "/student/notesmod-encours",
    "modules_history": "/student/notesmod",
    "semesters": "/student/notessem",
    "years": "/student/notesannee",
    "diploma": "/student/notesdiplome",
    "absences": "/student/absence/bilan",
    "sanctions": "/student/absence/sanctions",
    "courses": "/student/inscriptioncours",
    "catalog_form": "/plan-etudes-view/modules",
    "filieres": "/plan-etudes-view/filieres",
}
STATS_PATH = "/notes-stat/elemevalsat"

# label-substring (lowercased, checked in order) -> stable placeholder
LABELED = [
    ("prénom", "Jane"),
    ("prenom", "Jane"),
    ("الاسم", "فلان"),
    ("النسب", "الفلاني"),
    ("nom", "Doe"),
    ("cin", "AA000000"),
    ("cne", "X000000000"),
    ("massar", "X000000000"),
    ("masar", "X000000000"),
    ("matricule", "STU0000"),
    ("code", "STU0000"),
    ("mail", "student@example.test"),
    ("lieu", "Exempleville"),
    ("naissance", "01/01/2000"),
    ("adr", "1 Example Street"),
    ("ville", "Exempleville"),
    ("prof_", "Employé"),
    ("tél", "0600000000"),
    ("tel", "0600000000"),
    ("gsm", "0600000000"),
]

PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "student@example.test"),
    (re.compile(r"\b[A-Z]{1,2}\d{5,7}\b"), "AA000000"),
    (re.compile(r"\b[A-Z]\d{8,10}\b"), "X000000000"),
    (re.compile(r'(src=")[^"]*(?:photo|upload|student)[^"]*(")', re.I), r"\1photo.png\2"),
]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def kv_pairs(html: str) -> list[tuple[str, str]]:
    """Generic label/value harvest: 2-cell table rows and dt/dd pairs."""
    soup = BeautifulSoup(html, "html.parser")
    pairs: list[tuple[str, str]] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) == 2:
            k = " ".join(cells[0].get_text(" ", strip=True).split())
            v = " ".join(cells[1].get_text(" ", strip=True).split())
            if k and v:
                pairs.append((k, v))
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            k = " ".join(dt.get_text(" ", strip=True).split())
            v = " ".join(dd.get_text(" ", strip=True).split())
            if k and v:
                pairs.append((k, v))
    return pairs


def build_exact(pairs: list[tuple[str, str]], env_email: str) -> dict[str, str]:
    exact: dict[str, str] = {}
    for label, value in pairs:
        ll = label.lower().rstrip(" :")
        if len(value) < 4:
            continue
        for needle, fake in LABELED:
            if needle in ll:
                exact.setdefault(value, fake)
                break
    if env_email:
        exact.setdefault(env_email, "student@example.test")
        for tok in re.split(r"[^a-zA-Z]+", env_email.split("@")[0]):
            if len(tok) >= 4:
                exact.setdefault(tok, "Doe")
    return exact


def sanitize(text: str, exact: dict[str, str]) -> str:
    text = htmllib.unescape(text)
    for real in sorted(exact, key=len, reverse=True):
        text = re.sub(re.escape(real), exact[real], text, flags=re.IGNORECASE)
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    return text


def fetch_stats_popup(client: SchoolAppClient, elements_html: str) -> tuple[str, str] | None:
    """Pick the first element row with a real Moy/CC note and fetch its popup."""
    soup = BeautifulSoup(elements_html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None
    best = max(tables, key=lambda t: len(t.find_all("tr")))
    for tr in best.find_all("tr"):
        tds = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if len(tds) < 10 or not tds[0]:
            continue
        for eval_param, idx in (("MoyElem", 8), ("NoteCC", 2)):
            note = tds[idx]
            if note and note != "--":
                params = {"eval": eval_param, "codeelem": tds[0].upper(), "au": tds[1], "note": note}
                print(f"stats popup: {eval_param} for {tds[0].upper()} ({tds[1]})")
                return client._get(STATS_PATH, **params), tds[0].upper()
    return None


def main() -> int:
    env = load_env(ENV_FILE)
    email, password = env.get("SCHOOLAPP_EMAIL", ""), env.get("SCHOOLAPP_PASSWORD", "")
    if not email or not password:
        print("Missing SCHOOLAPP_EMAIL/SCHOOLAPP_PASSWORD in .env")
        return 2

    client = SchoolAppClient(min_interval=0.5)
    client.login(email, password)
    print("login: OK")

    raw: dict[str, str] = {}
    for name, path in PAGES.items():
        try:
            raw[name] = client._get(path)
            print(f"fetched {name:17s} {len(raw[name]):7d} bytes")
        except Exception as exc:  # noqa: BLE001 - capture what we can, report the rest
            print(f"fetched {name:17s} FAILED: {exc}")

    if "elements_encours" in raw:
        popup = fetch_stats_popup(client, raw["elements_encours"])
        if popup:
            raw["stats"] = popup[0]
            print(f"fetched {'stats':17s} {len(popup[0]):7d} bytes")
        else:
            print("stats popup: no numeric note found; skipped")

    pairs = kv_pairs(raw.get("profile", ""))
    print("profile labels:", " | ".join(k for k, _ in pairs) or "(none)")
    exact = build_exact(pairs, email)
    print(f"exact scrub values: {len(exact)}")

    clean: dict[str, str] = {name: sanitize(text, exact) for name, text in raw.items()}

    reals = list(exact)
    failures = [
        (name, f"value#{reals.index(real)}")
        for name, text in clean.items()
        for real in reals
        if re.search(re.escape(real), text, re.IGNORECASE)
    ]
    if failures:
        print("PII SURVIVED SANITIZATION - nothing written:", failures)
        return 1

    FIXTURES.mkdir(exist_ok=True)
    for name, text in clean.items():
        (FIXTURES / f"{name}.html").write_text(text, encoding="utf-8")
    print(f"wrote {len(clean)} sanitized fixtures to {FIXTURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
