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

from . import __version__, render, store
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
from .utils import AppContext, banner, load_config, load_env_file, log
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
    epilog="Examples: schoolapp fetch-all | schoolapp serve | schoolapp s4 watch --once",
)

app.add_typer(s3_app, name="s3", help="Semester S3 namespace")
app.add_typer(s4_app, name="s4", help="Semester S4 namespace")

catalog_app = typer.Typer(no_args_is_help=True, help="Institution-wide curriculum catalog")
app.add_typer(catalog_app, name="catalog")

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
    ctx.obj = AppContext(debug=debug, config=cfg)
    if debug:
        set_log_level("DEBUG")
        log("INFO", "Debug mode enabled")

    banner()
    if config:
        log("INFO", f"Config loaded from {config}")

    if ctx.invoked_subcommand is None:
        _dashboard_impl(json_out=False)


@app.command("doctor")
def doctor(
    ctx: typer.Context,
    check: bool = typer.Option(False, "--check", help="Run one-shot auth/connectivity checks"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds for --check"),
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
) -> None:
    """Print effective runtime config and optional health checks."""
    app_ctx: AppContext = ctx.obj
    panel = Panel.fit(str(app_ctx.config), title="Effective config")
    from .utils import console

    console.print(panel)

    if not check:
        return

    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)
    if password:
        resolved_password = password

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


@app.command("profile")
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


@app.command("fetch-all")
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


@app.command("export")
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


@app.command("status")
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


@app.command("dashboard")
def dashboard(json_out: bool = JSON_OPT) -> None:
    """Overview: who you are, latest results, store freshness, recent changes."""
    _dashboard_impl(json_out=json_out)


@app.command("changes")
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


@app.command("serve")
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
app.add_typer(show_app, name="show")


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
app.add_typer(documents_app, name="documents")


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
