from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from . import __version__, csvout, render, store
from .client import CATALOG_PATH, FILIERES_PATH, SchoolAppClient
from .extractors import crawl_catalog
from .extractors.catalog_presets import (
    CATALOG_RESOURCE,
    load_catalog_modules,
    module_defs,
    reconcile,
    to_module_def,
)
from .presets import PRESET_2A_S3, PRESET_2A_S4
from .render import console, err_console
from .semesters.s3 import app as s3_app
from .semesters.s4 import app as s4_app
from .utils import AppContext, banner, load_config, load_env_file, log, resolve_config_path
from .utils import resolve_credentials
from .utils import set_log_level, set_quiet
from .watcher import _append_history, _history_path, run_health_check

# Reusable across every read/fetch command: clean JSON to stdout (chrome stays
# on stderr, so the pipe is always parseable).
JSON_OPT = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout")


def _emit_json(data) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))

app = typer.Typer(
    name="schoolapp",
    no_args_is_help=False,  # bare `schoolapp` renders the dashboard (help when store empty)
    help=(
        "ENSAM SchoolApp toolkit — one front-end over the shared library, state "
        "store and API.\n\n"
        "Fetch (profile, fetch-all, export, catalog crawl) writes the store; "
        "serve exposes that same store over the API the plasmoid/Android app read; "
        "status shows what it would serve. s3/s4 are the per-semester namespaces."
    ),
    epilog=("Examples: schoolapp             (dashboard)   |  schoolapp changes\n"
            "          schoolapp explain API421   |  schoolapp csv grades -o grades.csv\n"
            "          schoolapp s4 table  |  schoolapp serve\n"
            "Shell completion: schoolapp --install-completion"),
)

app.add_typer(s3_app, name="s3", help="Semester S3 namespace", rich_help_panel="Semesters")
app.add_typer(s4_app, name="s4", help="Semester S4 namespace", rich_help_panel="Semesters")

catalog_app = typer.Typer(no_args_is_help=True, help="Institution-wide curriculum catalog")
app.add_typer(catalog_app, name="catalog", rich_help_panel="Catalog")

RESOURCE_FILES = store.RESOURCE_FILES


def _library_client(ctx: typer.Context, email: str | None, password: str | None,
                    timeout: int, min_interval: float = 0.0) -> SchoolAppClient:
    app_ctx: AppContext = ctx.obj
    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)
    if password:
        resolved_password = password
    if not resolved_email or not resolved_password:
        log("ERROR", "Missing credentials: provide --email/--password, env vars, config file, or keyring")
        raise typer.Exit(code=1)
    client = SchoolAppClient(timeout=timeout, min_interval=min_interval)
    client.login(resolved_email, resolved_password)
    return client


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _version_callback(value: bool) -> None:
    # Eager so `schoolapp --version` prints and exits before typer's
    # no_args_is_help rejects the (absent) subcommand.
    if value:
        typer.echo(f"schoolapp {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback,
                                 is_eager=True, help="Show version and exit"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    quiet: bool = typer.Option(False, "--quiet", "-q", "--no-banner",
                               help="Silence the banner and logs (stderr chrome only)"),
    config: str | None = typer.Option(None, "--config", help="Path to config TOML (default ~/.schoolapp/config.toml)"),
    env_file: str | None = typer.Option(None, "--env-file", help="Load KEY=VALUE env vars from file"),
) -> None:
    # --json is a per-command flag; go quiet for it too so stderr stays clean.
    # Set explicitly (not latching) so the flag resets between invocations.
    set_quiet(quiet or "--json" in sys.argv)

    load_env_file(env_file)
    cfg = load_config(config)
    ctx.obj = AppContext(debug=debug, config=cfg, config_path=resolve_config_path(config))
    if debug:
        set_log_level("DEBUG")
        log("INFO", "Debug mode enabled")

    banner()
    if config:
        log("INFO", f"Config loaded from {config}")

    if ctx.invoked_subcommand is None:
        _dashboard_impl(json_out=False)


