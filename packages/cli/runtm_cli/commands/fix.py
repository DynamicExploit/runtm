"""Fix command - universal repair for common project issues."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from runtm_shared.lockfiles import check_all_lockfiles, fix_lockfile
from runtm_shared.manifest import Manifest

console = Console()


def fix_command(
    path: Path = Path("."),
) -> None:
    """Fix common project issues to make it deployment-ready.

    Currently fixes:
    - Missing or drifted lockfiles

    Future fixes:
    - Missing .runtmignore
    - Manifest issues

    Args:
        path: Path to project directory
    """
    manifest_path = path / "runtm.yaml"

    if not manifest_path.exists():
        console.print("[red]✗[/red] No runtm.yaml found. Run [bold]runtm init[/bold] first.")
        raise typer.Exit(1)

    try:
        manifest = Manifest.from_file(manifest_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Invalid runtm.yaml: {e}")
        raise typer.Exit(1) from e

    console.print(f"[dim]Fixing project: {path.absolute()}[/dim]")
    console.print()

    fixed_count = 0
    error_count = 0

    # Fix lockfiles
    lockfile_statuses = check_all_lockfiles(path, manifest.runtime)

    for status in lockfile_statuses:
        if status.needs_fix:
            action = "Creating" if not status.exists else "Updating"
            console.print(f"[yellow]{action} {status.lockfile_path}...[/yellow]")

            if fix_lockfile(path, status):
                console.print(f"[green]✓[/green] Fixed {status.lockfile_path}")
                fixed_count += 1
            else:
                console.print(f"[red]✗[/red] Failed to fix {status.lockfile_path}")
                console.print(f"    Run manually: {status.install_cmd}")
                error_count += 1
        else:
            console.print(f"[green]✓[/green] {status.lockfile_path} is in sync")

    # Summary
    console.print()
    if error_count > 0:
        console.print(f"[red]✗[/red] {error_count} issue(s) could not be fixed")
        raise typer.Exit(1)
    elif fixed_count > 0:
        console.print(f"[green]✓[/green] Fixed {fixed_count} issue(s)")
        console.print("[dim]Committing changes is recommended.[/dim]")
    else:
        console.print("[green]✓[/green] No issues found")
