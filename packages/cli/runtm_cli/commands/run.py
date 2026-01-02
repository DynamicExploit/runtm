"""Run command - start local development server based on template runtime."""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

from runtm_shared.lockfiles import check_lockfile, fix_lockfile
from runtm_shared.manifest import Manifest

console = Console()


def _get_package_manager() -> tuple[str, str]:
    """Detect available package manager (prefer Bun for speed).

    Returns:
        Tuple of (package_manager_name, install_command)
        e.g., ("bun", "bun install") or ("npm", "npm install")
    """
    # Prefer Bun if available (3x faster)
    if shutil.which("bun"):
        return "bun", "bun"
    # Fall back to npm
    if shutil.which("npm"):
        return "npm", "npm"
    # Last resort - try npx
    if shutil.which("npx"):
        return "npm (via npx)", "npx"

    console.print("[red]✗[/red] No package manager found. Install Bun or npm.")
    raise SystemExit(1)


def _run_js_install(path: Path, pm_name: str, pm_cmd: str) -> bool:
    """Run JavaScript package installation.

    Args:
        path: Directory to run in
        pm_name: Package manager name for display
        pm_cmd: Package manager command (bun, npm, etc.)

    Returns:
        True if successful
    """
    console.print(f"[dim]Installing dependencies with {pm_name}...[/dim]")

    if pm_cmd == "bun":
        # Bun install (faster, respects package-lock.json)
        result = subprocess.run(
            ["bun", "install"],
            cwd=path,
            check=False,
        )
    else:
        # npm install
        result = subprocess.run(
            ["npm", "install"],
            cwd=path,
            check=False,
        )

    return result.returncode == 0


def _run_js_dev(path: Path, pm_cmd: str) -> subprocess.Popen:
    """Start JavaScript dev server.

    Args:
        path: Directory to run in
        pm_cmd: Package manager command (bun, npm, etc.)

    Returns:
        Popen process
    """
    if pm_cmd == "bun":
        return subprocess.Popen(
            ["bun", "run", "dev"],
            cwd=path,
        )
    else:
        return subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=path,
        )


def run_command(
    path: Path,
    install: bool = True,
    no_autofix: bool = False,
) -> None:
    """Run the project locally based on template runtime.

    Reads runtm.yaml to detect the runtime and starts the appropriate
    development server with the correct port.

    Uses Bun if available (3x faster), falls back to npm.

    Automatically fixes lockfile drift unless --no-autofix is passed.

    Args:
        path: Path to project directory
        install: Whether to install dependencies first
        no_autofix: If True, don't auto-fix lockfile issues (just warn)
    """
    from runtm_cli.telemetry import command_span, emit_run_started

    manifest_path = path / "runtm.yaml"

    if not manifest_path.exists():
        console.print(
            "[red]✗[/red] No runtm.yaml found. "
            "Run [bold]runtm init[/bold] first or check you're in the right directory."
        )
        raise SystemExit(1)

    try:
        manifest = Manifest.from_file(manifest_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Invalid runtm.yaml: {e}")
        raise SystemExit(1) from e

    runtime = manifest.runtime
    template = manifest.template

    # Check if Bun is available
    has_bun = shutil.which("bun") is not None

    with command_span("run", {"runtm.runtime": runtime, "runtm.template": template}):
        # Emit run started event
        emit_run_started(runtime, has_bun)

        console.print(f"[dim]Detected template:[/dim] [bold]{template}[/bold] ({runtime})")

        # Check and auto-fix lockfile (sandbox is disposable, autofix by default)
        lockfile_status = check_lockfile(path, runtime)
        if lockfile_status.needs_fix:
            if no_autofix:
                console.print(
                    f"[yellow]⚠[/yellow] Lockfile {'missing' if not lockfile_status.exists else 'out of sync'}. "
                    f"Run: [bold]{lockfile_status.install_cmd}[/bold]"
                )
            else:
                action = "Creating" if not lockfile_status.exists else "Updating"
                console.print(
                    f"[yellow]{action} lockfile via {lockfile_status.install_cmd}...[/yellow]"
                )
                if fix_lockfile(path, lockfile_status):
                    console.print("[dim]Committing lockfile is recommended.[/dim]")
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Failed to fix lockfile. "
                        f"Run manually: [bold]{lockfile_status.install_cmd}[/bold]"
                    )

        if runtime == "python":
            _run_python(path, install)
        elif runtime == "node":
            _run_node(path, install)
        elif runtime == "fullstack":
            _run_fullstack(path, install)
        else:
            console.print(f"[red]✗[/red] Unknown runtime: {runtime}")
            raise SystemExit(1)


