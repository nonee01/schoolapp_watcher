# schoolapp in Rust, Plan 1: foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Rust library and `schoolapp-rs fetch-all` that log into the portal, parse every per-student page and write a resource store byte-identical to the Python one.

**Architecture:** One crate `rust/schoolapp` (lib + bin) in a Cargo workspace. HTML parsing mirrors `schoolapp/extractors/` module by module; HTTP sits behind a trait so the client runs against a fixture-backed fake in tests and `ureq` live. Parity is proven against golden files that the Python implementation generates.

**Tech Stack:** Rust stable (edition 2024), ureq 2 (`cookies`), scraper, serde + serde_json, indexmap 2 (`serde`), chrono (`clock`), sha2 + hex, clap 4 (`derive`), anyhow; dev: tempfile, pretty_assertions.

**Spec:** `docs/superpowers/specs/2026-10-19-rust-port-design.md`

## Global Constraints

- Store JSON is serialized like `json.dumps(obj, ensure_ascii=False, indent=1)`: one-space indent, raw UTF-8, `": "` and `",\n"` separators, `[]`/`{}` for empty containers.
- Struct fields serialize in the Python dataclass field order with the Python names; every `raw` map and every dict built from a table keeps header order (`IndexMap`, never `HashMap`/`BTreeMap`).
- Base URL `https://schoolapp.ensam-umi.ac.ma`, User-Agent `schoolapp-cli/0.2`, default timeout 20 s.
- Paths: `/login`, `/index`, `/student/noteselem-encours`, `/student/noteselem`, `/student/notesmod-encours`, `/student/notesmod`, `/student/notessem`, `/student/notesannee`, `/student/notesdiplome`, `/student/absence/bilan`, `/student/absence/sanctions`, `/student/inscriptioncours`, `/notes-stat/elemevalsat`, `/student/documents/attestation-scolarite`.
- Error messages kept verbatim: `No table found on marks page`, `Login page changed: CSRF token missing`, `Login failed: verify email/password`, `Session expired and re-authentication failed`.
- Golden files are regenerated with `rust/tools/make_golden.py`, never edited by hand. Fixed clock in goldens and tests: `2026-01-01T00:00:00+00:00`.
- Cargo `target-dir` = `/home/notadil/.cache/cargo-target/schoolapp` (set in `rust/.cargo/config.toml`; `~/Projects` is synced by Syncthing).
- The Python package and its tests are not modified. Binary name: `schoolapp-rs`.
- Commits: short lowercase messages like the existing log, no attribution trailers.
- Academics-computed fields (`moy_sr_computed`, `decision_computed`, `moy_computed`, `coeff_assumed`) stay at their defaults in this plan; Plan 2 fills them. The golden generator disables `academics.annotate_student_data` to match.

## Review Focus

- **Session expiry mid-run:** the portal answers a later request with the login form. Expect one silent re-login and a retried request; a second login form raises `Session expired and re-authentication failed`. Test in Task 5.
- **One page failing:** HTTP 500 on `/student/notessem` must not stop `fetch_all`; the error lands under the Python key (`semester_results`) and every other resource is still saved. Tests in Tasks 5 and 6.
- **Accents and Arabic:** `Prénom`, `Filière` and Arabic names must reach the store as raw UTF-8, not `\u` escapes. Tests in Tasks 1 and 4.
- **Ragged and malformed tables:** rows shorter than the header get `""` for missing cells, all-empty rows are skipped, unclosed `<td>`/`<tr>` and `&nbsp;` parse like BeautifulSoup. Synthetic goldens in Task 3.
- **Bad password answered with a redirect:** the login POST is answered `302 Location: /login?error`. The live transport must follow it and the client must raise `Login failed: verify email/password`, not report success. Test in Task 7.

---

### Task 1: Workspace, golden generator, models, JSON writers

**Files:**
- Create: `rust/Cargo.toml` (workspace, member `schoolapp`), `rust/.cargo/config.toml`, `rust/.gitignore` (`target/`)
- Create: `rust/schoolapp/Cargo.toml`, `rust/schoolapp/src/lib.rs`, `rust/schoolapp/src/main.rs`, `rust/schoolapp/src/models.rs`, `rust/schoolapp/src/json.rs`
- Create: `rust/tools/make_golden.py`, generated `rust/schoolapp/tests/golden/**`
- Test: `rust/schoolapp/tests/models.rs`, `rust/schoolapp/tests/common/mod.rs`

