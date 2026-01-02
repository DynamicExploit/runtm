"""Logs command - view deployment logs."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from runtm_shared.errors import RuntmError

from ..api_client import APIClient
from ..config import get_token

console = Console()


def logs_command(
    deployment_id: str = typer.Argument(
        ...,
        help="Deployment ID (e.g., dep_abc123)",
    ),
    log_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Log type filter: build, deploy, runtime",
    ),
    lines: int = typer.Option(
        20,
        "--lines",
        "-n",
        help="Number of runtime log lines to include (default: 20)",
    ),
    search: str | None = typer.Option(
        None,
        "--search",
        "-s",
        help="Filter logs containing this text (case-insensitive)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output logs as JSON (useful for AI agents)",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output raw logs (pipe-friendly, works with grep)",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow logs in real-time (coming soon)",
    ),
) -> None:
    """View deployment logs.

    By default shows build, deploy, and recent runtime logs.
    Use --type to filter to a specific log type.

    Search supports:
    - Single term: --search "error"
    - Multiple terms (OR): --search "error,warning,failed"
    - Regex patterns: --search "HTTP.*[45]\\d\\d"

    Examples:
        runtm logs dep_abc123                           # All logs + runtime tail
        runtm logs dep_abc123 --type runtime            # Only runtime logs
        runtm logs dep_abc123 --lines 50                # More runtime lines
        runtm logs dep_abc123 --search "error"          # Filter by text
        runtm logs dep_abc123 --search "error,warning"  # Multiple keywords (OR)
        runtm logs dep_abc123 --json                    # JSON for AI agents
        runtm logs dep_abc123 --raw | grep "error"      # Pipe to grep
    """
    import json as json_lib

    # Check auth
    token = get_token()
    if not token:
        if json_output:
            print(json_lib.dumps({"error": "Not authenticated", "hint": "Run runtm login"}))
        else:
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
        raise typer.Exit(1)

    if follow and not json_output:
        console.print(
            "[yellow]⚠[/yellow] Real-time log following coming soon. Showing current logs."
        )
        console.print()

    # Get logs
    client = APIClient()

    try:
        response = client.get_logs(deployment_id, log_type, lines=lines, search=search)
    except RuntmError as e:
        if json_output:
            print(json_lib.dumps({"error": e.message, "hint": e.recovery_hint}))
        else:
            console.print(f"[red]✗[/red] {e.message}")
            if e.recovery_hint:
                console.print(f"    {e.recovery_hint}")
        raise typer.Exit(1)

    # JSON output mode
    if json_output:
        output = {
            "deployment_id": deployment_id,
            "source": response.source,
            "logs": [
                {
                    "type": entry.log_type,
                    "content": entry.content,
                    "timestamp": entry.created_at.isoformat(),
                }
                for entry in response.logs
            ],
        }
        if response.instructions:
            output["instructions"] = response.instructions
        print(json_lib.dumps(output, indent=2))
        return

    # Raw output mode (pipe-friendly, works with grep)
    if raw:
        for entry in response.logs:
            # Prefix each line with log type for filtering
            prefix = f"[{entry.log_type.upper()}]"
            for line in entry.content.split("\n"):
                print(f"{prefix} {line}")
        return

    if not response.logs and not response.instructions:
        console.print("No logs available yet.")
        console.print()
        console.print("If the deployment is still in progress, try again in a moment.")
        return

    # Show instructions for runtime logs (only if no logs at all)
    if response.instructions and not response.logs:
        console.print(f"[dim]Source: {response.source}[/dim]")
        console.print()
        console.print(response.instructions)
        return

    # Display logs
    for entry in response.logs:
        title = f"{entry.log_type.upper()} - {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        panel = Panel(
            entry.content,
            title=title,
            title_align="left",
            border_style="dim",
        )
        console.print(panel)
        console.print()
