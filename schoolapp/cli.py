from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from . import __version__, store
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
from .semesters.s3 import app as s3_app
from .semesters.s4 import app as s4_app
from .utils import AppContext, banner, load_config, load_env_file, log
from .utils import resolve_credentials
from .utils import set_log_level
from .watcher import run_health_check

app = typer.Typer(
    name="schoolapp",
    no_args_is_help=True,
    help="ENSAM SchoolApp CLI with semester namespaces (s3, s4)",
    epilog="Examples: schoolapp s3 calc | schoolapp s4 list | schoolapp s3 watch --once",
)

app.add_typer(s3_app, name="s3", help="Semester S3 namespace")
app.add_typer(s4_app, name="s4", help="Semester S4 namespace")

catalog_app = typer.Typer(no_args_is_help=True, help="Institution-wide curriculum catalog")
app.add_typer(catalog_app, name="catalog")

# StudentData attribute -> store resource name (spec §7 layout)
RESOURCE_FILES = {
    "profile": "student/profile",
    "element_grades": "student/elements",
    "module_grades": "student/modules",
    "semester_results": "student/semesters",
    "year_results": "student/years",
    "diploma": "student/diploma",
    "absences": "student/absences",
    "absence_summary": "student/absence_summary",
    "sanctions": "student/sanctions",
    "courses": "student/courses",
    "stats": "student/stats",
    "documents": "student/documents",
}


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


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    config: str | None = typer.Option(None, "--config", help="Path to config TOML (default ~/.schoolapp/config.toml)"),
    env_file: str | None = typer.Option(None, "--env-file", help="Load KEY=VALUE env vars from file"),
) -> None:
    if version:
        typer.echo(f"schoolapp {__version__}")
        raise typer.Exit(code=0)

    load_env_file(env_file)
    cfg = load_config(config)
    ctx.obj = AppContext(debug=debug, config=cfg)
    # set log level from env or debug flag
    if debug:
        set_log_level("DEBUG")
        log("INFO", "Debug mode enabled")
    else:
        # ensure env var is respected by utils module init
        pass

    banner()
    if config:
        log("INFO", f"Config loaded from {config}")


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
) -> None:
    """Fetch and display the student profile (/index)."""
    from .utils import console

    client = _library_client(ctx, email, password, timeout)
    p = client.profile()
    table = Table(title="Student profile", header_style="bold magenta")
    table.add_column("Field")
    table.add_column("Value")
    for k, v in p.raw.items():
        table.add_row(k, v or "--")
    if p.photo_url:
        table.add_row("Photo", p.photo_url)
    console.print(table)


@app.command("fetch-all")
def fetch_all_cmd(
    ctx: typer.Context,
    email: str | None = typer.Option(None, help="SchoolApp email (overrides config/env)"),
    password: str | None = typer.Option(None, help="SchoolApp password (overrides config/env)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    history: bool = typer.Option(True, "--history/--no-history", help="Include past-year grade pages"),
    stats: bool = typer.Option(False, "--stats", help="Also fetch per-element statistics popups"),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist to the state store"),
) -> None:
    """Fetch every per-student resource; persist to the store unless --no-save."""
    from .utils import console

    client = _library_client(ctx, email, password, timeout)
    data = client.fetch_all(include_history=history, include_stats=stats)

    if save:
        store.save_resource("student/all", data, source="fetch_all")
        for attr, name in RESOURCE_FILES.items():
            store.save_resource(name, getattr(data, attr), source="fetch_all")

    table = Table(title="fetch-all", header_style="bold magenta")
    table.add_column("Resource")
    table.add_column("Result")
    table.add_row("profile", "ok" if data.profile else "--")
    table.add_row("diploma", ("empty" if data.diploma.empty else "ok") if data.diploma else "--")
    for attr in ("element_grades", "module_grades", "semester_results", "year_results",
                 "absences", "absence_summary", "sanctions", "courses", "stats", "documents"):
        table.add_row(attr, str(len(getattr(data, attr))))
    console.print(table)
    if save:
        console.print(f"Saved to {store.state_dir()}")
    for name, err in data.errors.items():
        console.print(f"[red]{name}: {err}[/red]")


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

    out_dir = Path(out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    store.save_resource("all", data, source="export", directory=out_dir)
    for attr, name in RESOURCE_FILES.items():
        store.save_resource(name.split("/")[-1], getattr(data, attr),
                            source="export", directory=out_dir)

    if with_documents:
        docs_dir = out_dir / "documents"
        docs_dir.mkdir(exist_ok=True)
        for doc in data.documents:
            try:
                (docs_dir / doc.filename).write_bytes(client.download(doc))
                log("INFO", f"downloaded {doc.filename}")
            except Exception as exc:  # noqa: BLE001 — one bad PDF must not kill the export
                log("WARNING", f"download {doc.filename} failed: {exc}")

    console.print(f"Exported to {out_dir}")
    for name, err in data.errors.items():
        console.print(f"[red]{name}: {err}[/red]")


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
    from .utils import console

    client = _library_client(ctx, email, password, timeout, min_interval=min_interval)
    merged = {(m.code_mod, m.niveau, m.semestre, m.filiere): m for m in load_catalog_modules()}
    progress = {"combos": 0, "errors": 0}

    def on_combo(n, f, s, fresh, err):
        progress["combos"] += 1
        if err is not None:
            progress["errors"] += 1
            log("WARNING", f"catalog combo ({n}, {f}, {s}) failed: {err}")
            return
        if fresh:
            for m in fresh:
                merged[(m.code_mod, m.niveau, m.semestre, m.filiere)] = m
            store.save_resource(CATALOG_RESOURCE, list(merged.values()), source=CATALOG_PATH)
            log("INFO", f"({n}, {f}, {s}) +{len(fresh)} modules (total {len(merged)})")

    crawl_catalog(client, niveaux=_split_csv(niveaux), filieres=_split_csv(filieres),
                  on_combo=on_combo)
    filiere_models = client.filieres()
    store.save_resource("catalog/filieres", filiere_models, source=FILIERES_PATH)

    mismatches = reconcile([to_module_def(m) for m in merged.values()],
                           list(PRESET_2A_S3) + list(PRESET_2A_S4))
    for msg in mismatches:
        log("WARNING", f"catalog≠presets: {msg}")

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


if __name__ == "__main__":
    app()
