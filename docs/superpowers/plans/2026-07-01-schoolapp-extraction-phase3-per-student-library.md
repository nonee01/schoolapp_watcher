# Phase 3 (library half): per-student extractors + client surface

- **Date:** 2026-07-01
- **Spec:** `docs/superpowers/specs/2026-06-28-schoolapp-comprehensive-extraction-design.md` §4–6, §10, §12, §13.3
- **Branch:** `android-native-app` (on top of Phase 1, commit `7698868`)

## Scope & ordering note

Spec Phase 2 ("wire existing consumers") requires editing `watcher.py`/`api.py`, which carry
~1,000 uncommitted lines of in-progress work — any commit would entangle it. Phases are
independently shippable, so this plan delivers **Phase 3's library half first**: pure extractors
for every per-student resource, the matching `SchoolAppClient` methods, and `fetch_all`.

**Deferred to a "wiring" plan once the tree is clean:** watcher/API rewire (Phase 2), the new
Flask endpoints (`/api/profile` … `/api/all`), and CLI `profile`/`fetch-all` (spec §8). Nothing
here touches a dirty file.

## Task 1 — Sanitized fixtures (spec §12)

`tests/fixtures/_capture.py` — a dev-only script, committed for future re-captures:

1. Read `SCHOOLAPP_EMAIL`/`SCHOOLAPP_PASSWORD` from `.env` (tiny KEY=VALUE parser, no new dep).
2. Log in **from code** via `schoolapp.client.SchoolAppClient` (never a browser form) and GET:
   `/index`, `/student/noteselem-encours`, `/student/noteselem`, `/student/notesmod-encours`,
   `/student/notesmod`, `/student/notessem`, `/student/notesannee`, `/student/notesdiplome`,
   `/student/absence/bilan`, `/student/absence/sanctions`, `/student/inscriptioncours`,
   plus one `/notes-stat/elemevalsat` popup derived from the first element row with a real note.
3. **Sanitize in memory before anything touches disk** (per the `sanitizing-schoolapp-fixtures`
   skill): learn the real PII values from `/index`'s key/value pairs (name Latin+Arabic, CIN,
   CNE/Masar, matricule, email, birth date), globally replace them (len ≥ 4 guard) with stable
   placeholders (`Doe`, `Jane`, `AA000000`, `X000000000`, `student@example.test`, …), then apply
   the regex pass (email / CIN-like / CNE-like / photo `src`).
4. Self-verify: assert no real value survives in any output file; print only labels/sizes, never
   values. Raw HTML is never written to disk.
5. Manual gate before commit: `grep -RniE '<known-email-locals>|@gmail|@edu' tests/fixtures/`
   must be empty.

Fixtures land in `tests/fixtures/*.html` (12 files; diploma fixture is the real empty state).

## Task 2 — Extractors (pure, one module per resource group)

All return models from `schoolapp.models`; no I/O; tolerant of missing tables (return empty —
logging/carry-forward stays in consumers, spec §10). Row `raw` dict = header→cell.

- `extractors/grades.py` — `parse_element_grades(html)` (signature `{CodeElem, Moy}`, cols
  `CodeElem AU CC EX TP MoySO RAT MoySR Moy Decision`; serves both `-encours` and history) and
  `parse_module_grades(html)` (signature `{CodeMod, Moy}`, `Dec` **or** `Decision`).
- `extractors/results.py` — `parse_semester_results(html)` (`{Semestre, Moy SEM}`, `Decesion`
  typo fallback), `parse_year_results(html)` (`Niveau Filière AU Statut "Moy Année" PJ Decesion
  Classement`), `parse_diploma(html)` (the "Vous n'avez pas de note de diplome" empty state is
  `DiplomaResult(empty=True, message=…)`, not an error). Year/semester parsers walk the DOM (not
  just text) to capture `releve_url` from the row's `<a href>`.
- `extractors/absences.py` — `parse_absences(html)` (`{Element, Date, Seance}`; date truncated
  at first space; `justified` from `Justif` cell) and `parse_sanctions(html)` (first 2-col
  key/value table).
- `extractors/courses.py` — `parse_courses(html)` (`CodeElem Statut Section Groupe S.Groupe Num`).
- `extractors/profile.py` — `parse_profile(html)` over `/index`'s two key/value blocks; full
  pair set preserved in `StudentProfile.raw`. Exact DOM confirmed from the fixture.
- `extractors/stats.py` — `parse_mark_statistics(popup_html, element, eval_kind, au, note)`
  (popup `div.stat`: `<p>` title + table, as in `fetch_element_details`).
- `extractors/documents.py` — `build_documents(year_results) -> list[Document]`: the fixed
  attestation descriptor + one `releve` per `YearResult.releve_url`.
- `extractors/_tables.py` — add `REGISTRY: dict[str, tuple[frozenset[str], Callable]]` mapping
  each table-shaped resource to (header signature, parser) for the future generic watcher diff.

## Task 3 — Client resource surface (spec §5)

Path constants + one method per resource on `SchoolAppClient`: `profile()`,
`element_grades(history=False)`, `module_grades(history=False)`, `semester_results()`,
`year_results()`, `diploma()`, `absences()`, `sanctions()`, `courses()`,
`mark_statistics(code, eval_kind="all")` (elements page → popup GETs, mirroring
`fetch_element_details`), `documents()`, and
`fetch_all(include_history=True, include_stats=False) -> StudentData` — each resource isolated
in try/except, failures collected in `StudentData.errors`, `fetched_at` = UTC ISO-8601.
`download()` stays out (spec Phase 5).

## Task 4 — Tests + verification + commit

- Per-extractor tests against the fixtures (incl. `Decesion` typo, `releve_url`, empty diploma,
  no-table → empty result).
- `fetch_all` test over a fake session serving fixture HTML per path; error-isolation test
  (one route raises → other resources still populated, error recorded).
- `python -m pytest -q` green (existing 18 + new); commit fixtures + code + tests only
  (never the dirty files).
