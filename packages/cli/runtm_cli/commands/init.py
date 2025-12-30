"""Init command - scaffold new projects from templates."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import questionary
import typer
from questionary import Style
from rich.console import Console

console = Console()

# Template definitions with descriptions (ordered list for numbered selection)
TEMPLATES_LIST = [
    {
        "name": "backend-service",
        "title": "Backend Service",
        "description": "Great for scrapers, agent backends, webhooks, and API services",
    },
    {
        "name": "static-site",
        "title": "Static Site",
        "description": "Great for marketing sites, landing pages, docs, and status pages",
    },
    {
        "name": "web-app",
        "title": "Web App",
        "description": "Great for dashboards, customer portals, and AI app demos",
    },
]

# Dict for quick lookup
TEMPLATES = {t["name"]: t for t in TEMPLATES_LIST}

# Custom style for questionary prompts - using emerald green (like "Live" status in dashboard)
PROMPT_STYLE = Style([
    ("qmark", "fg:#10b981 bold"),           # emerald-500
    ("question", "bold"),
    ("answer", "fg:#10b981 bold"),          # emerald-500
    ("pointer", "fg:#10b981 bold"),         # emerald-500
    ("highlighted", "fg:#10b981 bold"),     # emerald-500
    ("selected", "fg:#10b981"),             # emerald-500
    ("separator", "fg:#71717a"),            # zinc-500
    ("instruction", "fg:#71717a"),          # zinc-500
])


def _find_project_root() -> Optional[Path]:
    """Find the project root directory by looking for pyproject.toml.

    Returns:
        Path to project root or None if not found
    """
    # Start from the current file and walk up
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / "templates").exists():
            return current
        current = current.parent
    return None


def prompt_template_selection() -> str:
    """Prompt user to select a template interactively.

    Supports both arrow key navigation and number shortcuts (1, 2, 3) for LLM/agent use.

    Returns:
        Selected template name
    """
    # Build choices with numbered shortcuts for LLM-friendliness
    choices = [
        questionary.Choice(
            title=f"[{i+1}] {t['title']} - {t['description']}",
            value=t["name"],
            shortcut_key=str(i + 1),  # Allow pressing 1, 2, 3 to select
        )
        for i, t in enumerate(TEMPLATES_LIST)
    ]

    console.print()
    console.print("[dim]Select a template (arrow keys + Enter, or press 1/2/3):[/dim]")
    console.print()
    
    result = questionary.select(
        "What type of project do you want to create?",
        choices=choices,
        style=PROMPT_STYLE,
        instruction="",
        use_shortcuts=True,  # Enable number shortcuts
    ).ask()

    if result is None:
        # User cancelled (Ctrl+C)
        raise typer.Exit(0)

    return result


def get_template_path(template: str) -> Optional[Path]:
    """Get path to template directory.

    Args:
        template: Template name (e.g., "backend-service")

    Returns:
        Path to template or None if not found
    """
    # Try to find project root
    project_root = _find_project_root()
    if project_root:
        template_path = project_root / "templates" / template
        if template_path.exists():
            return template_path

    # Fallback: try relative to current file (for development)
    # init.py is at: packages/cli/runtm_cli/commands/init.py
    # Go up 5 levels to get to project root
    dev_template_path = Path(__file__).parent.parent.parent.parent.parent / "templates" / template
    if dev_template_path.exists():
        return dev_template_path

    # Try current working directory (if running from project root)
    cwd_template_path = Path.cwd() / "templates" / template
    if cwd_template_path.exists():
        return cwd_template_path

    return None


def _get_old_template(dest_path: Path) -> Optional[str]:
    """Detect the old template from existing runtm.yaml.

    Args:
        dest_path: Destination directory

    Returns:
        Old template name or None if not found
    """
    runtm_yaml = dest_path / "runtm.yaml"
    if not runtm_yaml.exists():
        return None

    try:
        import yaml
        with runtm_yaml.open() as f:
            data = yaml.safe_load(f)
            return data.get("template") if isinstance(data, dict) else None
    except Exception:
        return None


def _cleanup_old_template(dest_path: Path, old_template: str) -> None:
    """Remove template-specific files/directories from the old template.

    Args:
        dest_path: Destination directory
        old_template: Name of the old template to clean up
    """
    # Template-specific paths to remove when switching templates
    template_paths = {
        "backend-service": [
            "app",
            "tests",
            "pyproject.toml",
            "Dockerfile",
            "README.md",
            "AGENT.md",
            "CLAUDE.md",
            ".cursor",
        ],
        "static-site": [
            "app",
            "components",
            "public",
            "package.json",
            "package-lock.json",
            "next.config.js",
            "next-env.d.ts",
            "postcss.config.js",
            "tailwind.config.js",
            "tsconfig.json",
            "Dockerfile",
            "README.md",
            "AGENT.md",
            "CLAUDE.md",
            ".cursor",
        ],
        "web-app": [
            "frontend",
            "backend",
            "Dockerfile",
            "README.md",
            "AGENT.md",
            "CLAUDE.md",
            ".cursor",
        ],
    }

    paths_to_remove = template_paths.get(old_template, [])
    for path_name in paths_to_remove:
        path_to_remove = dest_path / path_name
        if path_to_remove.exists():
            if path_to_remove.is_dir():
                shutil.rmtree(path_to_remove)
            else:
                path_to_remove.unlink()


def copy_template(
    template_path: Path,
    dest_path: Path,
    name: Optional[str] = None,
    cleanup_old: bool = False,
) -> None:
    """Copy template to destination.

    Args:
        template_path: Source template directory
        dest_path: Destination directory
        name: Optional project name to substitute
        cleanup_old: If True, clean up old template files before copying
    """
    # Clean up old template if requested
    if cleanup_old:
        old_template = _get_old_template(dest_path)
        if old_template and old_template in TEMPLATES:
            _cleanup_old_template(dest_path, old_template)

    # Files that need name substitution
    name_substitution_files = {"runtm.yaml", "package.json", "pyproject.toml"}

    # Copy all files
    for item in template_path.rglob("*"):
        if item.is_file():
            relative = item.relative_to(template_path)
            dest_file = dest_path / relative

            # Create parent directories
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(item, dest_file)

            # Substitute name in config files
            if relative.name in name_substitution_files and name:
                content = dest_file.read_text()
                # Replace all placeholder names
                content = content.replace("my-service", name)
                content = content.replace("my-site", name)
                content = content.replace("my-web-app-frontend", f"{name}-frontend")
                content = content.replace("my-web-app-backend", f"{name}-backend")
                content = content.replace("my-web-app", name)
                dest_file.write_text(content)


def init_command(
    template: Optional[str] = typer.Argument(
        None,
        help="Template type: backend-service, static-site, or web-app",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path", "-p",
        help="Destination directory",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Project name (defaults to directory name)",
    ),
) -> None:
    """Initialize a new project from template.

    Examples:
        runtm init                  # Interactive template selection
        runtm init backend-service  # Creates FastAPI backend service
        runtm init static-site      # Creates Next.js static site
        runtm init web-app          # Creates fullstack app (Next.js + FastAPI)
    """
    import time

    from runtm_cli.telemetry import (
        command_span,
        emit_init_completed,
        emit_init_template_selected,
    )

    # If no template provided, show interactive selection
    # Handle None, empty string, or the string "None" (Typer edge case)
    if template is None or template == "" or (isinstance(template, str) and template.lower() == "none"):
        template_name = prompt_template_selection()
    else:
        template_name = template

    start_time = time.time()

    with command_span("init", {"runtm.template": template_name}) as span:
        # Get template path
        template_path = get_template_path(template_name)
        if not template_path:
            console.print(f"[red]✗[/red] Template not found: {template_name}")
            console.print()
            console.print("Available templates:")
            for i, t in enumerate(TEMPLATES_LIST):
                console.print(f"  [{i+1}] [bold]{t['name']}[/bold] - {t['description']}")
            console.print()
            console.print("[dim]Tip: Run [bold]runtm init[/bold] for interactive selection[/dim]")
            console.print("[dim]  or [bold]runtm init backend-service[/bold] to specify directly[/dim]")
            raise typer.Exit(1)

        # Resolve destination
        dest_path = path.resolve()

        # Check if destination has files
        has_existing_files = dest_path.exists() and any(dest_path.iterdir())
        should_cleanup = False
        if has_existing_files:
            # Check for existing runtm.yaml
            if (dest_path / "runtm.yaml").exists():
                old_template = _get_old_template(dest_path)
                if old_template and old_template != template_name:
                    console.print(f"[yellow]⚠[/yellow] Project already initialized with template: {old_template}")
                    console.print(f"Switching to template: {template_name}")
                    if not typer.confirm("Overwrite existing files? (old template files will be removed)"):
                        raise typer.Exit(0)
                    should_cleanup = True
                else:
                    console.print("[yellow]⚠[/yellow] Project already initialized (runtm.yaml exists)")
                    if not typer.confirm("Overwrite existing files?"):
                        raise typer.Exit(0)

        # Emit template selected event
        emit_init_template_selected(template_name, has_existing_files)

        # Resolve name
        if not name:
            name = dest_path.name.lower().replace("_", "-")

        console.print(f"Initializing {template_name} project...")
        console.print(f"  Path: {dest_path}")
        console.print(f"  Name: {name}")
        console.print()

        # Copy template
        try:
            copy_template(template_path, dest_path, name, cleanup_old=should_cleanup)
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to initialize: {e}")
            raise typer.Exit(1)

        # Emit init completed event
        duration_ms = (time.time() - start_time) * 1000
        emit_init_completed(template_name, duration_ms)

        console.print("[green]✓[/green] Project initialized!")
        console.print()
        console.print("[dim]AI assistant rules auto-configured for:[/dim]")
        console.print("[dim]  Cursor, Claude Code, Windsurf, GitHub Copilot[/dim]")
        console.print()
        console.print("Next steps:")
        # Only show cd if destination is different from current directory
        if dest_path.resolve() != Path.cwd().resolve():
            console.print(f"  cd {dest_path.name}")
        console.print("  runtm validate")
        console.print("  runtm deploy")

