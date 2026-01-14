"""Agent runner for executing prompts in sandboxes.

Provides functions to run agent prompts within sandbox isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from runtm_agents.adapters.base import AgentAdapter, AgentOutput
from runtm_agents.adapters.claude_code import ClaudeCodeAdapter

if TYPE_CHECKING:
    from runtm_shared.types import Sandbox

logger = structlog.get_logger()

# Registry of available adapters
_ADAPTERS: dict[str, type[AgentAdapter]] = {
    "claude-code": ClaudeCodeAdapter,
    # Future: "codex": CodexAdapter,
    # Future: "gemini": GeminiAdapter,
}


def get_adapter(agent_type: str) -> AgentAdapter:
    """Get an adapter instance for the specified agent type.

    Args:
        agent_type: Agent type name (e.g., "claude-code")

    Returns:
        AgentAdapter instance

    Raises:
        ValueError: If agent type is not supported
    """
    adapter_class = _ADAPTERS.get(agent_type)
    if not adapter_class:
        supported = ", ".join(_ADAPTERS.keys())
        raise ValueError(f"Unknown agent type: {agent_type}. Supported: {supported}")

    return adapter_class()


def list_adapters() -> list[str]:
    """List all available agent adapter types.

    Returns:
        List of agent type names
    """
    return list(_ADAPTERS.keys())


async def run_prompt_in_sandbox(
    sandbox: Sandbox,
    prompt: str,
    *,
    continue_session: str | None = None,
    stream: bool = True,
) -> AsyncIterator[AgentOutput]:
    """Run an agent prompt inside sandbox isolation.

    This function wraps agent execution to run within a sandbox's
    workspace directory. The sandbox-runtime tool handles actual
    OS-level isolation.

    Args:
        sandbox: Sandbox instance to run in
        prompt: The prompt to send to the agent
        continue_session: Session ID to continue (optional)
        stream: Whether to stream output

    Yields:
        AgentOutput events as they occur
    """
    # Get the appropriate adapter
    adapter = get_adapter(sandbox.config.agent.value)
    workspace = Path(sandbox.workspace_path)

    logger.info(
        "Running prompt in sandbox",
        sandbox_id=sandbox.id,
        agent=sandbox.config.agent.value,
        workspace=str(workspace),
        prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
    )

    # Verify workspace exists
    if not workspace.exists():
        yield AgentOutput(
            type="error",
            content=f"Workspace does not exist: {workspace}",
        )
        return

    # Run the prompt through the adapter
    # Note: The sandbox isolation is handled by sandbox-runtime (srt)
    # which should be configured to wrap the claude command.
    # For now, we run directly in the workspace directory.
    async for output in adapter.prompt(
        prompt=prompt,
        workspace=workspace,
        continue_session=continue_session,
        stream=stream,
    ):
        yield output


async def run_prompt(
    workspace: Path,
    prompt: str,
    agent_type: str = "claude-code",
    *,
    continue_session: str | None = None,
    stream: bool = True,
) -> AsyncIterator[AgentOutput]:
    """Run an agent prompt in a directory (no sandbox required).

    Convenience function for running prompts without a full sandbox.
    Useful for testing or when sandbox isolation is not needed.

    Args:
        workspace: Working directory for the agent
        prompt: The prompt to send to the agent
        agent_type: Agent type (default: "claude-code")
        continue_session: Session ID to continue (optional)
        stream: Whether to stream output

    Yields:
        AgentOutput events as they occur
    """
    adapter = get_adapter(agent_type)

    logger.info(
        "Running prompt",
        agent=agent_type,
        workspace=str(workspace),
        prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
    )

    async for output in adapter.prompt(
        prompt=prompt,
        workspace=workspace,
        continue_session=continue_session,
        stream=stream,
    ):
        yield output