def _run_python(path: Path, install: bool) -> None:
    """Run Python/FastAPI project."""
    console.print("\n[bold blue]Starting Python server...[/bold blue]")

    if install:
        console.print("[dim]Installing dependencies...[/dim]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
            cwd=path,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            # Try without dev extras
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=path,
                check=False,
            )
            if result.returncode != 0:
                console.print("[red]✗[/red] Failed to install dependencies")
                raise SystemExit(1)

    console.print("[green]→[/green] Running on [bold]http://localhost:8080[/bold]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--port",
                "8080",
                "--host",
                "0.0.0.0",
            ],
            cwd=path,
            check=False,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")


def _run_node(path: Path, install: bool) -> None:
    """Run Node.js/Next.js project."""
    console.print("\n[bold blue]Starting Node.js server...[/bold blue]")

    pm_name, pm_cmd = _get_package_manager()
    console.print(f"[dim]Using {pm_name}[/dim]")

    if install and not _run_js_install(path, pm_name, pm_cmd):
        console.print("[red]✗[/red] Failed to install dependencies")
        raise SystemExit(1)

    console.print("[green]→[/green] Running on [bold]http://localhost:3000[/bold]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        if pm_cmd == "bun":
            subprocess.run(["bun", "run", "dev"], cwd=path, check=False)
        else:
            subprocess.run(["npm", "run", "dev"], cwd=path, check=False)
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")


def _run_fullstack(path: Path, install: bool) -> None:
    """Run fullstack project (frontend + backend)."""
    backend_path = path / "backend"
    frontend_path = path / "frontend"

    if not backend_path.exists() or not frontend_path.exists():
        console.print("[red]✗[/red] Fullstack template requires backend/ and frontend/ directories")
        raise SystemExit(1)

    console.print("\n[bold blue]Starting fullstack servers...[/bold blue]")

    pm_name, pm_cmd = _get_package_manager()
    console.print(f"[dim]Using {pm_name} for frontend[/dim]")

    # Install dependencies
    if install:
        console.print("[dim]Installing backend dependencies...[/dim]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
            cwd=backend_path,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=backend_path,
                check=False,
            )

        if not _run_js_install(frontend_path, pm_name, pm_cmd):
            console.print(
                "[yellow]⚠[/yellow] Frontend dependency install had issues, continuing..."
            )

    console.print("[green]→[/green] Backend running on [bold]http://localhost:8080[/bold]")
    console.print("[green]→[/green] Frontend running on [bold]http://localhost:3000[/bold]")
    console.print("[dim]Press Ctrl+C to stop both servers[/dim]\n")

    # Start both processes
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--port",
            "8080",
            "--host",
            "0.0.0.0",
        ],
        cwd=backend_path,
    )

    frontend_proc = _run_js_dev(frontend_path, pm_cmd)

    def cleanup(_signum: int, _frame: Any) -> None:
        """Clean up child processes on exit."""
        console.print("\n[dim]Stopping servers...[/dim]")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait()
        frontend_proc.wait()
        console.print("[dim]Servers stopped.[/dim]")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Wait for either process to exit
    try:
        while True:
            backend_exit = backend_proc.poll()
            frontend_exit = frontend_proc.poll()

            if backend_exit is not None:
                console.print(f"[yellow]Backend exited with code {backend_exit}[/yellow]")
                frontend_proc.terminate()
                break

            if frontend_exit is not None:
                console.print(f"[yellow]Frontend exited with code {frontend_exit}[/yellow]")
                backend_proc.terminate()
                break

            import time

            time.sleep(0.5)
    except KeyboardInterrupt:
        cleanup(signal.SIGINT, None)
