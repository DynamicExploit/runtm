"""AI coding agent adapters for runtm.

This package provides adapters for various AI coding agents:
- Claude Code: Anthropic's CLI coding agent
- Codex: OpenAI's code model (future)
- Gemini: Google's AI model (future)
"""

from runtm_agents.adapters.base import AgentAdapter, AgentOutput, AgentResult
from runtm_agents.adapters.claude_code import ClaudeCodeAdapter
from runtm_agents.runner import get_adapter, run_prompt_in_sandbox

__all__ = [
    "AgentAdapter",
    "AgentOutput",
    "AgentResult",
    "ClaudeCodeAdapter",
    "get_adapter",
    "run_prompt_in_sandbox",
]