**Interfaces:**
- Produces: `models::{StudentProfile, ElementGrade, ModuleGrade, SemesterResult, YearResult, DiplomaResult, Absence, Sanction, CourseEnrollment, MarkStatistics, Document, StudentData}`, all `Serialize + Default + Clone + Debug + PartialEq`, fields named and ordered exactly as in `schoolapp/models.py`; `raw`, `params` and `errors` are `IndexMap<String, String>`; `DiplomaResult.message: Option<String>`; `StudentData.profile: Option<StudentProfile>`, `StudentData.diploma: Option<DiplomaResult>`, `absence_summary: Vec<IndexMap<String, String>>`; `DiplomaResult` defaults `empty` to `true`.
- Produces: `json::to_store_json<T: Serialize>(&T) -> String` (indent 1) and `json::to_python_compact_json<T: Serialize>(&T) -> String` (`", "` and `": "` separators, no newlines, like `json.dumps` without indent).
- Produces (tests): `common::fixture(name) -> String` reads `../../tests/fixtures/<name>.html` relative to `CARGO_MANIFEST_DIR`; `common::golden(path) -> String` reads `tests/golden/<path>`; `common::NOW = "2026-01-01T00:00:00+00:00"`.

- [ ] **Step 1: Write `rust/tools/make_golden.py`**

Run from the repo root with `.venv/bin/python rust/tools/make_golden.py`; it imports `schoolapp` and `tests.test_fetch_all` from the repo, wipes and rewrites `rust/schoolapp/tests/golden/`, and serializes every value as `json.dumps(store._jsonable(v), ensure_ascii=False, indent=1)`. Outputs:
- `models/<Class>.json`: `Class()` for the twelve classes above.
- `extract/<fixture>__<parser>.json` for: `elements_encours` and `elements_history` × `parse_element_grades`; `modules_encours` and `modules_history` × `parse_module_grades`; `semesters` × `parse_semester_results`; `years` × `parse_year_results`; `diploma` × `parse_diploma`; `absences` × `parse_absences` and `parse_absence_summary`; `sanctions` × `parse_sanctions`; `courses` × `parse_courses`; `profile` × `parse_profile`; `stats` × `parse_mark_statistics(html, element="ELEM1", eval_kind="MoyElem", au="2025/2026", note="12.50")`; `elements_encours` × `extract_table` (as `{"headers": …, "rows": …}`).
- `extract/elements_encours__fingerprint.txt`: `fingerprint(*extract_table(html))`.
- `extract/documents.json`: `build_documents(parse_year_results(years), parse_semester_results(semesters))`.
- `synthetic/<case>.html` plus `synthetic/<case>__<parser>.json` for the cases in Tasks 3 and 4 (HTML strings defined in the script).
- Store trees, with `schoolapp.client.datetime` and `schoolapp.store.datetime` stubbed so `now()` returns the fixed clock and `schoolapp.academics.annotate_student_data` replaced by a no-op: `store_default/` = `SchoolAppClient(session=FakeSession())` after `login("e", "p")`, `fetch_all()`, `save_student_data(data, source="fetch_all", directory=…)`; `store_stats_nohistory/` = `fetch_all(include_history=False, include_stats=True)`; `store_fail_semesters/` = `FakeSession(fail_paths={"/student/notessem"})`, default `fetch_all()`.

- [ ] **Step 2: Generate and commit the goldens**

Run: `.venv/bin/python rust/tools/make_golden.py && find rust/schoolapp/tests/golden -type f | wc -l`
Expected: no traceback; every store tree holds `student/all.json` and the twelve `student/*.json` files.

- [ ] **Step 3: Write the failing tests in `tests/models.rs`**

