# SchoolApp CLI — presentation layer + full API-parity command surface

Status: approved 2026-07-02. Builds on the library/store/API wiring (commits
`db08cb4`..`72a5e68`). Goal: the CLI becomes a coherent, good-looking front-end
that surfaces *every* form of information the API exposes, with clean
machine-readable output and first-class PDF downloads.

## 1. Principles

- **stdout = data, stderr = chrome.** Command *results* (tables, JSON) go to a
  stdout console; banner, logs, spinners, progress go to a stderr console. So
  `schoolapp show grades --json > f.json` is always clean JSON with no flag
  threading. `--quiet/-q` silences the stderr chrome.
- **Fetch vs show split.** `fetch-all`/`profile`/`catalog crawl`/`documents
  download` do network→store writes; `show *` is pure store→display and never
  hits the network. No command silently fetches.
- **One presentation layer.** All rendering + colors defined once in
  `render.py`; commands never hand-build ad-hoc tables/colors again.

## 2. `schoolapp/render.py` (new)

- `THEME = rich.Theme({...})`: named styles `ok` (VORD/validated, green),
  `fail` (NV, red), `rat` (amber), `info` cyan, `warning` yellow, `error` red,
  `muted` dim, `header` bold magenta, `accent` cyan.
- `console` (stdout) and `err_console` (stderr, `stderr=True`), both themed.
  `utils.console` is re-pointed at this themed console so existing
  `from .utils import console` consumers get theming for free.
- Helpers:
  - `status_badge(value) -> Text`: V*/validated→`ok ✓`, NV→`fail ✗`,
    RAT→`rat`, `--`/empty→`muted`.
  - `data_table(title, columns, rows, *, caption=None) -> Table`.
  - `error_panel(message, *, hint=None) -> Panel`.
  - Per-resource renderers returning a renderable (Table/Group):
    `profile_view`, `element_grades_table`, `module_grades_table`,
    `semesters_table`, `years_table`, `absences_view` (log + summary +
    sanctions), `courses_table`, `stats_view`, `documents_table`,
    `catalog_table`, `filieres_table`, `freshness_table` (used by `status`).
  Renderers take the plain envelope `data` (dicts/lists as stored) so they work
  straight off `store.load_resource(...)["data"]`.

## 3. Output plumbing (`utils.py`)

- `console = Console(theme=THEME)` (stdout); add `err_console` (stderr).
- `banner()` and `log()` print to `err_console`; both respect a module
  `QUIET` flag. `set_quiet(bool)`.
- Main callback: add `--quiet/-q`; set `QUIET`. Skip the banner when
  `--json`, `-q`, `--quiet`, or `--no-banner` appear in `sys.argv` (banner is
  on stderr anyway, so JSON stdout is clean regardless — this just reduces
  noise). Fix `--version`: handle it before typer's `no_args_is_help` rejects
  the missing subcommand (check `sys.argv` in the callback / add an eager
  `is_eager` version option that prints and exits 0).

## 4. Commands

### `show` group (offline, store→display, each supports `--json`)
`all, profile, grades [--history] [--modules], semesters, years, absences,
courses, stats [CODE], documents, catalog [--niveau --filiere --semestre],
filieres`. Reads `store.load_resource(RESOURCE_FILES[...] / "catalog/...")`.
Empty → themed hint "not cached — run `schoolapp fetch-all`" (exit 0, or exit 1
for a single explicit resource with no cache, matching `catalog show`). `grades`
default = elements latest-AU; `--history` = full; `--modules` = module grades.
`--json` prints `json.dumps(envelope["data"])` (or the filtered slice) to stdout.

### `documents` group
- `documents list` — from `student/documents` store (kind, filename, cached?).
- `documents download [KIND | --all] [--out DIR]` — needs credentials; fetches
  the `documents` list live (or from store), downloads each selected PDF via
  `client.download`, caches to the store with `store.save_document`, and copies
  to `--out` when given. Per-file spinner; per-file error isolation. `--json`
  prints a result manifest (kind, filename, bytes, cached_path).

### Kept / fixed
- `fetch-all`: add a stderr status spinner; `--json` prints the counts+errors
  manifest instead of the table.
- `profile`: live-fetch, **save to store**, then display (so it also warms the
  store); `--json` supported.
- `catalog crawl`: drive a `rich.Progress` bar off the existing `on_combo`
  callback.
- `status`: reuse `render.freshness_table`; `--json` prints the freshness map.
- `--version` works from a bare `schoolapp --version`.

## 5. Testing

- `render.py`: `status_badge` styles for VORD/NV/RAT/`--`; `data_table` shape;
  each resource renderer runs on the seeded fixtures without error.
- `show`: seed store (via a `check_once`/`save_resource`), invoke each
  subcommand, assert key content present AND `--json` output parses with
  `json.loads` and stdout contains no banner/log text.
- `documents download`: monkeypatched client → asserts PDF cached in store
  (+ `--out`), manifest correct, one failing file doesn't abort the rest.
- `--version`: `["--version"]` exit 0, prints version.
- stdout purity: `show profile --json` stdout is exactly parseable JSON.

## 6. Out of scope

- `watcher.py` email/Telegram HTML rendering (different medium; heavily-modified
  user file) — untouched. Terminal renderers in `watcher.py`/`semesters/*` may
  later adopt `render.py` helpers but not in this pass.
- No API/response-shape changes (frozen contracts stay frozen).
