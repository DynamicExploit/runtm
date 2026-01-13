"""Base interface for sandbox providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from runtm_shared.types import Sandbox, SandboxConfig, SandboxState


class SandboxProvider(ABC):
    """Interface for sandbox providers.

    Implementations handle the actual creation and management of
    isolated sandbox environments. Different providers can use
    different isolation technologies:

    - LocalSandboxProvider: Uses sandbox-runtime (bubblewrap/seatbelt)
    - CloudProvider: Uses gVisor/Firecracker (future)
    """

    @abstractmethod
    def create(self, sandbox_id: str, config: SandboxConfig) -> Sandbox:
        """Create a new sandbox.

        Creates the workspace directory and initializes sandbox state.
        Does not start any processes.

        Args:
            sandbox_id: Unique identifier for the sandbox.
            config: Configuration for the sandbox.

        Returns:
            Created Sandbox object.
        """
        ...

    @abstractmethod
    def attach(self, sandbox_id: str) -> int:
        """Attach to a sandbox.

        Runs an interactive shell inside the sandbox with proper
        isolation. Blocks until the shell exits.

        Args:
            sandbox_id: ID of sandbox to attach to.

        Returns:
            Exit code from the shell process.

        Raises:
            ValueError: If sandbox not found.
        """
        ...

    @abstractmethod
    def stop(self, sandbox_id: str) -> None:
        """Stop a sandbox.

        Marks the sandbox as stopped. Does not delete workspace.

        Args:
            sandbox_id: ID of sandbox to stop.
        """
        ...

    @abstractmethod
    def destroy(self, sandbox_id: str) -> None:
        """Destroy a sandbox.

        Deletes the workspace directory and removes state.

        Args:
            sandbox_id: ID of sandbox to destroy.
        """
        ...

    @abstractmethod
    def list_sandboxes(self) -> list[Sandbox]:
        """List all sandboxes.

        Returns:
            List of all sandboxes managed by this provider.
        """
        ...

    @abstractmethod
    def get_state(self, sandbox_id: str) -> SandboxState:
        """Get the state of a sandbox.

        Args:
            sandbox_id: ID of sandbox.

        Returns:
            Current state of the sandbox.
            Returns DESTROYED if sandbox not found.
        """
        ...
