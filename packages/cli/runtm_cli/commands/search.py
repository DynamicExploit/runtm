"""Search command - search deployments by discovery metadata."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from runtm_cli.api_client import APIClient
from runtm_cli.config import get_token
from runtm_shared.errors import RuntmError

console = Console()


def search_command(
    query: str,
    state: str | None = None,
    template: str | None = None,
    limit: int = 20,
    json_output: bool = False,
) -> None:
    """Search deployments by description, tags, and capabilities.

    Searches across runtm.discovery.yaml metadata including:
    - description
    - summary
    - tags
    - capabilities
    - use_cases

    Examples:
        runtm search "stripe webhook"
        runtm search "payment" --template backend-service
        runtm search "dashboard" --state ready
    """
    # Check auth
    token = get_token()
    if not token:
        console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
        raise typer.Exit(1)

    client = APIClient()

    try:
        results = client.search_deployments(
            query=query,
            state=state,
            template=template,
            limit=limit,
        )
    except RuntmError as e:
        console.print(f"[red]✗[/red] {e.message}")
        if e.recovery_hint:
            console.print(f"    {e.recovery_hint}")
        raise typer.Exit(1)

    if json_output:
        import json

        output = {
            "query": query,
            "total": results.total,
            "results": [
                {
                    "deployment_id": r.deployment_id,
                    "name": r.name,
                    "state": r.state,
                    "url": r.url,
                    "template": r.template,
                    "summary": r.summary,
                    "tags": r.tags,
                    "match_score": r.match_score,
                }
                for r in results.results
            ],
        }
        console.print(json.dumps(output, indent=2))
        return

    if not results.results:
        console.print()
        console.print(f'[yellow]No apps found matching "{query}"[/yellow]')
        console.print()
        console.print("[dim]Tips:[/dim]")
        console.print("  • Try broader search terms")
        console.print("  • Add discovery metadata with runtm.discovery.yaml")
        console.print("  • Check that apps have been deployed with discovery files")
        return

    console.print()
    console.print(f'[bold]Found {results.total} app(s) matching "{query}":[/bold]')
    console.print()

    for result in results.results:
        _print_search_result(result)


def _print_search_result(result) -> None:
    """Print a single search result with rich formatting."""
    # Build the header with name and template
    header = Text()
    header.append(result.name, style="bold cyan")
    if result.template:
        header.append(f" ({result.template})", style="dim")

    # Build status indicator
    state_colors = {
        "ready": "green",
        "building": "yellow",
        "deploying": "yellow",
        "queued": "blue",
        "failed": "red",
        "destroyed": "dim",
    }
    state_color = state_colors.get(result.state, "white")
    state_text = f"[{state_color}]●[/{state_color}] {result.state}"

    # Build content
    content_lines = []

    # Summary (most important)
    if result.summary:
        content_lines.append(result.summary)
    elif result.description:
        # Truncate description if too long
        desc = result.description.strip()
        if len(desc) > 100:
            desc = desc[:97] + "..."
        content_lines.append(desc)

    # Tags
    if result.tags:
        tags_text = " ".join(f"[dim]#{tag}[/dim]" for tag in result.tags[:5])
        if len(result.tags) > 5:
            tags_text += f" [dim]+{len(result.tags) - 5} more[/dim]"
        content_lines.append(tags_text)

    # URL
    if result.url:
        content_lines.append(f"[link={result.url}]{result.url}[/link]")

    # Create panel
    panel_content = "\n".join(content_lines) if content_lines else "[dim]No description[/dim]"

    panel = Panel(
        panel_content,
        title=header,
        subtitle=state_text,
        title_align="left",
        subtitle_align="right",
        border_style="dim",
        padding=(0, 1),
    )

    console.print(panel)
