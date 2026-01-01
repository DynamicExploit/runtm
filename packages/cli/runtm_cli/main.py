"""Runtm CLI - deploy AI-generated code to live URLs."""

from __future__ import annotations

# NOTE: We intentionally do NOT load .env from the monorepo root.
# The CLI runs in user projects and should only use:
# - User's system environment variables
# - User's project .env.local (via secrets commands)
# - ~/.runtm/config.yaml for CLI config (API URL, token)

from typing import Optional

import typer
from rich.console import Console

from runtm_cli import __version__
from runtm_cli.commands import (
    approve_command,
    deploy_command,
    destroy_command,
    domain_add_command,
    domain_remove_command,
    domain_status_command,
    fix_command,
    init_command,
    list_command,
    logs_command,
    run_command,
    search_command,
    secrets_get_command,
    secrets_list_command,
    secrets_set_command,
    secrets_unset_command,
    status_command,
    validate_command,
)
from runtm_cli.commands.admin import admin_app
from runtm_cli.config import get_config, get_token, set_token, clear_token

console = Console()


def _telemetry_callback(ctx: typer.Context) -> None:
    """Typer callback to initialize telemetry for each command.

    This runs before any command and ensures telemetry is set up.
    """
    # Import here to avoid circular imports and ensure lazy loading
    from runtm_cli.telemetry import get_telemetry

    # Initialize telemetry (this handles first_run, upgrade detection)
    get_telemetry()


# Create main app with callback
app = typer.Typer(
    name="runtm",
    help="Deploy AI-generated code to live URLs in minutes.",
    no_args_is_help=True,
    callback=_telemetry_callback,
)


@app.command("init")
def init(
    template: Optional[str] = typer.Argument(None, help="Template type: backend-service, static-site, web-app"),
    path: str = typer.Option(".", "--path", "-p"),
    name: str = typer.Option(None, "--name", "-n"),
) -> None:
    """Initialize a new project from template."""
    from pathlib import Path

    init_command(
        template=template,
        path=Path(path),
        name=name,
    )