```rust
#[test]
fn defaults_serialize_like_python_dataclasses() {
    assert_eq!(to_store_json(&ElementGrade::default()), golden("models/ElementGrade.json"));
    assert_eq!(to_store_json(&DiplomaResult::default()), golden("models/DiplomaResult.json"));
    assert_eq!(to_store_json(&StudentData::default()), golden("models/StudentData.json"));
    // … one assertion per class in Interfaces
}

#[test]
fn non_ascii_stays_raw_utf8() {
    let p = StudentProfile { prenom: "Yassine".into(), nom_ar: "العيدوس".into(), filiere: "Génie".into(), ..Default::default() };
    let out = to_store_json(&p);
    assert!(out.contains("\"nom_ar\": \"العيدوس\"") && out.contains("Génie") && !out.contains("\\u"));
}

#[test]
fn compact_json_matches_python_default_separators() {
    let v = serde_json::json!({"headers": ["a", "b"], "rows": [["x", "é"]]});
    assert_eq!(to_python_compact_json(&v), r#"{"headers": ["a", "b"], "rows": [["x", "é"]]}"#);
}
```

- [ ] **Step 4: Run them to make sure they fail**

Run: `cd rust && cargo test --test models`
Expected: compile errors, since `models` and `json` don't exist yet.

- [ ] **Step 5: Implement `models.rs` and `json.rs`**

`to_store_json` uses `serde_json::ser::PrettyFormatter::with_indent(b" ")`; `to_python_compact_json` is a small custom `serde_json::ser::Formatter` writing `", "` between items and `": "` after keys. `main.rs` is a clap skeleton with `--version` only.

- [ ] **Step 6: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test models`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add rust/
git commit -m "add the rust workspace, models and golden files"
```

---

### Task 2: Table helpers

**Files:**
- Create: `rust/schoolapp/src/extract/mod.rs`, `rust/schoolapp/src/extract/tables.rs`
- Test: `rust/schoolapp/tests/tables.rs`

**Interfaces:**
- Consumes: `json::to_python_compact_json`.
- Produces: `extract::tables::{normalize_cell(&str) -> String, text_of(scraper::ElementRef) -> String, extract_table(&str) -> anyhow::Result<(Vec<String>, Vec<Vec<String>>)>, table_by_headers(&str, &[&str]) -> Option<(Vec<String>, Vec<Vec<String>>)>, fingerprint(&[String], &[Vec<String>]) -> String}`.
- `text_of` reproduces BeautifulSoup `get_text(" ", strip=True)` followed by `normalize_cell`: descendant text nodes, each trimmed, empty ones dropped, joined with one space, whitespace runs collapsed (`&nbsp;` counts as whitespace).
- `extract_table` picks the table with the most `<tr>` (first one on ties), headers from every `<th>`, rows from every `<tr>` with `<td>`, skipping rows whose cells are all empty; no table gives `Err("No table found on marks page")`.
- `table_by_headers` returns the first table whose header set contains all `wanted` names.
- `fingerprint` = lowercase hex SHA-256 of `to_python_compact_json({"headers", "rows"})` with keys sorted.

- [ ] **Step 1: Write the failing tests**

```rust
#[test]
fn extract_table_and_fingerprint_match_python() {
    let html = fixture("elements_encours");
    let (headers, rows) = extract_table(&html).unwrap();
    let got = to_store_json(&serde_json::json!({"headers": headers, "rows": rows}));
    assert_eq!(got, golden("extract/elements_encours__extract_table.json"));
    assert_eq!(fingerprint(&headers, &rows), golden("extract/elements_encours__fingerprint.txt").trim());
}

#[test]
fn no_table_is_the_python_error() {
    assert_eq!(extract_table("<p>rien</p>").unwrap_err().to_string(), "No table found on marks page");
}

#[test]
fn normalize_cell_collapses_unicode_whitespace() {
    assert_eq!(normalize_cell("  12,5\u{a0}\n  /20 "), "12,5 /20");
}

#[test]
fn table_by_headers_skips_tables_missing_a_column() {
    let html = "<table><tr><th>A</th></tr></table><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>";
    assert_eq!(table_by_headers(html, &["A", "B"]).unwrap().1, vec![vec!["1".to_string(), "2".into()]]);
    assert!(table_by_headers(html, &["C"]).is_none());
}
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test tables`
Expected: compile errors (module missing).

- [ ] **Step 3: Implement `tables.rs` with the signatures above**

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test tables`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add rust/schoolapp
git commit -m "port the table helpers"
```

---

### Task 3: Grade, course and absence extractors

**Files:**
- Create: `rust/schoolapp/src/extract/grades.rs`, `courses.rs`, `absences.rs`
- Modify: `rust/tools/make_golden.py` only if a synthetic case below is missing
- Test: `rust/schoolapp/tests/extract_tables.rs`

