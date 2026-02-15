from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from . import __version__
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


if __name__ == "__main__":
    app()
