# Phase 2 + 6 + API wiring — watcher/API on the library

Spec: `docs/superpowers/specs/2026-06-28-schoolapp-comprehensive-extraction-design.md`
§8.1/§8.3/§9/§13. Unblocked by the user's watcher/API overhaul landing as `dbd4ee8`.

**Invariants:** legacy `s4_snapshot.json` (headers/rows/extras) and `changes.jsonl`
formats byte-stable; frozen API endpoints unchanged (additive only); notify semantics
identical in Task 1 (no new alerts until Task 2); suite green after every task.

## Task 1 — Phase 2: watcher fetches through the library, persists via store

- `client.py` (additive): `set_credentials(email, password)` (lazy re-auth, no login
  POST); `last_pages: dict[path, html]` recorded by `_request` on success so cache-layer
  consumers can reuse raw HTML (bounded: one entry per distinct path).
- `store.py`: move `RESOURCE_FILES` here; add `save_student_data(data, *, source,
  directory=None)` (student/all + per-resource envelopes). `cli.py` reuses both.
- `watcher.py`:
  - Delete duplicated helpers; import-alias instead: `extract_csrf`,
    `looks_like_login_page` (client), `extract_table`, `fingerprint`, `normalize_cell`,
    `table_by_headers` (extractors._tables). Delete `_login`, `_fetch_extras`,
    `_parse_absence_log`, `_parse_sanctions`, `_parse_modules_encours`,
    `_parse_semester_results`.
  - `check_once`: `client.fetch_all()` once → legacy snapshot from
    `_extract_table(client.last_pages[ELEMENTS_PATH])`; extras blobs rebuilt from typed
    models via `_absences_blob/_sanctions_blob/_modules_blob/_semesters_blob` adapters
    (byte-parity pinned by tests); resource in `data.errors` → blob `None` (carry-forward
    unchanged); `element_grades` error → raise (watch_loop backoff preserved); persist
    `store.save_student_data(data, source="watcher")` after diffing.
  - `run_health_check`: same step-by-step flow via imported helpers (keeps HTTP codes).
  - `fetch_element_details`: thin wrapper over `SchoolAppClient.login` +
    `element_grades` + `mark_statistics`, returning the exact legacy dict
    (`element_code`, `data`, `stats[].{eval,title,rows}`; `None` when nothing).
- Tests: adapters vs inline legacy algorithm on the fixtures (parity); `check_once`
  end-to-end on FakeSession (first run rc=1 + snapshot + store envelopes; unchanged
  second run rc=0; extras carry-forward on failure).

## Task 2 — Phase 6: digest covers every per-student resource + catalog summary

- Generic differ in `watcher.py`: keyed added/removed/changed lines per resource —
  profile (field diff), years (`niveau|au`), diploma (rows), courses (`code_elem|num`),
  element/module history rows (key `code|au`, filtered to rows without `Dec` so current
  cards aren't duplicated). Old state = previous store envelopes (loaded pre-save); no
  envelope → no baseline → silent.
- One `_simple_card` + one Telegram section per changed resource, bundled into the
  existing single email/Telegram per cycle; one typed `changes.jsonl` entry each.
- `cli.py catalog crawl`: added/removed/changed summary vs the previous store contents,
  printed once per crawl + one `changes.jsonl` entry (spec §9 catalog exception).
- Tests: seeded envelope → card/section/history line; no baseline → silent; crawl
  summary counts.

## Task 3 — API: new endpoints, all additive, all store-served

- `/api/profile`, `/api/years`, `/api/courses`, `/api/all`, `/api/stats/<code>`
  (filter cached `student/stats`), `/api/grades/elements` + `/api/grades/modules`
  (`?history=1` → merged list; default filters to latest AU), `/api/documents`
  (listing), `/api/documents/<kind>` (cached PDF via `store.document_path`; 404 when
  absent), `/api/export?format=json|zip`, `/api/catalog?niveau=&filiere=&semestre=`,
  `/api/filieres`.
- `/api/status` gains `resources: store.freshness(...)` (additive key).
- `store.py`: `document_path(kind)` / `save_document(kind, content)`; CLI `export
  --with-documents` also drops PDFs there.
- Tests: Flask test_client on seeded store; frozen-endpoint regression
  (`/api/grades/S4` shape from a seeded legacy snapshot); 404 paths; auth.