**Interfaces:**
- Consumes: `tables::{table_by_headers, text_of, normalize_cell}`, the models.
- Produces: `extract::{parse_element_grades(&str) -> Vec<ElementGrade>, parse_module_grades(&str) -> Vec<ModuleGrade>, parse_courses(&str) -> Vec<CourseEnrollment>, parse_absences(&str) -> Vec<Absence>, parse_absence_summary(&str) -> Vec<IndexMap<String, String>>, parse_sanctions(&str) -> Vec<Sanction>}`.
- Header signatures: elements `{CodeElem, AU, Moy}`, modules `{CodeMod, AU, Moy}`, courses `{CodeElem, Statut, Num}`, absences `{Element, Date, Seance}`, summary `{CodeElem, Non Justifiée, Justifiée}`.
- Field mapping as in the Python extractors: `decision` = `Dec`, or `Decision` when `Dec` is missing or empty; courses `sous_groupe` from `S.Groupe`; absence `date` = text before the first space; `justified` when `Justif` lowercased is `true`, `1`, `oui` or `yes`; rows without the key column (`CodeElem`, `CodeMod`, `Element`, first summary cell) are skipped; sanctions = the first table with at least one `<tr>` holding two or more `<td>` and a non-empty first cell, `raw = {"key", "value"}`.
- Synthetic cases in the generator: `ragged_rows` (headers `CodeElem AU CC EX TP Moy`, one full row, one 3-cell row, one all-empty row) and `malformed_table` (unclosed `<td>` and `<tr>`, `<b>12</b>.<i>5</i>` inside a cell, `&nbsp;`), both × `parse_element_grades`.

- [ ] **Step 1: Write the failing tests**

```rust
fn check<T: serde::Serialize>(got: &T, golden_path: &str) {
    pretty_assertions::assert_eq!(to_store_json(got), golden(golden_path));
}

#[test] fn element_grades() { check(&parse_element_grades(&fixture("elements_encours")), "extract/elements_encours__parse_element_grades.json");
                             check(&parse_element_grades(&fixture("elements_history")), "extract/elements_history__parse_element_grades.json"); }
#[test] fn module_grades() { /* modules_encours, modules_history */ }
#[test] fn courses() { /* courses */ }
#[test] fn absences_summary_sanctions() { /* absences ×2, sanctions */ }
#[test] fn ragged_and_malformed_tables() {
    check(&parse_element_grades(&golden("synthetic/ragged_rows.html")), "synthetic/ragged_rows__parse_element_grades.json");
    check(&parse_element_grades(&golden("synthetic/malformed_table.html")), "synthetic/malformed_table__parse_element_grades.json");
}
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test extract_tables`
Expected: compile errors (functions missing).

