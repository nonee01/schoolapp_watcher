# SchoolApp CLI

Production-oriented CLI for ENSAM SchoolApp with semester namespaces:

- `schoolapp s3 ...`
- `schoolapp s4 ...`

## Features

- Semester-first commands (`s3`, `s4`)
- Watch mode with snapshot diffing
- Interactive weighted calculator
- Module listing per semester
- Optional SMTP notifications
- Rich output (tables, panels, color logs)

## Installation

### Local editable install (recommended)

```bash
cd /home/notadil/Projects/schoolapp_watcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### User install

```bash
python3 -m pip install --user -e .
```

If `schoolapp` is not found, ensure your user bin path is in `PATH`.

## CLI Layout

```text
schoolapp                     # dashboard: profile, latest results, freshness, recent changes
schoolapp dashboard           # …the same, explicitly
schoolapp changes             # change history - the same feed the email digests narrate
schoolapp explain API421      # règlement walkthrough for one element (SO/SR/decision + articles)
schoolapp csv grades -o m.csv # export marks/rankings as CSV for a spreadsheet
schoolapp show grades         # offline view of any cached resource (mirrors the API)
schoolapp fetch-all           # log in, fetch everything, write the store
schoolapp serve               # expose the store over the API the plasmoid/Android app read

schoolapp s3 list | calc | watch
schoolapp s4 list | calc | watch | table
```

Commands are grouped in `--help` by panel: **Read** (offline, from the store),
**Live** (logs into the portal), **Server**, **Semesters**, **Catalog**.

### Rattrapage / règlement

`schoolapp explain <CODE>` and the `s3/s4 table` views apply the official ENSAM
evaluation règlement (CE 2019‑10‑22 / CU 2019‑12‑25): after a rattrapage the
element moyenne is `max(SO, max(0.3·CC + 0.7·Rat, Rat))` (Art. 7) and a module
validated on rattrapage is capped at the pass bar - 11/20 in the prépa years,
12/20 in the cycle ingénieur (Art. 9). Values the tool computes while the portal
has not yet published them are shown with a `*` marker.

### CSV export

```bash
schoolapp csv grades --latest -o grades.csv   # current-year element marks
schoolapp csv stats  -o rankings.csv          # NoteRAT/exam ranking stats (needs fetch-all --stats)
```

Resources: `elements`/`grades`, `modules`, `semesters`, `years`, `courses`,
`absences`, `stats`. The same rows are available over HTTP at
`GET /api/csv/<resource>`.

### Whole-promotion notes (anonymized)

```bash
schoolapp promo API421 --eval rat,moy,ex,cc -o out/   # one element
schoolapp promo-sem S1  -o out/                        # a whole semester
schoolapp promo-year 2A -o out/                        # a whole year
```

Recovers **every student's note** across the whole promotion - without names,
which the portal never exposes. It works because the stats endpoint answers
`rank(note)` for any hypothetical note, so sweeping that value traces the full
grade distribution. Endpoints: `/notes-stat/elemevalsat` (element),
`/notes-stat/semsat` (semester), `/notes-stat/anneesat` (année). Target a
semester by its label (`S1`…`S4`) and a year by its niveau (`1A`, `2A`); the
année universitaire and filière are resolved from your own rows automatically.

Each run writes, per evaluation, into `--out-dir` (default `.`), all keyed by
the code (`API421`, `S1`, `2A`):

| File | Contents |
|------|----------|
| `promo_<code>_<eval>_hist.csv` | binned histogram - how many got each mark (`bin_low,bin_high,count,percent,cumulative`) |
| `promo_<code>_<eval>_dist.csv` | exact reconstructed distribution (`note,count,rank_top`) |
| `promo_<code>_<eval>_students.csv` | one anonymized row per student (`rank,note`) |
| `promo_<code>_<eval>_summary.csv` | effectif, moyenne promo, min/max/écart-type, median, your note/rank |
| `promo_<code>_<eval>_hist.png` | histogram figure (mean + your-note markers); needs matplotlib, `--no-plot` to skip |

Fires many **rate-limited** requests (`--min-interval`, default 0.25 s) - expect
a few minutes per evaluation. `--bin` sets the histogram bin width (default 1.0).
The reconstruction is cached and served at `GET /api/promo/<code>`.

## Common Commands

```bash
schoolapp --help
schoolapp --version
schoolapp --install-completion   # shell tab-completion
schoolapp s3 --help
schoolapp s4 --help
```

### List modules

```bash
schoolapp s3 list
schoolapp s4 list
```

### Calculator

Interactive:

```bash
schoolapp s3 calc
schoolapp s4 calc
```

From JSON marks file:

```bash
schoolapp s4 calc --marks-file marks.json
```

Example `marks.json`:

```json
{
  "API411.cc": 12,
  "API411.ex": 14,
  "API421.cc": 10,
  "API421.ex": 13
}
```

### Watch mode

Single run:

```bash
schoolapp s4 watch --once --email "you@example.com" --password "secret"
```

Continuous polling:

```bash
schoolapp s3 watch --interval 300 --email "you@example.com" --password "secret"
```

Watch mode polls every `--interval` seconds (default 300) all day, slowing to
30 minutes between 04:00 and 06:00. The session is reused between checks
(re-login only on expiry). Changes are detected per-element on real mark
fields, so cosmetic page changes don't trigger notifications. With
`--notify-email`, repeated failures for over an hour send a single warning
email, followed by a recovery email when checks succeed again.

Each check also watches, in the same session and email:

- `student/absence/bilan` - new absences (justified or not) and justification changes
- `student/absence/sanctions` - sanction level changes (e.g. Avertissement)
- `student/notesmod-encours` - official module moyennes/decisions as published
- `student/notessem` - semester moyenne, decision and class ranking

With email notification:

```bash
schoolapp s3 watch --interval 900 --notify-email --email "you@example.com" --password "secret"
```

## Config and Environment

Global options:

- `--debug`
- `--version`
- `--config PATH`
- `--env-file PATH`

If `--env-file` is not provided, the CLI will try to auto-load an env file from
the current working directory or project root: it checks `.env` first and then
`.env.example`. If `.env` is missing but `.env.example` exists, the CLI will
create `.env` by copying `.env.example` (permissions set to 600 where possible).
You can also pass `--env-file .env.example` explicitly.

Optional config file: `~/.schoolapp/config.toml`

```toml
[schoolapp]
email = "you@example.com"
password = "secret"

[smtp]
host = "smtp.gmail.com"
port = 587
username = "you@gmail.com"
password = "app-password"
from = "you@gmail.com"
to = "you@gmail.com"
```

Supported env vars:

- `SCHOOLAPP_EMAIL`, `SCHOOLAPP_PASSWORD`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`

## Common Errors

### Wrong Python interpreter

Symptoms: `ModuleNotFoundError` (e.g. `requests`)

Fix:

```bash
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
schoolapp s4 list
```

### Missing virtualenv activation

Run commands via venv interpreter directly:

```bash
/home/notadil/Projects/schoolapp_watcher/.venv/bin/schoolapp s3 list
```

### SMTP issues

- Check SMTP host/port/credentials
- Use app passwords where required (e.g. Gmail)
- Test once with `--once` before running long watch mode

## Exit Codes

- `0`: success / no change in watch-once
- `1`: change detected in watch-once
- `2`: runtime error (validation/network/login/etc)