@app.command("deploy")
def deploy(
    path: str = typer.Argument(".", help="Path to project"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout: int = typer.Option(300, "--timeout", "-t"),
    new: bool = typer.Option(False, "--new", help="DANGEROUS: Create new Fly app instead of redeploying. Loses custom domains and secrets!"),
    tier: str = typer.Option(None, "--tier", help="Machine tier: starter, standard, performance"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-fix lockfile issues without prompting"),
    config_only: bool = typer.Option(False, "--config-only", help="Skip Docker build - reuse previous image (for env/tier changes only)"),
) -> None:
    """Deploy a project to a live URL.
    
    Blocks if lockfile is missing or out of sync. Use --yes to auto-fix.
    
    Use --config-only to skip the Docker build and reuse the previous image.
    This is useful for changing environment variables or machine tier without
    rebuilding. Requires unchanged source code.
    """
    from pathlib import Path

    # SAFETY: Require explicit confirmation for --new flag
    if new:
        console.print()
        console.print("[red bold]⚠ WARNING: --new creates a NEW Fly app![/red bold]")
        console.print()
        console.print("This will:")
        console.print("  • Create a brand new deployment URL")
        console.print("  • NOT transfer custom domains (e.g., app.runtm.com)")
        console.print("  • NOT transfer environment secrets")
        console.print()
        console.print("Use this ONLY if you intentionally want a separate deployment.")
        console.print()
        if not typer.confirm("Are you sure you want to create a NEW deployment?", default=False):
            console.print("[dim]Cancelled. Use 'runtm deploy' without --new to update existing.[/dim]")
            raise typer.Exit(0)

    deploy_command(
        path=Path(path),
        wait=wait,
        timeout=timeout,
        new=new,
        tier=tier,
        yes=yes,
        config_only=config_only,
    )


@app.command("validate")
def validate(
    path: str = typer.Argument(".", help="Path to project"),
) -> None:
    """Validate project before deployment."""
    from pathlib import Path

    validate_command(path=Path(path))


@app.command("approve")
def approve(
    path: str = typer.Argument(".", help="Path to project"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be applied without making changes"),
) -> None:
    """Apply agent-proposed changes from runtm.requests.yaml.

    Merges requested env vars, connections, and egress allowlist into
    runtm.yaml. After approval, the requests file is deleted.

    In v1, this is informational - deploys work without approval.

    Examples:
        runtm approve              # Apply pending requests
        runtm approve --dry-run    # Preview without applying
    """
    from pathlib import Path

    approve_command(path=Path(path), dry_run=dry_run)


@app.command("fix")
def fix(
    path: str = typer.Argument(".", help="Path to project"),
) -> None:
    """Fix common project issues (lockfiles, etc.).
    
    Automatically repairs:
    - Missing or drifted lockfiles
    
    Examples:
        runtm fix              # Fix current directory
        runtm fix ./my-project # Fix specific project
    """
    from pathlib import Path

    fix_command(path=Path(path))


@app.command("run")
def run(
    path: str = typer.Argument(".", help="Path to project"),
    no_install: bool = typer.Option(False, "--no-install", help="Skip dependency installation"),
    no_autofix: bool = typer.Option(False, "--no-autofix", help="Don't auto-fix lockfile drift"),
) -> None:
    """Run project locally (auto-detects runtime from runtm.yaml).
    
    Starts the development server with the correct port and command
    based on your template's runtime (python, node, or fullstack).
    
    Uses Bun if available (3x faster), falls back to npm.
    
    Automatically fixes lockfile drift unless --no-autofix is passed.
    
    Examples:
        runtm run              # Run current directory
        runtm run ./my-project # Run specific project
        runtm run --no-install # Skip bun/npm/pip install
        runtm run --no-autofix # Don't auto-fix lockfile issues
    """
    from pathlib import Path

    run_command(path=Path(path), install=not no_install, no_autofix=no_autofix)


@app.command("status")
def status(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
) -> None:
    """Check status of a deployment."""
    status_command(deployment_id=deployment_id)


@app.command("logs")
def logs(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
    log_type: str = typer.Option(None, "--type", "-t", help="Log type: build, deploy, runtime"),
    lines: int = typer.Option(20, "--lines", "-n", help="Runtime log lines to include"),
    search: str = typer.Option(None, "--search", "-s", help="Filter: term, term1,term2 (OR), or regex"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON for AI agents"),
    raw: bool = typer.Option(False, "--raw", help="Raw output for piping to grep"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs (not implemented)"),
) -> None:
    """View deployment logs."""
    logs_command(
        deployment_id=deployment_id,
        log_type=log_type,
        lines=lines,
        search=search,
        json_output=json_output,
        raw=raw,
        follow=follow,
    )


@app.command("destroy")
def destroy(
    deployment_id: str = typer.Argument(..., help="Deployment ID to destroy"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Destroy a deployment and stop all running resources."""
    destroy_command(
        deployment_id=deployment_id,
        force=force,
    )


@app.command("list")
def list_deployments(
    state: str = typer.Option(None, "--state", "-s", help="Filter by state"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum results"),
) -> None:
    """List all deployments."""
    list_command(state=state, limit=limit)


@app.command("search")
def search_apps(
    query: str = typer.Argument(..., help="Search query (e.g., 'stripe webhook')"),
    state: str = typer.Option(None, "--state", "-s", help="Filter by state"),
    template: str = typer.Option(None, "--template", "-t", help="Filter by template type"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Search deployments by description, tags, and capabilities.

    Searches across runtm.discovery.yaml metadata to find apps.

    Examples:
        runtm search "stripe webhook"
        runtm search "payment" --template backend-service
        runtm search "dashboard" --state ready --json
    """
    search_command(
        query=query,
        state=state,
        template=template,
        limit=limit,
        json_output=json_output,
    )


# Domain subcommand group
domain_app = typer.Typer(
    name="domain",
    help="Manage custom domains for deployments.",
    no_args_is_help=True,
)
app.add_typer(domain_app, name="domain")


@domain_app.command("add")
def domain_add(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
    hostname: str = typer.Argument(..., help="Custom domain (e.g., api.example.com)"),
) -> None:
    """Add a custom domain to a deployment.

    Configures SSL certificate and shows required DNS records.

    Example:
        runtm domain add dep_abc123 api.example.com
    """
    domain_add_command(deployment_id=deployment_id, hostname=hostname)


@domain_app.command("status")
def domain_status(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
    hostname: str = typer.Argument(..., help="Custom domain to check"),
) -> None:
    """Check status of a custom domain.

    Shows certificate status and required DNS configuration.

    Example:
        runtm domain status dep_abc123 api.example.com
    """
    domain_status_command(deployment_id=deployment_id, hostname=hostname)


@domain_app.command("remove")
def domain_remove(
    deployment_id: str = typer.Argument(..., help="Deployment ID"),
    hostname: str = typer.Argument(..., help="Custom domain to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a custom domain from a deployment.

    Example:
        runtm domain remove dep_abc123 api.example.com
    """
    domain_remove_command(deployment_id=deployment_id, hostname=hostname, force=force)


# Secrets subcommand group
secrets_app = typer.Typer(
    name="secrets",
    help="Manage local environment secrets (.env.local).",
    no_args_is_help=True,
)
app.add_typer(secrets_app, name="secrets")


@secrets_app.command("set")
def secrets_set(
    key_value: str = typer.Argument(..., help="KEY=VALUE pair to set"),
    path: str = typer.Option(".", "--path", "-p", help="Path to project"),
) -> None:
    """Set a secret in .env.local.

    Secrets are stored locally and injected to the deployment provider
    at deploy time. Runtm never stores secret values.

    Examples:
        runtm secrets set DATABASE_URL=postgres://...
        runtm secrets set API_KEY=sk-xxx
    """
    from pathlib import Path

    secrets_set_command(key_value=key_value, path=Path(path))


@secrets_app.command("get")
def secrets_get(
    key: str = typer.Argument(..., help="Secret name to get"),
    path: str = typer.Option(".", "--path", "-p", help="Path to project"),
) -> None:
    """Get a secret value from .env.local.

    Prints the value to stdout (useful for scripting).

    Example:
        runtm secrets get DATABASE_URL
    """
    from pathlib import Path

    secrets_get_command(key=key, path=Path(path))


@secrets_app.command("list")
def secrets_list(
    path: str = typer.Option(".", "--path", "-p", help="Path to project"),
    show_values: bool = typer.Option(False, "--values", "-v", help="Show values (non-secrets only)"),
) -> None:
    """List all secrets and their status.

    Shows which env vars from env_schema are set, missing, or have defaults.

    Example:
        runtm secrets list
        runtm secrets list --values
    """
    from pathlib import Path

    secrets_list_command(path=Path(path), show_values=show_values)


@secrets_app.command("unset")
def secrets_unset(
    key: str = typer.Argument(..., help="Secret name to remove"),
    path: str = typer.Option(".", "--path", "-p", help="Path to project"),
) -> None:
    """Remove a secret from .env.local.

    Example:
        runtm secrets unset OLD_API_KEY
    """
    from pathlib import Path

    secrets_unset_command(key=key, path=Path(path))


@app.command("login")
def login(
    token: Optional[str] = typer.Option(
        None,
        "--token", "-t",
        help="API token (will prompt if not provided)",
    ),
    device: bool = typer.Option(
        False,
        "--device",
        help="Use browser-based device flow (hosted Runtm only)",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Replace existing token without prompting",
    ),
) -> None:
    """Authenticate with Runtm API.

    Two authentication methods:
    - Token: Paste an API token directly (default for self-hosted)
    - Device flow: Authenticate via browser (hosted Runtm only)

    Examples:
        runtm login                    # Prompt for token
        runtm login --token runtm_xxx  # Provide token directly
        runtm login --device           # Browser-based auth (hosted only)
    """
    import os
    from runtm_cli.telemetry import emit_login_started, emit_login_completed

    # Check if already logged in
    existing_token = get_token()
    if existing_token and not force:
        # Mask the token for display
        masked = existing_token[:16] + "..." + existing_token[-4:] if len(existing_token) > 24 else existing_token[:8] + "..."
        console.print()
        console.print(f"[yellow]⚠[/yellow]  You are already logged in with token: [dim]{masked}[/dim]")
        console.print()
        if not typer.confirm("Replace existing token?", default=False):
            console.print("[dim]Keeping existing token.[/dim]")
            raise typer.Exit(0)

    if device:
        # Device flow: only for hosted Runtm or explicitly configured
        config = get_config()
        api_url = config.get("api_url", "")
        device_auth_url = os.environ.get("RUNTM_DEVICE_AUTH_URL", "")

        # Check if device flow is available
        is_hosted = "api.runtm.dev" in api_url or "api.runtm.com" in api_url
        if not is_hosted and not device_auth_url:
            console.print("[red]Error:[/red] Device flow only available for hosted Runtm")
            console.print()
            console.print("For self-hosted instances, use --token instead:")
            console.print("  runtm login --token YOUR_TOKEN")
            console.print()
            console.print("Or set RUNTM_DEVICE_AUTH_URL to enable device flow:")
            console.print("  export RUNTM_DEVICE_AUTH_URL=https://your-auth-server/device")
            raise typer.Exit(1)

        # Device flow authentication
        emit_login_started(auth_method="device")
        console.print("[yellow]Device flow not yet implemented[/yellow]")
        console.print("Please use --token for now")
        raise typer.Exit(1)

        # TODO: Implement device flow
        # 1. POST to device_auth_url to get device_code and user_code
        # 2. Show user_code and verification URL
        # 3. Poll for token completion
        # 4. Save token
        # emit_login_completed(auth_method="device")
    else:
        # Token-based authentication
        if token is None:
            # Show helpful instructions for getting an API key
            console.print()
            console.print("  ┌─────────────────────────────────────────────────┐")
            console.print("  │  [bold]To authenticate with Runtm:[/bold]                    │")
            console.print("  │                                                 │")
            console.print("  │  1. Go to [cyan]https://app.runtm.com[/cyan]                 │")
            console.print("  │  2. Sign in or create an account                │")
            console.print("  │  3. Navigate to [bold]API Keys[/bold]                        │")
            console.print("  │  4. Create a new API key                        │")
            console.print("  │  5. Paste it below                              │")
            console.print("  └─────────────────────────────────────────────────┘")
            console.print()
            token = typer.prompt("  Enter your API key", hide_input=True)

        emit_login_started(auth_method="token")

        # Validate the token against Cloud Backend before saving
        console.print()
        console.print("[dim]Validating API key...[/dim]")

        from runtm_cli.api_client import verify_cloud_api_key
        from runtm_shared.errors import InvalidTokenError, RuntmError

        try:
            result = verify_cloud_api_key(token)
            console.print(f"[green]✓[/green] Key validated: [bold]{result.name}[/bold]")
            if result.expires_at:
                console.print(f"[dim]  Expires: {result.expires_at}[/dim]")
            console.print(f"[dim]  Scopes: {', '.join(result.scopes)}[/dim]")
        except InvalidTokenError as e:
            console.print(f"[red]✗[/red] Invalid API key: {e}")
            console.print()
            console.print("[dim]Please create a new key at https://app.runtm.com/api-keys[/dim]")
            raise typer.Exit(1)
        except RuntmError as e:
            console.print(f"[red]✗[/red] {e}")
            if e.recovery_hint:
                console.print()
                console.print(f"[dim]{e.recovery_hint}[/dim]")
            raise typer.Exit(1)

        set_token(token)
        emit_login_completed(auth_method="token")
        console.print()
        console.print("[green]✓[/green] Token saved to ~/.runtm/config.yaml")
        console.print("[dim]You can now use runtm commands.[/dim]")


@app.command("logout")
def logout(
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Remove saved API credentials.

    Clears the stored API token from ~/.runtm/config.yaml.
    You will need to run 'runtm login' again to authenticate.

    Examples:
        runtm logout          # Prompt for confirmation
        runtm logout --force  # Skip confirmation
    """
    existing_token = get_token()
    
    if not existing_token:
        console.print("[dim]No token found. Already logged out.[/dim]")
        raise typer.Exit(0)

    # Mask the token for display
    masked = existing_token[:16] + "..." + existing_token[-4:] if len(existing_token) > 24 else existing_token[:8] + "..."
    
    if not force:
        console.print()
        console.print(f"Current token: [dim]{masked}[/dim]")
        console.print()
        if not typer.confirm("Remove this token?", default=False):
            console.print("[dim]Token kept.[/dim]")
            raise typer.Exit(0)

    clear_token()
    console.print()
    console.print("[green]✓[/green] Token removed from ~/.runtm/config.yaml")
    console.print("[dim]Run 'runtm login' to authenticate again.[/dim]")


# Admin subcommand group (for self-host operators)
app.add_typer(admin_app, name="admin")


@app.command("version")
def version() -> None:
    """Show CLI version."""
    console.print(f"runtm-cli v{__version__}")


def main() -> None:
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()