- [ ] **Step 3: Implement the three modules with the signatures above**

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test extract_tables`
Expected: 5 passed. If a golden differs, find the BeautifulSoup behavior that explains it (the generator is the reference) and match it in `tables::text_of` or the extractor; never edit a golden.

- [ ] **Step 5: Commit**

```bash
git add rust/
git commit -m "port the grade, course and absence extractors"
```

---

### Task 4: Result, profile, statistics and document extractors

**Files:**
- Create: `rust/schoolapp/src/extract/results.rs`, `profile.rs`, `stats.rs`, `documents.rs`
- Test: `rust/schoolapp/tests/extract_pages.rs`

**Interfaces:**
- Consumes: `tables::{text_of, normalize_cell}`, the models.
- Produces: `extract::{parse_semester_results(&str) -> Vec<SemesterResult>, parse_year_results(&str) -> Vec<YearResult>, parse_diploma(&str) -> DiplomaResult, parse_profile(&str) -> StudentProfile, parse_mark_statistics(html: &str, element: &str, eval_kind: &str, au: &str, note: &str) -> Option<MarkStatistics>, build_documents(&[YearResult], &[SemesterResult]) -> Vec<Document>}`.
- Semesters: signature `{Semestre, Moy SEM}`, rows need `Semestre`, `releve_url` = the row's first `<a href>` or `""`, `decision` from `Decesion` (site typo) then `Decision`. Years: signature `{Niveau, AU, Moy Année}`, rows need `Niveau`, `filiere` from `Filière`, `moy_annee` from `Moy Année`, same link and typo rules.
- Diploma: the table with the most `<tr>`; header rows keyed by header, else by index `"0"`, `"1"`…; non-empty rows give `empty=false, message=None, raw={"headers": headers joined with " | "}`; otherwise `empty=true`, `message` = the first text node containing `Vous n'avez pas de note de diplome`, normalized, or `None`, `rows=[]`, `raw={}`.
- Profile: every `<tr>` whose descendant `th`/`td` cells number exactly two with a `th` first; a repeated label with a different value becomes `Label (2)`, `Label (3)`…; `photo_url` = the first `<img src>` not containing `logo` (case-insensitive); typed fields from the labels `Code`, `CNE/Masar`, `Nom`, `Prénom`, `Nom Arabe`, `Prénom Arabe`, `CIN`, `Sexe`, `Date Naissance`, `Email`, `Filière`, `Niveau`, `Statut`, `Section`, `Groupe`, `Sous Groupe`.
- Stats: scope = `div.stat` or the whole page; title = first `<p>`; rows = th/td texts of each `<tr>` of the first table, skipping all-empty rows; `None` when there are no rows and no title; `raw = {"title": title}`.
- Documents: the attestation first (`kind "attestation-scolarite"`, `url "/student/documents/attestation-scolarite"`, `filename "attestation-scolarite.pdf"`), then `releve-annee` per year with a link (`params {"niveau"}`, `releve-<niveau>-<au>.pdf`), then `releve-semestre` per semester with a link (`params {"niveau", "semestre"}`, `releve-<niveau>-<semestre>-<au>.pdf`), all `application/pdf`.
- Synthetic cases in the generator: `duplicate_labels` (label `Lieu_Naissance` twice with different values and `Email` twice with the same value, a logo `<img>` before the photo) and `arabic_profile` (Arabic `Nom Arabe`/`Prénom Arabe`, accented `Filière`), both × `parse_profile`; `empty_diploma` (only the marker paragraph) × `parse_diploma`.

- [ ] **Step 1: Write the failing tests**

Same `check` helper as Task 3, one test per parser over the fixtures listed in Task 1 Step 1, plus:

```rust
#[test] fn profile_edge_cases() {
    check(&parse_profile(&golden("synthetic/duplicate_labels.html")), "synthetic/duplicate_labels__parse_profile.json");
    check(&parse_profile(&golden("synthetic/arabic_profile.html")), "synthetic/arabic_profile__parse_profile.json");
}
#[test] fn empty_diploma_page() { check(&parse_diploma(&golden("synthetic/empty_diploma.html")), "synthetic/empty_diploma__parse_diploma.json"); }
#[test] fn documents_from_results() {
    let years = parse_year_results(&fixture("years"));
    let sems = parse_semester_results(&fixture("semesters"));
    check(&build_documents(&years, &sems), "extract/documents.json");
}
#[test] fn stats_popup() {
    check(&parse_mark_statistics(&fixture("stats"), "ELEM1", "MoyElem", "2025/2026", "12.50"), "extract/stats__parse_mark_statistics.json");
    assert!(parse_mark_statistics("<html></html>", "", "", "", "").is_none());
}
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test extract_pages`
Expected: compile errors.

