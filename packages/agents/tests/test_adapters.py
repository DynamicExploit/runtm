"""Tests for agent adapters."""

from __future__ import annotations

import pytest

from runtm_agents.adapters.base import AgentOutput, AgentResult
from runtm_agents.adapters.claude_code import ClaudeCodeAdapter
from runtm_agents.runner import get_adapter, list_adapters


class TestAgentOutput:
    """Tests for AgentOutput dataclass."""

    def test_create_text_output(self) -> None:
        """Test creating a text output."""
        output = AgentOutput(type="text", content="Hello, world!")
        assert output.type == "text"
        assert output.content == "Hello, world!"
        assert output.metadata is None

    def test_create_output_with_metadata(self) -> None:
        """Test creating an output with metadata."""
        output = AgentOutput(
            type="tool_use",
            content="Writing file.py",
            metadata={"tool": "Write", "input": {"file_path": "file.py"}},
        )
        assert output.type == "tool_use"
        assert output.metadata is not None
        assert output.metadata["tool"] == "Write"


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful result."""
        result = AgentResult(
            session_id="sess_123",
            success=True,
            files_modified=["src/main.py"],
            commands_run=["npm install"],
        )
        assert result.success is True
        assert result.session_id == "sess_123"
        assert "src/main.py" in result.files_modified
        assert result.error is None

    def test_create_failed_result(self) -> None:
        """Test creating a failed result."""
        result = AgentResult(
            session_id="",
            success=False,
            error="Command failed",
        )
        assert result.success is False
        assert result.error == "Command failed"


class TestClaudeCodeAdapter:
    """Tests for ClaudeCodeAdapter."""

    def test_adapter_name(self) -> None:
        """Test adapter name property."""
        adapter = ClaudeCodeAdapter()
        assert adapter.name == "claude-code"

    def test_check_installed_without_claude(self) -> None:
        """Test check_installed when claude is not in PATH."""
        adapter = ClaudeCodeAdapter()
        # This will return True or False depending on the environment
        # We just verify it doesn't raise
        result = adapter.check_installed()
        assert isinstance(result, bool)

    def test_get_result_without_prompt(self) -> None:
        """Test get_result before any prompt is run."""
        adapter = ClaudeCodeAdapter()
        result = adapter.get_result()
        assert result.success is False
        assert result.error == "No prompt executed"


class TestGetAdapter:
    """Tests for get_adapter function."""

    def test_get_claude_adapter(self) -> None:
        """Test getting Claude Code adapter."""
        adapter = get_adapter("claude-code")
        assert adapter.name == "claude-code"
        assert isinstance(adapter, ClaudeCodeAdapter)

    def test_get_unknown_adapter(self) -> None:
        """Test getting an unknown adapter raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_adapter("unknown-agent")
        assert "Unknown agent type" in str(exc_info.value)


class TestListAdapters:
    """Tests for list_adapters function."""

    def test_list_includes_claude_code(self) -> None:
        """Test that claude-code is in the list of adapters."""
        adapters = list_adapters()
        assert "claude-code" in adapters
