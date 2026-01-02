"""Status command - check deployment status."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from runtm_shared.errors import RuntmError

from ..api_client import APIClient
from ..config import get_token

console = Console()


def status_command(
    deployment_id: str = typer.Argument(
        ...,
        help="Deployment ID (e.g., dep_abc123)",
    ),
) -> None:
    """Check status of a deployment.

    Shows current state, URL (if ready), and any error messages.
    """
    # Check auth
    token = get_token()
    if not token:
        console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
        raise typer.Exit(1)

    # Get status
    client = APIClient()

    try:
        deployment = client.get_deployment(deployment_id)
    except RuntmError as e:
        console.print(f"[red]✗[/red] {e.message}")
        if e.recovery_hint:
            console.print(f"    {e.recovery_hint}")
        raise typer.Exit(1)

    # Display status
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("ID", deployment.deployment_id)
    table.add_row("Name", deployment.name)

    # Color-code state
    state = deployment.state
    if state == "ready":
        state_display = f"[green]{state}[/green]"
    elif state == "failed":
        state_display = f"[red]{state}[/red]"
    elif state in ("building", "deploying"):
        state_display = f"[yellow]{state}[/yellow]"
    else:
        state_display = state

    table.add_row("State", state_display)

    if deployment.url:
        table.add_row("URL", deployment.url)

    if deployment.error_message:
        table.add_row("Error", f"[red]{deployment.error_message}[/red]")

    table.add_row("Created", deployment.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Updated", deployment.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

    console.print(table)

    # Show next steps
    if deployment.state == "ready" and deployment.url:
        console.print()
        console.print("Test your deployment:")
        console.print(f"  curl {deployment.url}/health")
    elif deployment.state == "failed":
        console.print()
        console.print("View logs:")
        console.print(f"  runtm logs {deployment_id}")
    elif deployment.state in ("queued", "building", "deploying"):
        console.print()
        console.print("Deployment in progress. Check again in a moment.")