- [ ] **Step 3: Implement the four modules with the signatures above**

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test extract_pages`
Expected: all pass, with the same rule as Task 3 for any golden difference.

- [ ] **Step 5: Commit**

```bash
git add rust/
git commit -m "port the result, profile, stats and document extractors"
```

---

### Task 5: Portal client over an HTTP trait

**Files:**
- Create: `rust/schoolapp/src/http.rs`, `rust/schoolapp/src/client.rs`
- Test: `rust/schoolapp/tests/client.rs`, `rust/schoolapp/tests/common/fake.rs`

**Interfaces:**
- Consumes: every extractor from Tasks 3 and 4.
- Produces: `http::Http` trait: `fn get(&mut self, path: &str, query: &[(&str, &str)]) -> Result<String, HttpError>` and `fn post_form(&mut self, path: &str, form: &[(&str, &str)]) -> Result<String, HttpError>`; `HttpError::{Status(u16), Transport(String)}` with `Display` `status <code>` and the transport message.
- Produces: `client::{extract_csrf(&str) -> Option<String>, looks_like_login_page(&str) -> bool, Client<H: Http>}` with `Client::new(http: H, now: fn() -> String)`, `set_credentials(&mut self, email, password)`, `login(&mut self, email, password) -> anyhow::Result<()>`, `get_page(&mut self, path) -> anyhow::Result<String>`, `pub last_pages: IndexMap<String, String>`, `fetch_all(&mut self, include_history: bool, include_stats: bool) -> StudentData`, `http_mut(&mut self) -> &mut H`.
- Login: GET `/login`, CSRF from `input[name="_csrf"]` (missing → `Login page changed: CSRF token missing`), POST `email`, `password`, `_csrf`; a login form in the answer → `Login failed: verify email/password`. A page is the login form when it has `form[action="/login"]` and `input[name="password"]`.
- Requests: any GET answered with the login form triggers one login and one retry; a second login form, or no stored credentials, → `Session expired and re-authentication failed`. Successful pages are stored in `last_pages` by path.
- `fetch_all`: `fetched_at = now()`; each resource isolated, an error stored as `errors[<key>] = err.to_string()` in this order: `profile`, `element_grades`, `element_grades_history`, `module_grades`, `module_grades_history`, `semester_results`, `year_results`, `diploma`, `absences` (one GET feeding both `absences` and `absence_summary`), `sanctions`, `courses`, `documents`, then `stats` when asked. History rows are appended only when their `(code, au)` is not already in the current rows. Stats: for each current element grade, for `("MoyElem", moy)` then `("NoteRAT", rat)` when the note is not empty and not `--`, GET `/notes-stat/elemevalsat` with `eval`, `codeelem` (uppercased), `au`, `note`, parsed with those values.
- Test fake (`common/fake.rs`): `FakeHttp` mirrors `tests/test_fetch_all.py::FakeSession`: same path → fixture map, the same `LOGIN_FORM` until a POST to `/login`, `fail_paths` answered `Status(500)`, `"<html><body>rien</body></html>"` for unknown paths, a `log: Vec<String>` with one entry per request (`"POST <path>"`, `"GET <path>"`, or `"GET <path>?k=v&k=v"` with the query pairs in the order given), and an `expire_after: Option<usize>` that serves the login form once after that many requests.

- [ ] **Step 1: Write the failing tests**

```rust
#[test]
fn login_then_fetch_all_reads_every_resource() {
    let mut c = Client::new(FakeHttp::default(), || NOW.into());
    c.login("e", "p").unwrap();
    let data = c.fetch_all(true, false);
    assert!(data.errors.is_empty());
    assert_eq!(data.fetched_at, NOW);
    assert!(data.profile.is_some() && !data.element_grades.is_empty());
}

#[test]
fn a_failing_page_is_recorded_and_the_rest_still_fetched() {
    let mut c = Client::new(FakeHttp { fail_paths: vec!["/student/notessem".into()], ..Default::default() }, || NOW.into());
    c.login("e", "p").unwrap();
    let data = c.fetch_all(true, false);
    assert_eq!(data.errors.get("semester_results").map(String::as_str), Some("status 500"));
    assert!(data.semester_results.is_empty() && !data.year_results.is_empty());
}

#[test]
fn session_expiry_triggers_one_relogin() {
    let mut c = Client::new(FakeHttp { expire_after: Some(3), ..Default::default() }, || NOW.into());
    c.login("e", "p").unwrap();
    assert!(c.fetch_all(true, false).errors.is_empty());
    assert_eq!(c.http_mut().log.iter().filter(|p| *p == "POST /login").count(), 2);
}

#[test]
fn wrong_password_and_missing_credentials() {
    let mut c = Client::new(FakeHttp { reject_login: true, ..Default::default() }, || NOW.into());
    assert_eq!(c.login("e", "bad").unwrap_err().to_string(), "Login failed: verify email/password");
    let mut anon = Client::new(FakeHttp::default(), || NOW.into());
    assert_eq!(anon.get_page("/index").unwrap_err().to_string(), "Session expired and re-authentication failed");
}

