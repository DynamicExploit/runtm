"""Secrets command - manage local environment secrets.

Secrets are stored in .env.local (gitignored, cursorignored) and injected
to the deployment provider at deploy time. Runtm never stores secret values.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import typer
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.table import Table

from runtm_shared.manifest import Manifest

console = Console()

# Files to check for secrets (in priority order)
ENV_FILES = [".env.local", ".env"]


def get_env_file_path(path: Path) -> Path:
    """Get the path to the .env.local file."""
    return path / ".env.local"


def ensure_gitignore(path: Path) -> None:
    """Ensure .env.local is in .gitignore."""
    gitignore_path = path / ".gitignore"
    pattern = ".env.local"

    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if pattern not in content:
            # Add to gitignore
            with open(gitignore_path, "a") as f:
                if not content.endswith("\n"):
                    f.write("\n")
                f.write(f"\n# Local secrets (never commit)\n{pattern}\n")
            console.print(f"[dim]Added {pattern} to .gitignore[/dim]")
    else:
        # Create .gitignore
        gitignore_path.write_text(f"# Local secrets (never commit)\n{pattern}\n")
        console.print(f"[dim]Created .gitignore with {pattern}[/dim]")


def ensure_cursorignore(path: Path) -> None:
    """Ensure .env* is in .cursorignore (agent protection)."""
    cursorignore_path = path / ".cursorignore"
    patterns = [".env", ".env.*", ".env.local"]

    if cursorignore_path.exists():
        content = cursorignore_path.read_text()
        missing = [p for p in patterns if p not in content]
        if missing:
            with open(cursorignore_path, "a") as f:
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n# Secrets - never expose to AI agents\n")
                for p in missing:
                    f.write(f"{p}\n")
            console.print("[dim]Added .env patterns to .cursorignore[/dim]")
    # Don't create .cursorignore if it doesn't exist - template should provide it


def load_local_env(path: Path) -> dict[str, str]:
    """Load environment variables from .env.local and .env files.

    Priority: .env.local > .env > environment

    Args:
        path: Project directory

    Returns:
        Dict of env var name -> value
    """
    env_vars: dict[str, str] = {}

    # Load in reverse priority order (later overrides earlier)
    for env_file in reversed(ENV_FILES):
        env_path = path / env_file
        if env_path.exists():
            file_vars = dotenv_values(env_path)
            env_vars.update({k: v for k, v in file_vars.items() if v is not None})

    return env_vars


def resolve_env_vars(
    path: Path,
    manifest: Manifest,
) -> tuple[dict[str, str], list[str], list[str]]:
    """Resolve all env vars from schema against available sources.

    Resolution order:
    1. .env.local file
    2. .env file
    3. System environment
    4. Default from schema

    Args:
        path: Project directory
        manifest: Parsed manifest with env_schema

    Returns:
        Tuple of (resolved_vars, missing_required, warnings)
    """
    resolved: dict[str, str] = {}
    missing_required: list[str] = []
    warnings: list[str] = []

    # Load from files
    file_vars = load_local_env(path)

    for env_var in manifest.env_schema:
        name = env_var.name
        value = None

        # Check sources in priority order
        if name in file_vars:
            value = file_vars[name]
        elif name in os.environ:
            value = os.environ[name]
        elif env_var.default is not None:
            value = env_var.default

        if value is not None:
            resolved[name] = value
        elif env_var.required:
            missing_required.append(name)

    return resolved, missing_required, warnings


def secrets_set_command(
    key_value: str,
    path: Path = Path("."),
) -> None:
    """Set a secret in .env.local.

    Example: runtm secrets set DATABASE_URL=postgres://...

    The value is stored locally in .env.local (gitignored) and will be
    injected to the deployment provider at deploy time.
    """
    # Parse KEY=VALUE
    if "=" not in key_value:
        console.print("[red]✗[/red] Invalid format. Use: runtm secrets set KEY=VALUE")
        raise typer.Exit(1)

    key, value = key_value.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        console.print("[red]✗[/red] Key cannot be empty")
        raise typer.Exit(1)

    # Validate key format
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        console.print(
            "[red]✗[/red] Key must be alphanumeric with underscores, starting with a letter"
        )
        raise typer.Exit(1)

    # Ensure .env.local exists and is gitignored
    env_file = get_env_file_path(path)
    if not env_file.exists():
        env_file.touch()
        console.print(f"[dim]Created {env_file.name}[/dim]")

    ensure_gitignore(path)
    ensure_cursorignore(path)

    # Set the value using python-dotenv
    success, key_written, value_written = set_key(str(env_file), key, value)

    if success:
        # Check if this is in the manifest's env_schema
        manifest_path = path / "runtm.yaml"
        if manifest_path.exists():
            try:
                manifest = Manifest.from_file(manifest_path)
                schema_names = {ev.name for ev in manifest.env_schema}
                if key not in schema_names:
                    console.print(
                        f"[yellow]⚠[/yellow] {key} is not declared in env_schema. "
                        "Consider adding it to runtm.yaml."
                    )
            except Exception:
                pass  # Don't fail on manifest parse errors

        console.print(f"[green]✓[/green] Set {key} in .env.local")
    else:
        console.print(f"[red]✗[/red] Failed to set {key}")
        raise typer.Exit(1)


def secrets_get_command(
    key: str,
    path: Path = Path("."),
) -> None:
    """Get a secret value from .env.local.

    Prints the value to stdout (useful for scripting).
    """
    env_vars = load_local_env(path)

    if key in env_vars:
        # Print just the value (for scripting)
        console.print(env_vars[key])
    else:
        # Also check system environment
        if key in os.environ:
            console.print(os.environ[key])
        else:
            console.print(f"[red]✗[/red] {key} not found", style="red")
            raise typer.Exit(1)


def secrets_list_command(
    path: Path = Path("."),
    show_values: bool = False,
) -> None:
    """List all secrets and their status.

    Shows which env vars from env_schema are set, missing, or have defaults.
    """
    # Load manifest
    manifest_path = path / "runtm.yaml"
    if not manifest_path.exists():
        console.print("[red]✗[/red] No runtm.yaml found. Run `runtm init` first.")
        raise typer.Exit(1)

    try:
        manifest = Manifest.from_file(manifest_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Invalid manifest: {e}")
        raise typer.Exit(1)

    if not manifest.env_schema:
        console.print("[dim]No env_schema defined in runtm.yaml[/dim]")
        return

    # Resolve env vars
    resolved, missing_required, _ = resolve_env_vars(path, manifest)

    # Build table
    table = Table(title="Environment Variables")
    table.add_column("Name", style="cyan")
    table.add_column("Required", style="dim")
    table.add_column("Secret", style="dim")
    table.add_column("Status")
    if show_values:
        table.add_column("Value")

    for env_var in manifest.env_schema:
        name = env_var.name
        required = "✓" if env_var.required else ""
        secret = "🔒" if env_var.secret else ""

        if name in resolved:
            if env_var.default and resolved[name] == env_var.default:
                status = "[dim]default[/dim]"
            else:
                status = "[green]set[/green]"
        elif name in os.environ:
            status = "[blue]env[/blue]"
        else:
            status = "[red]missing[/red]" if env_var.required else "[dim]unset[/dim]"

        row = [name, required, secret, status]

        if show_values:
            if name in resolved:
                if env_var.secret:
                    # Redact secret values
                    row.append("[dim]••••••••[/dim]")
                else:
                    row.append(
                        resolved[name][:50] + "..." if len(resolved[name]) > 50 else resolved[name]
                    )
            else:
                row.append("")

        table.add_row(*row)

    console.print(table)

    # Show summary
    if missing_required:
        console.print()
        console.print(f"[red]Missing required:[/red] {', '.join(missing_required)}")
        console.print("Set them with: runtm secrets set KEY=value")


def secrets_unset_command(
    key: str,
    path: Path = Path("."),
) -> None:
    """Remove a secret from .env.local."""
    env_file = get_env_file_path(path)

    if not env_file.exists():
        console.print("[yellow]⚠[/yellow] No .env.local file found")
        return

    # Read current content
    content = env_file.read_text()
    lines = content.split("\n")

    # Filter out the key
    new_lines = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            found = True
        else:
            new_lines.append(line)

    if found:
        env_file.write_text("\n".join(new_lines))
        console.print(f"[green]✓[/green] Removed {key} from .env.local")
    else:
        console.print(f"[yellow]⚠[/yellow] {key} not found in .env.local")
