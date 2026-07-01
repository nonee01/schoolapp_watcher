---
name: sanitizing-schoolapp-fixtures
description: Use when capturing, saving, or committing real SchoolApp HTML/JSON as a test fixture — captured pages embed the student's CIN, CNE/Masar, email, photo, and name, which must be scrubbed before the file ever reaches git.
---

# Sanitizing SchoolApp Fixtures

## Overview

Extractor tests run against real captured HTML. Real SchoolApp pages contain the
student's **CIN, CNE/Masar, email, photo URL, and name (Latin + Arabic)**. Fixtures are
committed to git **forever** — a leak is permanent and public the moment it's pushed.

**Core rule:** scrub PII *before* the file is written into `tests/fixtures/`, never
"later". Committing one "harmless-looking" page anyway is the violation.

## Scrub checklist (every fixture, every time)

- [ ] Name: `nom`, `prenom`, and Arabic `nom_ar` / `prenom_ar`
- [ ] CIN (national ID)
- [ ] CNE / Masar code
- [ ] Email address
- [ ] Photo `src` / filename
- [ ] Student `code` / matricule
- [ ] Birth date
- [ ] Page header/footer (often repeats the name on every page)

Replace with **stable** placeholders so tests stay deterministic (`Doe`, `Jane`,
`student@example.test`, `AA000000`).

## Where PII concentrates

`/index` (Situation administrative + Données personnelles) is the richest — and any model
`raw` dict captured from it. `/student/notesannee` repeats the name in its header.
Document filenames embed the matricule. Grade/absence tables are mostly safe **except**
their surrounding chrome.

## Reusable scrubber (tune the patterns, then verify)

```python
# tests/fixtures/_sanitize.py — run on captured HTML before writing the fixture
import re

EXACT = {                                   # known real → fake (fill in per capture)
    "RealFirst": "Jane", "RealLast": "Doe",
    "الاسم": "فلان", "النسب": "الفلاني",
}
PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "student@example.test"),  # email
    (re.compile(r"\b[A-Z]{1,2}\d{5,7}\b"),    "AA000000"),             # CIN-like
    (re.compile(r"\b[A-Z]\d{8,10}\b"),        "X000000000"),           # CNE/Masar-like
    (re.compile(r'(src=")[^"]*photo[^"]*(")'), r"\1photo.png\2"),      # photo
]

def sanitize(html: str) -> str:
    for real, fake in EXACT.items():
        html = html.replace(real, fake)
    for pat, repl in PATTERNS:
        html = pat.sub(repl, html)
    return html
```

The regexes are a **starting point** — Moroccan CIN/CNE formats vary. Always finish with
the verify step; never trust the regex alone.

## Verify before commit

```bash
grep -RniE 'real-name|real-cin|@edu\.umi\.ac\.ma' tests/fixtures/   # must be empty
git diff --cached tests/fixtures/                                   # eyeball every fixture
```

## Red flags — STOP and scrub now

- "It's just a grades table." → Headers/footers carry the name.
- "I'll scrub it later / in a follow-up commit." → Git history keeps the original.
- "It's only on my machine for now." → One `git add -A` and it's staged.
- "The repo is private." → Forks, clones, and visibility changes outlive the intent.

| Rationalization | Reality |
|---|---|
| "This page has no PII" | `/index`, `notesannee`, and `raw` dicts almost always do. Check, don't assume. |
| "Tests need the real values" | Tests need *stable* values; placeholders work identically. |
| "I'll remember to sanitize the batch" | Scrub each file at capture time; batches leak the one you forget. |

**Source of truth:** design spec §12 (Testing → Fixtures).
