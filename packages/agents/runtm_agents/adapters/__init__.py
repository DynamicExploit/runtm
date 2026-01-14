"""Agent adapters for different AI coding agents."""

from runtm_agents.adapters.base import AgentAdapter, AgentOutput, AgentResult
from runtm_agents.adapters.claude_code import ClaudeCodeAdapter

__all__ = [
    "AgentAdapter",
    "AgentOutput",
    "AgentResult",
    "ClaudeCodeAdapter",
]
