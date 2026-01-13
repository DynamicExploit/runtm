"""Local sandbox provider using sandbox-runtime.

Uses Anthropic's sandbox-runtime (bubblewrap on Linux, seatbelt on macOS)
for OS-level process isolation. Same technology as Claude Code.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import structlog
from runtm_shared.types import Sandbox, SandboxConfig, SandboxState

from ..config import generate_srt_config, write_config_file
from ..state import SandboxStateStore
from .base import SandboxProvider

logger = structlog.get_logger()


class LocalSandboxProvider(SandboxProvider):
    """Local sandbox using Anthropic's sandbox-runtime.

    Creates isolated environments using OS-level primitives:
    - Linux: bubblewrap (bwrap)
    - macOS: seatbelt (sandbox-exec)

    Startup time is <100ms since no containers are involved.
    """

    def __init__(self, sandboxes_dir: Path | None = None):
        """Initialize the provider.

        Args:
            sandboxes_dir: Directory to store sandboxes.
                          Defaults to ~/.runtm/sandboxes/
        """
        if sandboxes_dir is None:
            sandboxes_dir = Path.home() / ".runtm" / "sandboxes"

        self.sandboxes_dir = sandboxes_dir
        self.sandboxes_dir.mkdir(parents=True, exist_ok=True)

        self.state_store = SandboxStateStore(state_dir=sandboxes_dir)

    def create(self, sandbox_id: str, config: SandboxConfig) -> Sandbox:
        """Create a new sandbox.

        Creates the workspace directory and optionally scaffolds
        a template into it.

        Args:
            sandbox_id: Unique identifier for the sandbox.
            config: Configuration for the sandbox.

        Returns:
            Created Sandbox object with RUNNING state.
        """
        logger.info("Creating sandbox", sandbox_id=sandbox_id, agent=config.agent.value)

        # Create workspace directory
        workspace = self.sandboxes_dir / sandbox_id / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        # Scaffold template if specified
        if config.template:
            self._scaffold_template(workspace, config.template)

        # Create sandbox object
        sandbox = Sandbox(
            id=sandbox_id,
            session_id=sandbox_id,  # 1:1 for MVP
            config=config,
            state=SandboxState.RUNNING,
            workspace_path=str(workspace),
        )

        # Persist state
        self.state_store.save(sandbox)

        logger.info("Sandbox created", sandbox_id=sandbox_id, workspace=str(workspace))
        return sandbox

    def attach(self, sandbox_id: str) -> int:
        """Attach to a sandbox.

        Runs an interactive shell with sandbox-runtime isolation.

        Args:
            sandbox_id: ID of sandbox to attach to.

        Returns:
            Exit code from the shell process.

        Raises:
            ValueError: If sandbox not found.
        """
        sandbox = self.state_store.load(sandbox_id)
        if sandbox is None:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        workspace = Path(sandbox.workspace_path)
        logger.info("Attaching to sandbox", sandbox_id=sandbox_id, workspace=str(workspace))

        # Generate sandbox-runtime config
        srt_config = generate_srt_config(sandbox.config)
        config_path = self.sandboxes_dir / sandbox_id / "sandbox-config.json"
        write_config_file(srt_config, config_path)

        # Run shell in sandbox via srt
        # srt wraps the command with bubblewrap/seatbelt isolation
        result = subprocess.run(
            ["srt", "--config", str(config_path), "--", "/bin/bash"],
            cwd=workspace,
        )

        logger.info("Sandbox session ended", sandbox_id=sandbox_id, exit_code=result.returncode)
        return result.returncode

    def stop(self, sandbox_id: str) -> None:
        """Stop a sandbox.

        Marks the sandbox as stopped without deleting workspace.

        Args:
            sandbox_id: ID of sandbox to stop.
        """
        sandbox = self.state_store.load(sandbox_id)
        if sandbox is None:
            logger.debug("Sandbox not found for stop", sandbox_id=sandbox_id)
            return

        sandbox.state = SandboxState.STOPPED
        self.state_store.save(sandbox)

        logger.info("Sandbox stopped", sandbox_id=sandbox_id)

    def destroy(self, sandbox_id: str) -> None:
        """Destroy a sandbox.

        Deletes the workspace directory and removes state.

        Args:
            sandbox_id: ID of sandbox to destroy.
        """
        logger.info("Destroying sandbox", sandbox_id=sandbox_id)

        # Delete workspace directory
        sandbox_dir = self.sandboxes_dir / sandbox_id
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
            logger.debug("Deleted sandbox directory", path=str(sandbox_dir))

        # Remove from state store (state.json is already deleted with directory)
        # But call delete anyway for consistency
        self.state_store.delete(sandbox_id)

        logger.info("Sandbox destroyed", sandbox_id=sandbox_id)

    def list_sandboxes(self) -> list[Sandbox]:
        """List all sandboxes.

        Returns:
            List of all sandboxes.
        """
        return self.state_store.list_all()

    def get_state(self, sandbox_id: str) -> SandboxState:
        """Get the state of a sandbox.

        Args:
            sandbox_id: ID of sandbox.

        Returns:
            Current state, or DESTROYED if not found.
        """
        sandbox = self.state_store.load(sandbox_id)
        if sandbox is None:
            return SandboxState.DESTROYED
        return sandbox.state

    def _scaffold_template(self, workspace: Path, template: str) -> None:
        """Scaffold a template into the workspace.

        Args:
            workspace: Workspace directory to scaffold into.
            template: Template name (backend-service, web-app, static-site).
        """
        logger.info("Scaffolding template", template=template, workspace=str(workspace))

        # Find template directory
        # Templates are in the runtm repo at templates/
        # For now, try to find them relative to this package
        possible_paths = [
            # Development: running from repo
            Path(__file__).parent.parent.parent.parent.parent / "templates" / template,
            # Installed: templates might be in package data
            Path(__file__).parent.parent / "templates" / template,
        ]

        template_path = None
        for path in possible_paths:
            if path.exists():
                template_path = path
                break

        if template_path is None:
            logger.warning("Template not found", template=template)
            return

        # Copy template files
        shutil.copytree(template_path, workspace, dirs_exist_ok=True)
        logger.info("Template scaffolded", template=template, files=len(list(workspace.rglob("*"))))
