"""Destroy command - removes a deployment."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from runtm_cli.api_client import APIClient
from runtm_cli.config import get_token
from runtm_shared.errors import DeploymentNotFoundError, RuntmError

console = Console()


def destroy_command(
    deployment_id: str,
    force: bool = False,
) -> None:
    """Destroy a deployment.

    Args:
        deployment_id: Deployment ID to destroy
        force: Skip confirmation prompt
    """
    from runtm_cli.telemetry import command_span, emit_destroy_completed

    with command_span("destroy"):
        # Check auth upfront (consistent with deploy command)
        token = get_token()
        if not token:
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
            console.print()
            console.print("Or set RUNTM_API_KEY environment variable.")
            raise typer.Exit(1)

        client = APIClient()

        # First, get deployment info to show what will be destroyed
        try:
            deployment = client.get_deployment(deployment_id)
        except DeploymentNotFoundError:
            console.print(
                Panel(
                    f"[red]Deployment not found:[/red] {deployment_id}",
                    title="Error",
                    border_style="red",
                )
            )
            raise SystemExit(1)
        except RuntmError as e:
            console.print(
                Panel(
                    f"[red]{e.message}[/red]",
                    title="Error",
                    border_style="red",
                )
            )
            raise SystemExit(1)

        # Show deployment info
        console.print()
        console.print(f"[bold]Deployment:[/bold] {deployment.deployment_id}")
        console.print(f"[bold]Name:[/bold] {deployment.name}")
        console.print(f"[bold]State:[/bold] {deployment.state}")
        if deployment.url:
            console.print(f"[bold]URL:[/bold] {deployment.url}")
        console.print()

        # Confirm destruction
        if not force:
            console.print(
                "[yellow]⚠️  This will permanently destroy the deployment and stop all running resources.[/yellow]"
            )
            confirm = console.input("[bold]Type the deployment ID to confirm:[/bold] ")
            if confirm != deployment_id:
                console.print("[red]Aborted.[/red] Deployment ID did not match.")
                raise SystemExit(1)

        # Destroy the deployment
        console.print()
        with console.status("[bold blue]Destroying deployment...[/bold blue]"):
            try:
                result = client.destroy_deployment(deployment_id)
            except RuntmError as e:
                console.print(
                    Panel(
                        f"[red]{e.message}[/red]",
                        title="Error",
                        border_style="red",
                    )
                )
                if e.recovery_hint:
                    console.print(f"[dim]Hint: {e.recovery_hint}[/dim]")
                raise SystemExit(1)

        # Emit destroy completed event
        emit_destroy_completed()

        # Success
        console.print(
            Panel(
                f"[green]✓ {result.message}[/green]",
                title="Destroyed",
                border_style="green",
            )
        )
