from __future__ import annotations

import os

import typer
try:
    import keyring
except Exception:
    keyring = None

from ..calculator import list_modules, run_calculator
from ..utils import AppContext
from ..watcher import check_once, watch_loop
from ..watcher import _snapshot_path, _load_snapshot, _render_consolidated_snapshot
from ..utils import resolve_credentials


app = typer.Typer(help="S4 commands: calc, list, watch")


@app.command("list")
def list_cmd(
    table: bool = typer.Option(False, help="Print a single consolidated table for all modules"),
    show: str | None = typer.Option(None, help="Show only a specific module code (e.g. API41)"),
) -> None:
    """List S4 modules and elements."""
    list_modules("S4", single_table=table, show_module=show)


@app.command("table")
def table_cmd(
    ctx: typer.Context,
    state_file: str | None = typer.Option(None, help="Snapshot file path"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
) -> None:
    """Fetch SchoolApp and show consolidated table for S4 elements (API4*)."""
    app_ctx: AppContext = ctx.obj
    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)
    if password:
        resolved_password = password
    if not resolved_email or not resolved_password:
        raise typer.BadParameter("Missing credentials: provide --email/--password, env, config, or keyring")

    code = check_once(
        email=resolved_email,
        password=resolved_password,
        timeout=timeout,
        semester="S4",
        state_file=state_file,
        notify_email=False,
        config=app_ctx.config,
    )

    path = _snapshot_path("S4", state_file)
    snap = _load_snapshot(path)
    if not snap:
        raise typer.Exit(code=1)
    _render_consolidated_snapshot(snap.headers, snap.rows, "S4")


@app.command("details")
def details_cmd(
    ctx: typer.Context,
    element: str = typer.Argument(..., help="Element code (e.g., API411)"),
    eval: str = typer.Option("all", help="Which stat popup to fetch: all|cc|ex|tp|rat|moy"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
) -> None:
    """Fetch and display detailed grade breakdown for a specific element."""
    from ..watcher import fetch_element_details
    from ..utils import console
    from rich.table import Table
    from rich.panel import Panel

    if not element:
        raise typer.BadParameter("element is required")

    app_ctx: AppContext = ctx.obj
    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)
    if password:
        resolved_password = password
    if not resolved_email or not resolved_password:
        raise typer.BadParameter("Missing credentials: provide --email/--password, env, config, or keyring")

    details = fetch_element_details(
        email=resolved_email,
        password=resolved_password,
        timeout=timeout,
        element_code=element.upper(),
        eval_kind=eval,
    )

    if not details:
        console.print(f"[yellow]No detailed information found for {element}[/yellow]")
        raise typer.Exit(code=1)

    console.print(Panel.fit(f"Element Details: {element.upper()}", border_style="cyan"))
    
    if details.get("data"):
        console.print(f"[bold]Main data:[/bold] {', '.join(details['data'])}")

    if details.get("stats"):
        for block in details["stats"]:
            title = block.get("title", "Statistiques")
            st = Table(title=title, show_header=False)
            st.add_column("Metric")
            st.add_column("Value", justify="right")
            rows = block.get("rows", [])
            for row in rows:
                if len(row) >= 2:
                    st.add_row(row[0], row[1])
            console.print(st)
    
    if details.get("breakdown"):
        for i, breakdown in enumerate(details["breakdown"]):
            if "table" in breakdown:
                table = Table(title=f"Breakdown {i+1}", header_style="bold magenta")
                rows = breakdown["table"]
                if rows:
                    # Add columns based on first row
                    for col in rows[0]:
                        table.add_column(col or " ")
                    # Add data rows
                    for row in rows[1:]:
                        table.add_row(*row)
                    console.print(table)


@app.command("calc")
def calc_cmd(
    marks_file: str | None = typer.Option(None, help="JSON marks file"),
    snapshot_file: str | None = typer.Option(None, help="Snapshot JSON from fetched website data"),
    ask_missing: bool = typer.Option(False, help="Interactively ask for missing ordinary marks (CC/EX/TP)"),
    ask_rat: bool = typer.Option(False, help="Interactively ask for missing RATTRAPAGE notes"),
) -> None:
    """Run S4 calculator."""
    run_calculator(
        "S4",
        marks_file=marks_file,
        snapshot_file=snapshot_file,
        ask_missing=ask_missing,
        ask_rattrapage=ask_rat,
    )


@app.command("watch")
def watch_cmd(
    ctx: typer.Context,
    interval: int = typer.Option(300, min=30, help="Polling interval in seconds (slows to 30 min between 04:00-06:00)"),
    timeout: int = typer.Option(20, min=5, help="HTTP timeout in seconds"),
    email: str | None = typer.Option(None, help="SchoolApp email"),
    password: str | None = typer.Option(None, help="SchoolApp password"),
    state_file: str | None = typer.Option(None, help="Snapshot file path"),
    notify_email: bool = typer.Option(False, help="Send email on detected changes"),
    notify_telegram: bool = typer.Option(False, help="Send Telegram message on detected changes"),
    once: bool = typer.Option(False, help="Run one check and exit"),
) -> None:
    """Watch S4 marks for changes."""
    app_ctx: AppContext = ctx.obj
    cfg = app_ctx.config.get("schoolapp", {}) if isinstance(app_ctx.config, dict) else {}

    resolved_email, resolved_password = resolve_credentials(email, app_ctx.config)

    # allow CLI-provided password to override
    if password:
        resolved_password = password

    if not resolved_email or not resolved_password:
        raise typer.BadParameter("Missing credentials: provide --email/--password, env vars, config file, or store password in keyring")

    if once:
        code = check_once(
            email=resolved_email,
            password=resolved_password,
            timeout=timeout,
            semester="S4",
            state_file=state_file,
            notify_email=notify_email,
            notify_telegram=notify_telegram,
            config=app_ctx.config,
        )
        raise typer.Exit(code=code)

    code = watch_loop(
        email=resolved_email,
        password=resolved_password,
        timeout=timeout,
        semester="S4",
        state_file=state_file,
        interval=interval,
        notify_email=notify_email,
        notify_telegram=notify_telegram,
        config=app_ctx.config,
    )
    raise typer.Exit(code=code)
