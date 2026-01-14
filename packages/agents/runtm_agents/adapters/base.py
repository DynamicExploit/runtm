"""Base interface for AI coding agent adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentOutput:
    """Structured output from an agent.

    Represents a single output event from the agent during execution.
    """

    type: str  # "text", "tool_use", "file_write", "command", "error", "result"
    content: str
    metadata: dict | None = None


@dataclass
class AgentResult:
    """Final result from an agent prompt.

    Summarizes the outcome of running a prompt through an agent.
    """

    session_id: str  # For continuing conversations
    success: bool
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0


class AgentAdapter(ABC):
    """Interface for AI coding agent adapters.

    Adapters wrap CLI tools (like `claude`) to provide a uniform
    interface for sending prompts and streaming output.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name (e.g., 'claude-code')."""
        pass

    @abstractmethod
    def check_installed(self) -> bool:
        """Check if the agent CLI is installed."""
        pass

    @abstractmethod
    def check_auth(self) -> bool:
        """Check if agent is authenticated."""
        pass

    @abstractmethod
    async def prompt(
        self,
        prompt: str,
        workspace: Path,
        *,
        continue_session: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[AgentOutput]:
        """Send prompt to agent and stream output.

        Args:
            prompt: The user's prompt
            workspace: Working directory for the agent
            continue_session: Session ID to continue (optional)
            stream: Whether to stream output

        Yields:
            AgentOutput events as they occur
        """
        pass

    @abstractmethod
    def get_result(self) -> AgentResult:
        """Get final result after prompt completes."""
        pass
