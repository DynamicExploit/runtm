"""List command - shows all deployments."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from runtm_cli.api_client import APIClient
from runtm_cli.config import get_token
from runtm_shared.errors import RuntmError

console = Console()


def list_command(
    state: str | None = None,
    limit: int = 50,
) -> None:
    """List all deployments.

    Args:
        state: Filter by state (optional)
        limit: Maximum number of results
    """
    # Check auth upfront (consistent with deploy command)
    token = get_token()
    if not token:
        console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
        console.print()
        console.print("Or set RUNTM_API_KEY environment variable.")
        raise typer.Exit(1)

    client = APIClient()

    try:
        result = client.list_deployments(state=state, limit=limit)
    except RuntmError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.recovery_hint:
            console.print(f"[dim]Hint: {e.recovery_hint}[/dim]")
        raise SystemExit(1)

    if not result.deployments:
        if state:
            console.print(f"[dim]No deployments found with state '{state}'.[/dim]")
        else:
            console.print("[dim]No deployments found. Run 'runtm deploy' to create one.[/dim]")
        return

    # Create table
    table = Table(title=f"Deployments ({result.total} total)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("State", no_wrap=True)
    table.add_column("URL", style="dim")
    table.add_column("Created", style="dim", no_wrap=True)

    for dep in result.deployments:
        # Color state
        state_str = dep.state
        if dep.state == "ready":
            state_str = "[green]ready[/green]"
        elif dep.state == "failed":
            state_str = "[red]failed[/red]"
        elif dep.state == "destroyed":
            state_str = "[dim]destroyed[/dim]"
        elif dep.state in ("queued", "building", "deploying"):
            state_str = f"[yellow]{dep.state}[/yellow]"

        # Format URL
        url = dep.url or "-"

        # Format date
        created = dep.created_at.strftime("%Y-%m-%d %H:%M") if dep.created_at else "-"

        table.add_row(dep.deployment_id, dep.name, state_str, url, created)

    console.print()
    console.print(table)
    console.print()