#[test]
fn stats_follow_each_graded_element() {
    let mut c = Client::new(FakeHttp::default(), || NOW.into());
    c.login("e", "p").unwrap();
    let data = c.fetch_all(false, true);
    assert!(!data.stats.is_empty());
    assert!(c.http_mut().log.iter().any(|p| p.starts_with("GET /notes-stat/elemevalsat?eval=MoyElem&codeelem=")));
}
```

(`FakeHttp` also needs `reject_login: bool`, which keeps serving the login form after the POST.)

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test client`
Expected: compile errors.

- [ ] **Step 3: Implement `http.rs` and `client.rs` with the signatures above**

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test client`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add rust/schoolapp
git commit -m "port the portal client"
```

---

### Task 6: Resource store

**Files:**
- Create: `rust/schoolapp/src/store.rs`
- Test: `rust/schoolapp/tests/store.rs`

**Interfaces:**
- Consumes: `json::to_store_json`, `Client`, `FakeHttp`.
- Produces: `store::{state_dir() -> PathBuf, RESOURCE_FILES: [(&str, &str); 12], save_resource<T: Serialize>(name: &str, data: &T, source: &str, dir: Option<&Path>, now: &str) -> std::io::Result<PathBuf>, load_resource(name: &str, dir: Option<&Path>) -> Option<serde_json::Value>, save_student_data(data: &StudentData, source: &str, dir: Option<&Path>, now: &str) -> std::io::Result<()>}`.
- `state_dir` = trimmed non-empty `$XDG_STATE_HOME`, else `~/.local/state`, joined with `schoolapp`. `save_resource` writes `<dir>/<name>.json` (creating parents) through `<name>.json.tmp` and a rename, envelope fields in the order `fetched_at`, `source`, `data`. `load_resource` returns `None` when the file is missing, not JSON, or has no `data`. `save_student_data` writes `student/all` and then the twelve names from `store.RESOURCE_FILES`, in that order and with the same names.

- [ ] **Step 1: Write the failing tests**

```rust
fn assert_tree(case: &str, include_history: bool, include_stats: bool, fail: &[&str]) {
    let tmp = tempfile::tempdir().unwrap();
    let mut c = Client::new(FakeHttp { fail_paths: fail.iter().map(|s| s.to_string()).collect(), ..Default::default() }, || NOW.into());
    c.login("e", "p").unwrap();
    save_student_data(&c.fetch_all(include_history, include_stats), "fetch_all", Some(tmp.path()), NOW).unwrap();
    for name in std::iter::once("student/all").chain(RESOURCE_FILES.iter().map(|(_, n)| *n)) {
        let got = std::fs::read_to_string(tmp.path().join(format!("{name}.json"))).unwrap();
        pretty_assertions::assert_eq!(got, golden(&format!("{case}/{name}.json")), "{case}/{name}");
    }
}

#[test] fn default_tree_matches_python() { assert_tree("store_default", true, false, &[]); }
#[test] fn stats_without_history_matches_python() { assert_tree("store_stats_nohistory", false, true, &[]); }
#[test] fn failed_page_tree_matches_python() { assert_tree("store_fail_semesters", true, false, &["/student/notessem"]); }

#[test]
fn load_resource_rejects_missing_and_corrupt_files() {
    let tmp = tempfile::tempdir().unwrap();
    assert!(load_resource("student/profile", Some(tmp.path())).is_none());
    std::fs::create_dir_all(tmp.path().join("student")).unwrap();
    std::fs::write(tmp.path().join("student/profile.json"), "{oops").unwrap();
    assert!(load_resource("student/profile", Some(tmp.path())).is_none());
    save_resource("student/profile", &StudentProfile::default(), "x", Some(tmp.path()), NOW).unwrap();
    assert_eq!(load_resource("student/profile", Some(tmp.path())).unwrap()["source"], "x");
    assert!(!tmp.path().join("student/profile.json.tmp").exists());
}
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test store`
Expected: compile errors.

