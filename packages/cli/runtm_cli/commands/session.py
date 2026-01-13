"""Session commands for managing sandbox sessions.

Commands:
- runtm session start: Start a new sandbox session
- runtm session list: List all sandbox sessions
- runtm session attach: Attach to an existing session
- runtm session stop: Stop a session (preserves workspace)
- runtm session destroy: Destroy a session and delete workspace
- runtm session deploy: Deploy from a sandbox to a live URL
"""

from __future__ import annotations

import uuid
from pathlib import Path

import typer
from rich.console import Console

from runtm_shared.types import AgentType, SandboxConfig, SandboxState

console = Console()
session_app = typer.Typer(name="session", help="Manage sandbox sessions.")

# Sandbox package is optional - check availability
SANDBOX_AVAILABLE = False
try:
    from runtm_sandbox.deps import ensure_sandbox_deps
    from runtm_sandbox.providers.local import LocalSandboxProvider

    SANDBOX_AVAILABLE = True
except ImportError:
    pass


def _require_sandbox() -> None:
    """Check if sandbox package is available, exit with helpful message if not."""
    if not SANDBOX_AVAILABLE:
        console.print("[red]Sandbox package not installed.[/red]")
        console.print()
        console.print("Install with:")
        console.print("  [cyan]pip install runtm[sandbox][/cyan]")
        console.print()
        console.print("Or for development:")
        console.print("  [cyan]pip install -e packages/sandbox[/cyan]")
        raise typer.Exit(1)


@session_app.command("start")
def start(
    local: bool = typer.Option(True, "--local/--cloud", help="Local or cloud sandbox"),
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Template: backend-service, web-app, static-site",
    ),
    agent: str = typer.Option(
        "claude-code",
        "--agent",
        "-a",
        help="Agent: claude-code, codex, gemini",
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Session name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve dependency installation"),
) -> None:
    """Start a new sandbox session.

    Creates an isolated environment where an AI coding agent can build software.
    Uses OS-level isolation (bubblewrap/seatbelt) for fast startup (<100ms).

    Examples:
        runtm session start                    # Start with defaults
        runtm session start --template web-app # Start with template
        runtm session start --agent codex      # Use different agent
    """
    _require_sandbox()

    # 1. Ensure dependencies are installed (lazy install on first run)
    if not ensure_sandbox_deps(auto_approve=yes):  # type: ignore[name-defined]
        console.print("[red]Cannot start sandbox without dependencies.[/red]")
        console.print()
        console.print("Run with [cyan]--yes[/cyan] to auto-install, or install manually:")
        console.print("  • Bun: curl -fsSL https://bun.sh/install | bash")
        console.print("  • sandbox-runtime: bun install -g @anthropic-ai/sandbox-runtime")
        console.print("  • Claude Code: curl -fsSL https://claude.ai/install.sh | bash")
        raise typer.Exit(1)

    # 2. Validate agent type
    try:
        agent_type = AgentType(agent)
    except ValueError:
        console.print(f"[red]Invalid agent: {agent}[/red]")
        console.print("Valid agents: claude-code, codex, gemini, custom")
        raise typer.Exit(1)

    # 3. Create sandbox
    sandbox_id = f"sbx_{uuid.uuid4().hex[:12]}"
    config = SandboxConfig(
        agent=agent_type,
        template=template,
    )

    provider = LocalSandboxProvider()  # type: ignore[name-defined]

    console.print(f"\n[dim]Creating sandbox {sandbox_id}...[/dim]")
    sandbox = provider.create(sandbox_id, config)

    console.print(f"[green]✓[/green] Sandbox ready: {sandbox.workspace_path}")
    console.print()
    console.print("[bold]You are now in an isolated sandbox.[/bold]")
    console.print("  • Filesystem writes restricted to workspace")
    console.print("  • Network filtered to allowed domains")
    console.print("  • Run [cyan]claude[/cyan] to start coding with Claude Code")
    console.print("  • Run [cyan]exit[/cyan] to leave sandbox")
    console.print()

    # 4. Attach to sandbox (drops user into isolated shell)
    exit_code = provider.attach(sandbox_id)

    # 5. User exited - show next steps
    if exit_code == 0:
        console.print(f"\n[dim]Sandbox {sandbox_id} still running. Reattach with:[/dim]")
        console.print(f"  runtm session attach {sandbox_id}")
    else:
        console.print(f"\n[yellow]Sandbox exited with code {exit_code}[/yellow]")


