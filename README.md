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
schoolapp s3 list
schoolapp s3 calc
schoolapp s3 watch

schoolapp s4 list
schoolapp s4 calc
schoolapp s4 watch
```

## Common Commands

```bash
schoolapp --help
schoolapp --version
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

- `student/absence/bilan` — new absences (justified or not) and justification changes
- `student/absence/sanctions` — sanction level changes (e.g. Avertissement)
- `student/notesmod-encours` — official module moyennes/decisions as published
- `student/notessem` — semester moyenne, decision and class ranking

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