@app.command("doctor", rich_help_panel="Live (portal login)")
def doctor(
    ctx: typer.Context,
    check: bool = typer.Option(False, "--check", help="Run one-shot auth/connectivity checks"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds for --check"),
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
) -> None:
    """Print effective runtime config and optional health checks."""
    from zoneinfo import ZoneInfo

    app_ctx: AppContext = ctx.obj
    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)
    if password:
        resolved_password = password

    config_path = app_ctx.config_path
    now = datetime.now(ZoneInfo("Africa/Casablanca")).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        f"checked at:   {now}",
        f"config file:  {config_path} ({'found' if config_path.exists() else 'not found'})",
        f"config keys:  {sorted(app_ctx.config.keys()) or '--'}",
        f"state store:  {store.state_dir()}",
        f"email:        {resolved_email or '-- not set --'}",
        f"password:     {'set' if resolved_password else '-- not set --'}",
    ]
    from .utils import console

    console.print(Panel.fit("\n".join(lines), title="Effective config"))

    if not check:
        return

    if not resolved_email or not resolved_password:
        table = Table(title="Doctor checks", header_style="bold magenta")
        table.add_column("Check")
        table.add_column("Value")
        table.add_row("status", "FAIL")
        table.add_row("message", "Missing credentials: provide --email/--password, env vars, config file, or keyring")
        console.print(table)
        raise typer.Exit(code=1)

    try:
        report = run_health_check(email=resolved_email, password=resolved_password, timeout=timeout)
    except Exception as exc:
        from .utils import console
        console.print(f"[red]Doctor check failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    status = "PASS" if report.get("ok") else "FAIL"
    table = Table(title="Doctor checks", header_style="bold magenta")
    table.add_column("Check")
    table.add_column("Value")
    table.add_row("status", str(status))
    table.add_row("login_http", str(report.get("login_http", "--")))
    table.add_row("auth_http", str(report.get("auth_http", "--")))
    table.add_row("marks_http", str(report.get("marks_http", "--")))
    table.add_row("rows_parsed", str(report.get("rows", "--")))
    table.add_row("has_codeelem", str(report.get("has_codeelem", "--")))
    table.add_row("message", str(report.get("message", "")))
    console.print(table)

    if not report.get("ok"):
        raise typer.Exit(code=1)


@app.command("profile", rich_help_panel="Live (portal login)")
def profile_cmd(
    ctx: typer.Context,
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    json_out: bool = JSON_OPT,
) -> None:
    """Live-fetch the student profile (/index), cache it to the store, and display it."""
    client = _library_client(ctx, email, password, timeout)
    with err_console.status("Fetching profile…"):
        p = client.profile()
    store.save_resource("student/profile", p, source="profile")
    if json_out:
        _emit_json(asdict(p))
        return
    console.print(render.profile_view(asdict(p)))


@app.command("fetch-all", rich_help_panel="Live (portal login)")
def fetch_all_cmd(
    ctx: typer.Context,
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    history: bool = typer.Option(True, "--history/--no-history", help="Include past-year grade pages"),
    stats: bool = typer.Option(False, "--stats", help="Also fetch per-element statistics popups"),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist to the state store"),
    json_out: bool = JSON_OPT,
) -> None:
    """Fetch every per-student resource; persist to the store unless --no-save."""
    client = _library_client(ctx, email, password, timeout)
    with err_console.status("Fetching all resources…"):
        data = client.fetch_all(include_history=history, include_stats=stats)

    if save:
        store.save_student_data(data, source="fetch_all")

    counts = {attr: len(getattr(data, attr)) for attr in (
        "element_grades", "module_grades", "semester_results", "year_results",
        "absences", "absence_summary", "sanctions", "courses", "stats", "documents")}
    if json_out:
        _emit_json({
            "profile": bool(data.profile),
            "diploma": (None if data.diploma is None else ("empty" if data.diploma.empty else "ok")),
            "counts": counts,
            "errors": data.errors,
            "saved_to": str(store.state_dir()) if save else None,
        })
        return

    rows = [["profile", "ok" if data.profile else "--"],
            ["diploma", ("empty" if data.diploma.empty else "ok") if data.diploma else "--"]]
    rows += [[k, str(v)] for k, v in counts.items()]
    console.print(render.data_table("fetch-all", ["Resource", "Result"], rows))
    if save:
        err_console.print(f"[muted]Saved to {store.state_dir()}[/muted]")
    for name, err in data.errors.items():
        err_console.print(f"[error]{name}: {err}[/error]")


@app.command("export", rich_help_panel="Live (portal login)")
def export_cmd(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output directory"),
    with_documents: bool = typer.Option(False, "--with-documents", help="Also download the PDFs"),
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    stats: bool = typer.Option(False, "--stats", help="Also fetch per-element statistics popups"),
) -> None:
    """Fetch everything and write a JSON archive (optionally with the PDFs)."""
    from .utils import console

    client = _library_client(ctx, email, password, timeout)
    data = client.fetch_all(include_history=True, include_stats=stats)

    # Same layout as the store (and /api/export?format=zip): student/all.json,
    # student/<resource>.json, documents/<file>.pdf — so a CLI export and an API
    # export are interchangeable.
    out_dir = Path(out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    store.save_student_data(data, source="export", directory=out_dir)

    if with_documents:
        for doc in data.documents:
            try:
                content = client.download(doc)
                store.save_document(doc.filename, content, directory=out_dir)
                store.save_document(doc.filename, content)  # also cache for /api/documents/<kind>
                log("INFO", f"downloaded {doc.filename}")
            except Exception as exc:  # noqa: BLE001 — one bad PDF must not kill the export
                log("WARNING", f"download {doc.filename} failed: {exc}")

    console.print(f"Exported to {out_dir}")
    for name, err in data.errors.items():
        console.print(f"[red]{name}: {err}[/red]")


STORE_RESOURCES = ["student/all", *RESOURCE_FILES.values(), "catalog/modules", "catalog/filieres"]


@app.command("status", rich_help_panel="Read (offline · store)")
def status_cmd(json_out: bool = JSON_OPT) -> None:
    """Show what the API would serve: per-resource freshness from the local store.

    This is the CLI mirror of `/api/status`'s `resources` map — no network, no auth."""
    fresh = store.freshness(STORE_RESOURCES)
    if json_out:
        _emit_json({"store": str(store.state_dir()), "resources": fresh})
        return
    console.print(render.freshness_table(str(store.state_dir()), fresh))
    if not any(fresh.values()):
        err_console.print("[warning]Store is empty — run `schoolapp fetch-all` or the watcher first.[/warning]")


def _dashboard_impl(json_out: bool) -> None:
    fresh = store.freshness(STORE_RESOURCES)
    if not any(fresh.values()):
        if json_out:
            _emit_json(None)
            return
        render.console.print(render.empty_hint("data"))
        render.console.print("Run [accent]schoolapp --help[/accent] to see all commands.")
        return
    profile_env = store.load_resource("student/profile")
    sems_env = store.load_resource("student/semesters")
    changes = store.read_changes(limit=8)
    if json_out:
        _emit_json({"profile": (profile_env or {}).get("data"),
                    "semesters": (sems_env or {}).get("data") or [],
                    "resources": fresh, "changes": changes})
        return
    render.console.print(render.dashboard_view(
        (profile_env or {}).get("data"), (sems_env or {}).get("data") or [],
        fresh, changes, str(store.state_dir())))


@app.command("dashboard", rich_help_panel="Read (offline · store)")
def dashboard(json_out: bool = JSON_OPT) -> None:
    """Overview: who you are, latest results, store freshness, recent changes."""
    _dashboard_impl(json_out=json_out)


@app.command("changes", rich_help_panel="Read (offline · store)")
def changes_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries (newest first)"),
    type: str | None = typer.Option(None, "--type", help="Filter by change type (grades, rattrapage, absences…)"),
    json_out: bool = JSON_OPT,
) -> None:
    """Change history — the same feed the email digests narrate."""
    items = store.read_changes(limit=limit, type=type)
    if json_out:
        _emit_json(items)
        return
    if not items:
        render.console.print(render.empty_hint("changes"))
        return
    render.console.print(render.changes_table(items))


_CSV_RESOURCES = {
    "elements": "student/elements", "grades": "student/elements",
    "modules": "student/modules", "semesters": "student/semesters",
    "years": "student/years", "courses": "student/courses",
    "absences": "student/absences", "stats": "student/stats",
}


@app.command("csv", rich_help_panel="Read (offline · store)")
def csv_cmd(
    resource: str = typer.Argument(...,
        help="elements|grades|modules|semesters|years|courses|absences|stats"),
    out: str | None = typer.Option(None, "--out", "-o", help="Write to FILE instead of stdout"),
    latest: bool = typer.Option(False, "--latest",
        help="For elements/grades: only the latest académique year"),
) -> None:
    """Export marks (or the NoteRAT/exam ranking stats) as CSV for spreadsheets."""
    if not resource:
        raise typer.BadParameter("resource is required")
    name = _CSV_RESOURCES.get(resource.strip().lower())
    if name is None:
        err_console.print(render.error_panel(
            f"Unknown resource '{resource}'.",
            hint="Choose one of: " + ", ".join(sorted(set(_CSV_RESOURCES)))))
        raise typer.Exit(code=2)
    data, _ = _load(name)
    if not data:
        err_console.print(render.empty_hint(resource))
        raise typer.Exit(code=1)
    if name == "student/stats":
        text = csvout.stats_to_csv(data)
    else:
        if latest and name == "student/elements":
            data = _latest_au(data)
        text = csvout.rows_to_csv(data)
    if out:
        Path(out).expanduser().write_text(text, encoding="utf-8")
        log("SUCCESS", f"Wrote {len(data)} row(s) → {out}")
    else:
        typer.echo(text, nl=False)


def _promo_reconstruct_eval(client, agg_path, agg_params, probe, resolution, real_note="20"):
    """Return (steps, aggregates) for one eval, or None if the eval is unavailable.

    The aggregate popup is probed at `real_note` (the student's own note when
    known) so its 'Votre note'/'Votre classement' reflect the real value, not a
    hypothetical — the constant aggregates (effectif/moyenne/min/max) are the
    same at any note."""
    from . import promo as promo_mod
    first = client.promo_aggregates(agg_path, {**agg_params, "note": str(real_note or "20")})
    if not first:
        return None
    effectif = int(float(first.get("Effectif", "0") or 0))
    if effectif <= 0:
        return None
    steps = promo_mod.reconstruct(
        lambda n: (probe(n) or (1, effectif))[0], resolution=resolution)
    return steps, first


def _write_csv(path, rows, columns):
    Path(path).write_text(csvout.rows_to_csv(rows, columns=columns), encoding="utf-8")
    log("SUCCESS", f"Wrote {len(rows)} row(s) → {path}")


def _emit_promo_artifacts(code, level, per_eval, out_dir, bin_width, plot, your=None, meta=None):
    """Write 4 CSVs + optional PNG per eval into out_dir; persist store; print paths.

    per_eval: list of (eval_label, steps, aggregates).
    your:     eval_label → (your_note, your_rank).
    meta:     eval_label → (au, filiere) for the summary."""
    from . import promo as promo_mod
    your = your or {}
    meta = meta or {}
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    summaries, cached = [], {}
    for label, steps, aggr in per_eval:
        yn, yr = your.get(label, ("", ""))
        au, filiere = meta.get(label, ("", ""))
        hist = promo_mod.histogram_rows(code, level, label, steps, width=bin_width)
        dist = promo_mod.distribution_rows(code, level, label, steps)
        studs = promo_mod.student_rows(code, level, label, steps)
        summ = promo_mod.summary_row(code, level, label, steps, aggr,
                                     your_note=yn, your_rank=yr, au=au, filiere=filiere)
        base = out / f"promo_{code}_{label}"
        _write_csv(f"{base}_hist.csv", hist,
                   ["code", "level", "eval", "bin_low", "bin_high", "count", "percent", "cumulative"])
        _write_csv(f"{base}_dist.csv", dist,
                   ["code", "level", "eval", "note", "count", "rank_top"])
        _write_csv(f"{base}_students.csv", studs,
                   ["code", "level", "eval", "rank", "note"])
        _write_csv(f"{base}_summary.csv", [summ],
                   ["code", "level", "eval", "au", "filiere", "effectif", "recovered",
                    "moyenne_promo", "min", "max", "ecart_type", "median", "your_note", "your_rank"])
        if plot:
            try:
                from . import plots
                mean = float(aggr["Moyenne promo"]) if aggr.get("Moyenne promo") else None
                yn_f = float(yn) if yn else None
                png = plots.histogram_png(hist, path=f"{base}_hist.png",
                                          title=f"{code} · {label}",
                                          subtitle=f"{filiere} {au}".strip(),
                                          mean=mean, your_note=yn_f)
                log("SUCCESS", f"Wrote {png}")
            except RuntimeError as exc:
                log("WARNING", f"Plot skipped: {exc}")
        summaries.append(summ)
        cached[label] = {"steps": [[n, c] for n, c in steps], "summary": summ, "bins": hist}
    store.save_resource(f"promo/{code.lower()}", cached, source="promo")
    return summaries


@app.command("promo", rich_help_panel="Live (portal login)")
def promo_cmd(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="Element code, e.g. API421"),
    eval: str = typer.Option("rat,moy,ex,cc", "--eval",
        help="Comma list of evaluations: rat,moy,ex,cc,tp"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0,
        help="Seconds between requests — be polite to the school server"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's notes for an ELEMENT (anonymized).

    Writes, per evaluation, a histogram CSV (how many got each mark), the exact
    distribution, per-student rows, a stats summary, and a histogram PNG — all
    named promo_<CODE>_<eval>_*. Fires many rate-limited requests."""
    from . import promo as promo_mod
    from .client import STATS_PATH

    if not code:
        raise typer.BadParameter("code is required")
    code = code.upper()
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    target = next((g for g in client.element_grades() if g.code.upper() == code), None)
    au = target.au if target else None
    if not au:
        err_console.print(render.error_panel(
            f"Could not resolve the année universitaire for {code}."))
        raise typer.Exit(code=2)

    note_by_eval = {"NoteCC": target.cc, "NoteEX": target.ex, "NoteTP": target.tp,
                    "NoteRAT": target.rat, "MoyElem": target.moy}
    per_eval, your = [], {}
    for ev in (_split_csv(eval) or ["rat", "moy", "ex", "cc"]):
        eval_param = SchoolAppClient._EVAL_ALIASES.get(ev.strip().lower(), ev)
        label = promo_mod.EVAL_LABELS.get(ev.strip().lower(), eval_param)
        agg_params = {"eval": eval_param, "codeelem": code, "au": au}
        real = note_by_eval.get(eval_param, "")
        real = real if real and real != "--" else "20"
        with err_console.status(f"Reconstructing {code} · {label}…"):
            res = _promo_reconstruct_eval(
                client, STATS_PATH, agg_params,
                lambda n, e=ev: client.rank_for_note(code, e, au, n),
                resolution, real_note=real)
        if not res:
            log("WARNING", f"{label} unavailable for {code} — skipping")
            continue
        steps, aggr = res
        per_eval.append((label, steps, aggr))
        your[label] = (aggr.get("Votre note", ""), aggr.get("Votre classement", ""))
        log("SUCCESS", f"{label}: recovered {sum(c for _, c in steps)} notes")

    if not per_eval:
        err_console.print(render.error_panel(f"No promotion data reconstructed for {code}."))
        raise typer.Exit(code=2)
    # element rows carry no filière; au is the resolved element au
    meta = {label: (au, "") for label, _, _ in per_eval}
    _emit_promo_artifacts(code, "element", per_eval, out_dir, bin, not no_plot, your, meta)


def _resolve_sem_row(rows, label):
    if not rows:
        return None
    if not label:
        return rows[-1]
    return next((r for r in rows if r.semestre.upper() == label.upper()), None)


def _resolve_year_row(rows, label):
    if not rows:
        return None
    if not label:
        return rows[-1]
    return next((r for r in rows if r.niveau.upper() == label.upper()), None)


@app.command("promo-sem", rich_help_panel="Live (portal login)")
def promo_sem_cmd(
    ctx: typer.Context,
    semestre: Optional[str] = typer.Argument(None, help="Semester label, e.g. S1 S2 S3 S4 (default: latest)"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0, help="Seconds between requests"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's SEMESTER moyennes (anonymized)."""
    from .client import SEM_STATS_PATH
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    rows = client.semester_results()
    row = _resolve_sem_row(rows, semestre)
    if not row:
        labels = ", ".join(sorted({r.semestre for r in rows})) or "none"
        err_console.print(render.error_panel(
            f"Semester {semestre!r} not found.", hint=f"Available: {labels}"))
        raise typer.Exit(code=2)
    code, filiere = row.semestre.upper(), row.raw.get("Filière", "")
    agg_params = {"eval": "MoySem", "niveau": row.niveau, "filiere": filiere,
                  "semestre": row.semestre, "au": row.au}
    with err_console.status(f"Reconstructing {code} · MoySem…"):
        res = _promo_reconstruct_eval(
            client, SEM_STATS_PATH, agg_params,
            lambda n: client.rank_for_note_sem(row.niveau, filiere, row.semestre, row.au, n),
            resolution, real_note=row.moy_sem or "20")
    if not res:
        err_console.print(render.error_panel(f"No promotion data for {code}."))
        raise typer.Exit(code=2)
    steps, aggr = res
    per_eval = [("MoySem", steps, aggr)]
    _emit_promo_artifacts(code, "semester", per_eval, out_dir, bin, not no_plot,
                          {"MoySem": (row.moy_sem, row.classement)},
                          {"MoySem": (row.au, filiere)})


@app.command("promo-year", rich_help_panel="Live (portal login)")
def promo_year_cmd(
    ctx: typer.Context,
    niveau: Optional[str] = typer.Argument(None, help="Year label, e.g. 1A 2A (default: latest)"),
    out_dir: str = typer.Option(".", "--out-dir", "-o", help="Directory for the CSV/PNG artifacts"),
    bin: float = typer.Option(1.0, "--bin", min=0.1, help="Histogram bin width"),
    no_plot: bool = typer.Option(False, "--no-plot", help="Skip the PNG figure"),
    resolution: float = typer.Option(0.01, help="Note granularity to resolve"),
    min_interval: float = typer.Option(0.25, min=0.0, help="Seconds between requests"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
) -> None:
    """Reconstruct the WHOLE promotion's ANNÉE moyennes (anonymized)."""
    from .client import YEAR_STATS_PATH
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    rows = client.year_results()
    row = _resolve_year_row(rows, niveau)
    if not row:
        labels = ", ".join(sorted({r.niveau for r in rows})) or "none"
        err_console.print(render.error_panel(
            f"Year {niveau!r} not found.", hint=f"Available: {labels}"))
        raise typer.Exit(code=2)
    code = row.niveau.upper()
    agg_params = {"eval": "MoyAn", "niveau": row.niveau, "filiere": row.filiere, "au": row.au}
    with err_console.status(f"Reconstructing {code} · MoyAn…"):
        res = _promo_reconstruct_eval(
            client, YEAR_STATS_PATH, agg_params,
            lambda n: client.rank_for_note_year(row.niveau, row.filiere, row.au, n),
            resolution, real_note=row.moy_annee or "20")
    if not res:
        err_console.print(render.error_panel(f"No promotion data for {code}."))
        raise typer.Exit(code=2)
    steps, aggr = res
    per_eval = [("MoyAn", steps, aggr)]
    _emit_promo_artifacts(code, "year", per_eval, out_dir, bin, not no_plot,
                          {"MoyAn": (row.moy_annee, row.classement)},
                          {"MoyAn": (row.au, row.filiere)})


@app.command("explain", rich_help_panel="Read (offline · store)")
def explain(
    code: str = typer.Argument(..., help="Element code, e.g. API421"),
    json_out: bool = JSON_OPT,
) -> None:
    """Règlement walkthrough for one element: how SO/SR/decision are computed."""
    from .academics import explain_element

    if not code:
        raise typer.BadParameter("code is required")
    env = store.load_resource("student/elements")
    items = (env or {}).get("data") or []
    exp = explain_element(code, items)
    if exp is None:
        if json_out:
            _emit_json(None)
        else:
            render.console.print(render.error_panel(
                f"No cached grades for {code.upper()}.",
                hint="Run `schoolapp fetch-all` first, or check the code."))
        raise typer.Exit(code=1)
    if json_out:
        _emit_json(exp)
        return
    inp = exp["inputs"]
    render.console.print(render.data_table(
        f"{exp['code']} · AU {exp['au']}", ["CC", "EX", "TP", "Moy SO", "RAT", "Moy SR", "Décision"],
        [[inp["cc"] or "--", inp["ex"] or "--", inp["tp"] or "--", inp["moy_so"] or "--",
          inp["rat"] or "--", inp["moy_sr"] or "--", inp["decision"] or "--"]]))
    rows = [[s["article"], s["label"], s["formula"], s["value"],
             "officiel" if s["official"] else "calculé*"] for s in exp["steps"]]
    render.console.print(render.data_table(
        "Règlement (CE 2019-10-22 / CU 2019-12-25)",
        ["Article", "Étape", "Formule", "Valeur", "Source"], rows,
        caption="* calculé par l'outil — en attente de publication par le portail"))


@app.command("serve", rich_help_panel="Server")
def serve_cmd(
    ctx: typer.Context,
    host: str = typer.Option("0.0.0.0", help="Bind address"),
    port: int = typer.Option(8787, help="Port"),
    threads: int = typer.Option(4, min=1, help="waitress worker threads"),
    reload: bool = typer.Option(False, "--reload", help="Use Flask's dev server (autoreload) instead of waitress"),
) -> None:
    """Serve the read-through API over the same store the watcher writes.

    Reads credentials/API_KEY from the env already loaded by --env-file/--config,
    so `schoolapp --env-file .env serve` is the one-liner the plasmoid/app point at."""
    import os

    from .api import app as flask_app
    from .utils import console

    if not os.environ.get("API_KEY"):
        log("WARNING", "API_KEY is not set — every endpoint is unauthenticated")
    console.print(
        f"[green]SchoolApp API[/green] → http://{host}:{port}  "
        f"(serving {store.state_dir()})"
    )
    if reload:
        flask_app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve as waitress_serve
        waitress_serve(flask_app, host=host, port=port, threads=threads)


@catalog_app.command("crawl")
def catalog_crawl(
    ctx: typer.Context,
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    filieres: str | None = typer.Option(None, "--filieres", help="Comma-separated filière codes (default: all)"),
    niveaux: str | None = typer.Option(None, "--niveaux", help="Comma-separated niveaux (default: all)"),
    min_interval: float = typer.Option(1.0, help="Seconds between requests (politeness)"),
) -> None:
    """Crawl the (niveau × filière × semestre) catalog into the store. Incremental: re-runs merge."""
    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    merged = {(m.code_mod, m.niveau, m.semestre, m.filiere): m for m in load_catalog_modules()}
    initial = {k: asdict(m) for k, m in merged.items()}
    progress = {"combos": 0, "errors": 0}

    with err_console.status("Crawling catalog…") as spinner:
        def on_combo(n, f, s, fresh, err):
            progress["combos"] += 1
            if err is not None:
                progress["errors"] += 1
                log("WARNING", f"catalog combo ({n}, {f}, {s}) failed: {err}")
            elif fresh:
                for m in fresh:
                    merged[(m.code_mod, m.niveau, m.semestre, m.filiere)] = m
                store.save_resource(CATALOG_RESOURCE, list(merged.values()), source=CATALOG_PATH)
            spinner.update(
                f"Crawling catalog… {progress['combos']} combos, {len(merged)} modules, "
                f"{progress['errors']} errors")

        crawl_catalog(client, niveaux=_split_csv(niveaux), filieres=_split_csv(filieres),
                      on_combo=on_combo)
    filiere_models = client.filieres()
    store.save_resource("catalog/filieres", filiere_models, source=FILIERES_PATH)

    mismatches = reconcile([to_module_def(m) for m in merged.values()],
                           list(PRESET_2A_S3) + list(PRESET_2A_S4))
    for msg in mismatches:
        log("WARNING", f"catalog≠presets: {msg}")

    # One change summary per crawl (spec §9): the catalog never alerts per cell.
    added = [k for k in merged if k not in initial]
    modified = [k for k in merged if k in initial and asdict(merged[k]) != initial[k]]
    if added or modified:
        sample = ", ".join(sorted({k[0] for k in added + modified})[:10])
        summary = f"Catalogue: +{len(added)} module(s), ~{len(modified)} modifié(s) ({sample})"
        console.print(f"[bold]{summary}[/bold]")
        _append_history(_history_path("catalog", None), {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "type": "catalog",
            "summary": summary,
        })

    console.print(
        f"Crawl done: {progress['combos']} combos, {len(merged)} modules, "
        f"{len(filiere_models)} filières, {progress['errors']} errors → "
        f"{store.resource_path(CATALOG_RESOURCE)}"
    )


@catalog_app.command("show")
def catalog_show(
    niveau: str = typer.Argument(..., help="e.g. 2A"),
    filiere: str = typer.Argument(..., help="e.g. API-MPT"),
    semestre: str = typer.Argument(..., help="Absolute semester as the catalog reports it, e.g. S3"),
) -> None:
    """Show cached catalog modules (with element weights) for one combo."""
    from .utils import console

    if not niveau or not filiere or not semestre:
        raise typer.BadParameter("niveau, filiere, and semestre are all required")
    defs = module_defs(niveau, filiere, semestre)
    if not defs:
        console.print("[yellow]No cached modules for this combo — run `schoolapp catalog crawl` first.[/yellow]")
        raise typer.Exit(code=1)
    table = Table(title=f"{filiere} {niveau} {semestre} — {len(defs)} modules",
                  header_style="bold magenta")
    for col in ("Code", "Intitulé", "Coef", "Seuil", "Élim.", "Éléments"):
        table.add_column(col)
    for d in defs:
        elems = ", ".join(
            f"{e.code}(cc={e.coef_cc}, ex={e.coef_ex}, tp={e.coef_tp})" for e in d.elements
        )
        table.add_row(d.code, d.title, str(d.coef_mod), str(d.seuil),
                      str(d.eliminatoire), elems or "--")
    console.print(table)


# ── `show` group: offline, reads the store, mirrors every API endpoint ────────

show_app = typer.Typer(no_args_is_help=True,
                       help="Display cached data from the store (offline; mirrors the API).")
app.add_typer(show_app, name="show", rich_help_panel="Read (offline · store)")


def _load(name: str):
    env = store.load_resource(name)
    return (env["data"], env.get("fetched_at")) if env else (None, None)


def _latest_au(items: list[dict]) -> list[dict]:
    aus = [g.get("au", "") for g in items if g.get("au")]
    if not aus:
        return items
    latest = max(aus)
    return [g for g in items if g.get("au") == latest]


def _render_or_json(resource: str, name: str, renderer, json_out: bool, transform=lambda d: d):
    data, ts = _load(name)
    if data is None:
        if json_out:
            _emit_json(None)
        else:
            err_console.print(render.empty_hint(resource))
        return
    shown = transform(data)
    if json_out:
        _emit_json(shown)
        return
    console.print(renderer(shown))
    if ts:
        err_console.print(f"[muted]fetched {ts}[/muted]")


@show_app.command("all")
def show_all(json_out: bool = JSON_OPT) -> None:
    """The full StudentData bundle (counts overview, or the whole payload as --json)."""
    data, ts = _load("student/all")
    if data is None:
        if json_out:
            _emit_json(None)
        else:
            err_console.print(render.empty_hint("student data"))
        return
    if json_out:
        _emit_json(data)
        return
    rows = []
    for key, value in data.items():
        if key in ("fetched_at", "errors"):
            continue
        if isinstance(value, list):
            rows.append([key, str(len(value))])
        elif isinstance(value, dict):
            rows.append([key, "present"])
        else:
            rows.append([key, "present" if value else "--"])
    console.print(render.data_table("Student data (cached)", ["Resource", "Count / state"], rows))
    for name, err in (data.get("errors") or {}).items():
        err_console.print(f"[error]{name}: {err}[/error]")
    if ts:
        err_console.print(f"[muted]fetched {ts}[/muted]")


@show_app.command("profile")
def show_profile(json_out: bool = JSON_OPT) -> None:
    """Cached student profile."""
    _render_or_json("profile", "student/profile", render.profile_view, json_out)


@show_app.command("grades")
def show_grades(
    history: bool = typer.Option(False, "--history", help="Include past-year rows (default: latest AU only)"),
    modules: bool = typer.Option(False, "--modules", help="Show module grades instead of element grades"),
    json_out: bool = JSON_OPT,
) -> None:
    """Cached grades — element grades by default, module grades with --modules."""
    name = "student/modules" if modules else "student/elements"
    renderer = render.module_grades_table if modules else render.element_grades_table
    transform = (lambda d: d) if history else _latest_au
    _render_or_json("grades", name, renderer, json_out, transform)


@show_app.command("semesters")
def show_semesters(json_out: bool = JSON_OPT) -> None:
    """Cached semester results."""
    _render_or_json("semester results", "student/semesters", render.semesters_table, json_out)


@show_app.command("years")
def show_years(json_out: bool = JSON_OPT) -> None:
    """Cached year results."""
    _render_or_json("year results", "student/years", render.years_table, json_out)


@show_app.command("courses")
def show_courses(json_out: bool = JSON_OPT) -> None:
    """Cached course enrollments."""
    _render_or_json("courses", "student/courses", render.courses_table, json_out)


@show_app.command("absences")
def show_absences(json_out: bool = JSON_OPT) -> None:
    """Cached absences: event log, per-element summary, and sanctions."""
    absences, ts = _load("student/absences")
    summary, _ = _load("student/absence_summary")
    sanctions, _ = _load("student/sanctions")
    if absences is None and summary is None and sanctions is None:
        if json_out:
            _emit_json(None)
        else:
            err_console.print(render.empty_hint("absences"))
        return
    if json_out:
        _emit_json({"absences": absences or [], "summary": summary or [], "sanctions": sanctions or []})
        return
    console.print(render.absences_view(absences or [], summary or [], sanctions or []))
    if ts:
        err_console.print(f"[muted]fetched {ts}[/muted]")


@show_app.command("stats")
def show_stats(
    code: Optional[str] = typer.Argument(None, help="Filter to one element code"),
    json_out: bool = JSON_OPT,
) -> None:
    """Cached per-element statistics (fetch with `fetch-all --stats`)."""
    def transform(items):
        return [s for s in items if s.get("element", "").upper() == code.upper()] if code else items
    _render_or_json("statistics", "student/stats", render.stats_view, json_out, transform)


@show_app.command("documents")
def show_documents(json_out: bool = JSON_OPT) -> None:
    """Cached document descriptors and whether their PDF is downloaded."""
    data, ts = _load("student/documents")
    if data is None:
        if json_out:
            _emit_json(None)
        else:
            err_console.print(render.empty_hint("documents"))
        return
    cached = {d.get("filename", ""): store.document_path(d.get("filename", "")).exists() for d in data}
    if json_out:
        _emit_json([{**d, "cached": cached.get(d.get("filename", ""), False)} for d in data])
        return
    console.print(render.documents_table(data, cached=cached))
    if ts:
        err_console.print(f"[muted]fetched {ts}[/muted]")


@show_app.command("catalog")
def show_catalog(
    niveau: Optional[str] = typer.Option(None, "--niveau"),
    filiere: Optional[str] = typer.Option(None, "--filiere"),
    semestre: Optional[str] = typer.Option(None, "--semestre"),
    json_out: bool = JSON_OPT,
) -> None:
    """Cached institution catalog modules (filterable)."""
    def transform(items):
        out = items
        for field, want in (("niveau", niveau), ("filiere", filiere), ("semestre", semestre)):
            if want:
                out = [m for m in out if (m.get(field) or "").upper() == want.upper()]
        return out
    _render_or_json("catalog", "catalog/modules", render.catalog_table, json_out, transform)


@show_app.command("filieres")
def show_filieres(json_out: bool = JSON_OPT) -> None:
    """Cached filière list."""
    _render_or_json("filières", "catalog/filieres", render.filieres_table, json_out)


# ── `documents` group: list + download the student PDFs ───────────────────────

documents_app = typer.Typer(no_args_is_help=True,
                            help="Student PDF documents (attestation de scolarité, relevés).")
app.add_typer(documents_app, name="documents", rich_help_panel="Live (portal login)")


@documents_app.command("list")
def documents_list(json_out: bool = JSON_OPT) -> None:
    """List document descriptors from the store and whether each PDF is cached."""
    show_documents(json_out=json_out)


@documents_app.command("download")
def documents_download(
    ctx: typer.Context,
    kind: Optional[str] = typer.Argument(None, help="Document kind or filename (omit to list choices)"),
    download_all: bool = typer.Option(False, "--all", help="Download every available document"),
    out: Optional[str] = typer.Option(None, "--out", help="Also copy the PDFs into this directory"),
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    json_out: bool = JSON_OPT,
) -> None:
    """Download attestation / relevé PDFs, caching them into the store."""
    client = _library_client(ctx, email, password, timeout)
    with err_console.status("Listing documents…"):
        docs = client.documents()

    if download_all:
        selected = docs
    elif kind:
        selected = [d for d in docs if kind in (d.kind, d.filename)]
        if not selected:
            err_console.print(render.error_panel(
                f"No document matches '{kind}'.",
                hint="Available: " + ", ".join(d.kind for d in docs)))
            raise typer.Exit(code=1)
    else:  # nothing selected → show the menu
        if json_out:
            _emit_json([{"kind": d.kind, "filename": d.filename} for d in docs])
        else:
            console.print(render.data_table("Available documents", ["Kind", "Filename"],
                                            [[d.kind, d.filename] for d in docs],
                                            caption="Pass a KIND or --all to download"))
        return

    out_dir = Path(out).expanduser() if out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for d in selected:
        try:
            with err_console.status(f"Downloading {d.filename}…"):
                content = client.download(d)
            store.save_document(d.filename, content)
            if out_dir:
                (out_dir / d.filename).write_bytes(content)
            manifest.append({"kind": d.kind, "filename": d.filename, "bytes": len(content),
                             "cached_path": str(store.document_path(d.filename))})
            log("SUCCESS", f"downloaded {d.filename} ({len(content)} bytes)")
        except Exception as exc:  # noqa: BLE001 — one bad PDF must not abort the rest
            manifest.append({"kind": d.kind, "filename": d.filename, "error": str(exc)})
            log("WARNING", f"download {d.filename} failed: {exc}")

    if json_out:
        _emit_json(manifest)
        return
    rows = [[m["kind"], m["filename"], str(m.get("bytes", "--")),
             m.get("cached_path") or m.get("error", "")] for m in manifest]
    console.print(render.data_table("Downloaded", ["Kind", "Filename", "Bytes", "Path / error"], rows))


if __name__ == "__main__":
    app()
