# SchoolApp Watcher

CLI tool that logs into ENSAM SchoolApp, fetches the marks table, and alerts you when it changes.

## Setup

```bash
cd schoolapp
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Optional: install as a CLI command (recommended):

```bash
cd schoolapp
. .venv/bin/activate
pip install -e .
schoolapp-watch --help
```

## Run once

```bash
python schoolapp_watch.py --email "you@example.com"
```

Or load credentials from a file:

```bash
python schoolapp_watch.py --env-file .env.example
```

Recommended (keeps secrets out of git):

```bash
cp .env.example .env
# edit .env and set SCHOOLAPP_EMAIL / SCHOOLAPP_PASSWORD
schoolapp
```

## Watch mode (polling)

```bash
python schoolapp_watch.py --email "you@example.com" --watch --interval 900
```

## Calculator

Interactive calculator using your S3 (2A) coefficients:

```bash
python schoolapp_watch.py --calc
```

Or provide marks via JSON:

```json
{
	"API311.cc": 12,
	"API311.ex": 14,
	"API321.cc": 10,
	"API321.ex": 13
}
```

Run it:

```bash
python schoolapp_watch.py --calc --marks-file marks.json
```

## Email notifications

Set these env vars (recommended):

- `SCHOOLAPP_EMAIL` / `SCHOOLAPP_PASSWORD`
- `SMTP_HOST` (e.g. `smtp.gmail.com`)
- `SMTP_PORT` (e.g. `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM` (e.g. `you@gmail.com`)
- `SMTP_TO` (destination email)

Then:

```bash
python schoolapp_watch.py --watch --interval 900 --notify-email
```

Tip: prefer env vars for passwords (avoid passing `--password` on the command line).

Notes:
- “Instant” means: the moment a change is detected on the next poll.
- If your mail provider requires an app password (Gmail), use that.