- [ ] **Step 3: Implement `store.rs` with the signatures above**

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd rust && cargo test --test store`
Expected: 4 passed, which means the Rust store is byte-identical to the Python one for all three scenarios.

- [ ] **Step 5: Commit**

```bash
git add rust/schoolapp
git commit -m "port the resource store"
```

---

### Task 7: `schoolapp-rs fetch-all` with the live transport

**Files:**
- Create: `rust/schoolapp/src/ureq_http.rs`
- Modify: `rust/schoolapp/src/main.rs`
- Test: `rust/schoolapp/tests/ureq_http.rs`, `rust/schoolapp/tests/cli.rs`

**Interfaces:**
- Consumes: `Client`, `store::{save_student_data, state_dir}`.
- Produces: `ureq_http::UreqHttp::new(base_url: &str, timeout: Duration) -> UreqHttp` implementing `Http`: one agent with a cookie store, User-Agent `schoolapp-cli/0.2`, HTTP ≥ 400 → `HttpError::Status`, query and form values URL-encoded; `post_form` follows a 301/302/303 answer with a GET to its `Location`, like `requests` does.
- Produces: `schoolapp-rs fetch-all [--email E] [--password P] [--timeout 20] [--history/--no-history] [--stats] [--save/--no-save] [--json]`. Credentials: flags, else `SCHOOLAPP_EMAIL`/`SCHOOLAPP_PASSWORD`; missing → message `Missing credentials: provide --email/--password or SCHOOLAPP_EMAIL/SCHOOLAPP_PASSWORD` on stderr, exit 2. Login failure → `error: <message>` on stderr, exit 1. Saves with `source "fetch_all"` unless `--no-save`. Human output: one line per resource (`profile ok`, `diploma empty`, `element_grades 12`…), then `Saved to <dir>` and one `<key>: <error>` line per error on stderr. `--json`: `{"profile": bool, "diploma": null|"empty"|"ok", "counts": {…ten names in the Python order…}, "errors": {…}, "saved_to": path|null}`.

- [ ] **Step 1: Write the failing tests**

`tests/ureq_http.rs` runs a `std::net::TcpListener` on 127.0.0.1:0 in a thread that answers `GET /login` with the login form (CSRF `tok`), `POST /login` with `302 Location: /login?error`, and `GET /login?error` with the login form again:

```rust
#[test]
fn bad_password_redirect_is_reported_as_failed_login() {
    let base = serve_portal_stub();
    let mut c = Client::new(UreqHttp::new(&base, Duration::from_secs(5)), || NOW.into());
    assert_eq!(c.login("e", "bad").unwrap_err().to_string(), "Login failed: verify email/password");
}

#[test]
fn http_errors_become_status_errors() {
    let base = serve_status(503);
    let mut h = UreqHttp::new(&base, Duration::from_secs(5));
    assert_eq!(h.get("/student/notessem", &[]).unwrap_err().to_string(), "status 503");
}
```

`tests/cli.rs` (runs the built binary through `env!("CARGO_BIN_EXE_schoolapp-rs")` with `SCHOOLAPP_EMAIL`/`SCHOOLAPP_PASSWORD` removed from its environment):

```rust
#[test]
fn missing_credentials_is_a_usage_error() {
    let out = Command::new(env!("CARGO_BIN_EXE_schoolapp-rs")).arg("fetch-all")
        .env_remove("SCHOOLAPP_EMAIL").env_remove("SCHOOLAPP_PASSWORD").output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("Missing credentials"));
}
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `cd rust && cargo test --test ureq_http --test cli`
Expected: compile errors.

- [ ] **Step 3: Implement `ureq_http.rs` and the `fetch-all` subcommand with the signatures above**

- [ ] **Step 4: Run the whole suite**

Run: `cd rust && cargo test`
Expected: every test from Tasks 1 to 7 passes.

- [ ] **Step 5: Live check against the Python store**

```bash
set -a; . ./.env; set +a
A=$(mktemp -d); B=$(mktemp -d)
XDG_STATE_HOME=$A .venv/bin/schoolapp fetch-all >/dev/null
XDG_STATE_HOME=$B /home/notadil/.cache/cargo-target/schoolapp/debug/schoolapp-rs fetch-all
diff -r <(cd $A/schoolapp && grep -rv '"fetched_at"' student) <(cd $B/schoolapp && grep -rv '"fetched_at"' student)
```

Expected: only the academics-computed fields (`moy_sr_computed`, `decision_computed`, `moy_computed`, `coeff_assumed`) differ, since Plan 2 adds those. Any other difference is a bug to fix before committing.

- [ ] **Step 6: Commit**

```bash
git add rust/schoolapp
git commit -m "add schoolapp-rs fetch-all with the live transport"
```
