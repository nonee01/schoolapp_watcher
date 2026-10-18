# schoolapp in Rust: design

## Why

The watcher and the API run all day on the asus: about 75 MB of resident Python
plus an interpreter start for every CLI call. The same work in Rust fits in a few
MB and starts instantly. Decision (2026-10-19): schoolapp moves from Python to Rust.

## What must not change

The Python API, the plasmoid and the Android app keep reading the files the
watcher writes, so until each piece is replaced the Rust code writes exactly what
the Python code writes:

- **Resource store** under `$XDG_STATE_HOME/schoolapp/` (default
  `~/.local/state/schoolapp/`): one envelope per resource,
  `{"fetched_at", "source", "data"}`, written atomically through a `.tmp` file,
  serialized like `json.dumps(obj, ensure_ascii=False, indent=1)`: one-space
  indent, raw UTF-8, keys in the Python dataclass field order, `raw` maps in
  table-header order. Names: `student/all` plus the twelve in
  `store.RESOURCE_FILES`.
- **Legacy files**: `<sem>_snapshot.json` and `changes.jsonl` keep their format.
- **Notifications**: the email (subject, text body, HTML) and the Telegram
  message are byte-identical to the Python output for the same old and new state.
- **Configuration**: the same `.env` variables (`SCHOOLAPP_EMAIL`,
  `SCHOOLAPP_PASSWORD`, SMTP and Telegram settings) and the same portal
  behaviour: base URL `https://schoolapp.ensam-umi.ac.ma`, User-Agent
  `schoolapp-cli/0.2`, CSRF login, one re-login when a page comes back as the
  login form.

## How parity is proven

Golden files. A Python script in `rust/tools/` runs the current implementation on
the 17 sanitized portal pages in `tests/fixtures/` (and on synthetic cases for
edge inputs) and writes the expected output under `rust/schoolapp/tests/golden/`.
The Rust tests compare byte for byte. When the Python behaviour is the reference,
the golden files are regenerated from it, never edited by hand.

## Shape

- A Cargo workspace in `rust/` inside this repo, one crate `schoolapp`
  (library + binary). The binary is `schoolapp-rs` until the Python CLI is
  retired, so both can be installed side by side.
- Blocking I/O, no async runtime: `ureq` 2 (cookies) for HTTP, `scraper` for
  HTML, `serde`/`serde_json` with `indexmap` for order-preserving maps,
  `chrono`, `sha2`, `clap`, `anyhow`. Email through `lettre`, the API on
  `tiny_http` (later plans).
- HTTP sits behind a small trait, so the client is tested against a
  fixture-backed fake exactly like `tests/test_fetch_all.py::FakeSession`.
- Cargo's `target-dir` is `/home/notadil/.cache/cargo-target/schoolapp`:
  `~/Projects` is synced to the hp by Syncthing, and build output must not be.

## Phases (one plan each, each one deployable or verifiable on its own)

1. Foundation: models, HTML extractors, portal client, resource store,
   `schoolapp-rs fetch-all`. Verified by golden parity and one live run diffed
   against the Python store.
2. Watcher: academics (règlement-computed fields and rattrapage), snapshot and
   diffs, email and Telegram, history, `schoolapp-rs s5 watch` with the
   scheduled mode. Replaces `schoolapp-watcher.service`.
3. API: the routes in `schoolapp/api.py` on `tiny_http`. Replaces
   `schoolapp-api.service`.
4. The remaining CLI commands, then the Python package is removed.