@session_app.command("list")
def list_sessions() -> None:
    """List all sandbox sessions.

    Shows all sandboxes and their current state (running, stopped, etc.).

    Example:
        runtm session list
    """
    _require_sandbox()
    provider = LocalSandboxProvider()  # type: ignore[name-defined]
    sandboxes = provider.list_sandboxes()

    if not sandboxes:
        console.print("[dim]No sandboxes found.[/dim]")
        console.print("Start one with: [cyan]runtm session start[/cyan]")
        return

    console.print("\n[bold]Sandboxes[/bold]\n")
    for sandbox in sandboxes:
        state_color = {
            SandboxState.RUNNING: "green",
            SandboxState.STOPPED: "yellow",
            SandboxState.CREATING: "blue",
            SandboxState.DESTROYED: "red",
        }.get(sandbox.state, "dim")

        console.print(f"  {sandbox.id}  [{state_color}]{sandbox.state.value}[/{state_color}]")
        console.print(f"    [dim]Agent: {sandbox.config.agent.value}[/dim]")
        console.print(f"    [dim]Path: {sandbox.workspace_path}[/dim]")
        console.print()


@session_app.command("attach")
def attach(
    sandbox_id: str = typer.Argument(..., help="Sandbox ID to attach to"),
) -> None:
    """Attach to an existing sandbox.

    Reconnects to a running or stopped sandbox session.

    Example:
        runtm session attach sbx_abc123
    """
    _require_sandbox()
    provider = LocalSandboxProvider()  # type: ignore[name-defined]

    sandbox = provider.state_store.load(sandbox_id)
    if sandbox is None:
        console.print(f"[red]Sandbox not found: {sandbox_id}[/red]")
        console.print("Run [cyan]runtm session list[/cyan] to see available sandboxes.")
        raise typer.Exit(1)

    console.print(f"[dim]Attaching to {sandbox_id}...[/dim]")
    provider.attach(sandbox_id)


@session_app.command("stop")
def stop(
    sandbox_id: str = typer.Argument(..., help="Sandbox ID to stop"),
) -> None:
    """Stop a sandbox (preserves workspace).

    Marks the sandbox as stopped. The workspace and files are preserved.
    You can reattach later with 'runtm session attach'.

    Example:
        runtm session stop sbx_abc123
    """
    _require_sandbox()
    provider = LocalSandboxProvider()  # type: ignore[name-defined]
    provider.stop(sandbox_id)
    console.print(f"[green]✓[/green] Sandbox {sandbox_id} stopped")
    console.print(
        f"[dim]Workspace preserved. Reattach with: runtm session attach {sandbox_id}[/dim]"
    )


@session_app.command("destroy")
def destroy(
    sandbox_id: str = typer.Argument(..., help="Sandbox ID to destroy"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Destroy a sandbox and delete workspace.

    Permanently deletes the sandbox and all files in its workspace.
    This action cannot be undone.

    Example:
        runtm session destroy sbx_abc123
        runtm session destroy sbx_abc123 --force  # Skip confirmation
    """
    _require_sandbox()

    if not force:
        if not typer.confirm(f"Destroy sandbox {sandbox_id} and delete all files?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    provider = LocalSandboxProvider()  # type: ignore[name-defined]
    provider.destroy(sandbox_id)
    console.print(f"[green]✓[/green] Sandbox {sandbox_id} destroyed")


@session_app.command("deploy")
def deploy_from_sandbox(
    sandbox_id: str = typer.Argument(None, help="Sandbox ID (default: most recent)"),
    path: str = typer.Option(".", "--path", "-p", help="Path inside sandbox to deploy"),
) -> None:
    """Deploy what's in the sandbox to a live URL.

    Deploys the code from a sandbox workspace to a production URL.
    Uses the existing runtm deploy infrastructure (Fly.io).

    Example:
        runtm session deploy                    # Deploy most recent sandbox
        runtm session deploy sbx_abc123         # Deploy specific sandbox
        runtm session deploy --path ./backend   # Deploy subdirectory
    """
    _require_sandbox()
    provider = LocalSandboxProvider()  # type: ignore[name-defined]

    # Get sandbox
    if sandbox_id is None:
        sandboxes = provider.list_sandboxes()
        if not sandboxes:
            console.print("[red]No sandboxes found.[/red]")
            raise typer.Exit(1)
        sandbox = sandboxes[-1]  # Most recent
        sandbox_id = sandbox.id
        console.print(f"[dim]Using most recent sandbox: {sandbox_id}[/dim]")
    else:
        sandbox = provider.state_store.load(sandbox_id)
        if sandbox is None:
            console.print(f"[red]Sandbox not found: {sandbox_id}[/red]")
            raise typer.Exit(1)

    # Deploy from workspace
    workspace = Path(sandbox.workspace_path) / path
    if not workspace.exists():
        console.print(f"[red]Path not found: {workspace}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Deploying from {workspace}...[/dim]")

    # Use existing deploy logic
    from runtm_cli.commands.deploy import deploy_command

    deploy_command(path=workspace)
