"""Tests for sandbox state persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from runtm_shared.types import (
    AgentType,
    GuardrailsConfig,
    NetworkConfig,
    Sandbox,
    SandboxConfig,
    SandboxState,
)


@pytest.fixture
def temp_state_dir() -> Path:
    """Create a temporary directory for state storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_sandbox() -> Sandbox:
    """Create a sample sandbox for testing."""
    return Sandbox(
        id="sbx_test123",
        session_id="sbx_test123",
        config=SandboxConfig(
            agent=AgentType.CLAUDE_CODE,
            template="backend-service",
        ),
        state=SandboxState.RUNNING,
        workspace_path="/tmp/workspace",
    )


@pytest.fixture
def state_store(temp_state_dir: Path):
    """Create a SandboxStateStore with temporary directory."""
    from runtm_sandbox.state import SandboxStateStore

    store = SandboxStateStore(state_dir=temp_state_dir)
    return store


class TestSandboxStateStore:
    """Tests for SandboxStateStore."""

    def test_save_creates_state_file(
        self, state_store, sample_sandbox: Sandbox, temp_state_dir: Path
    ) -> None:
        """Should create a state.json file for the sandbox."""
        state_store.save(sample_sandbox)

        state_file = temp_state_dir / sample_sandbox.id / "state.json"
        assert state_file.exists()

    def test_save_writes_valid_json(
        self, state_store, sample_sandbox: Sandbox, temp_state_dir: Path
    ) -> None:
        """Should write valid JSON that can be parsed."""
        state_store.save(sample_sandbox)

        state_file = temp_state_dir / sample_sandbox.id / "state.json"
        data = json.loads(state_file.read_text())

        assert data["id"] == sample_sandbox.id
        assert data["state"] == "running"
        assert data["workspace_path"] == "/tmp/workspace"

    def test_load_returns_sandbox(self, state_store, sample_sandbox: Sandbox) -> None:
        """Should load a saved sandbox correctly."""
        state_store.save(sample_sandbox)

        loaded = state_store.load(sample_sandbox.id)

        assert loaded is not None
        assert loaded.id == sample_sandbox.id
        assert loaded.state == SandboxState.RUNNING
        assert loaded.config.agent == AgentType.CLAUDE_CODE

    def test_load_returns_none_for_nonexistent(self, state_store) -> None:
        """Should return None for non-existent sandbox."""
        loaded = state_store.load("sbx_nonexistent")
        assert loaded is None

    def test_delete_removes_state_file(
        self, state_store, sample_sandbox: Sandbox, temp_state_dir: Path
    ) -> None:
        """Should delete the state file."""
        state_store.save(sample_sandbox)
        state_file = temp_state_dir / sample_sandbox.id / "state.json"
        assert state_file.exists()

        state_store.delete(sample_sandbox.id)

        assert not state_file.exists()

    def test_delete_handles_nonexistent(self, state_store) -> None:
        """Should not raise error when deleting non-existent sandbox."""
        # Should not raise
        state_store.delete("sbx_nonexistent")

    def test_list_all_returns_all_sandboxes(self, state_store) -> None:
        """Should list all saved sandboxes."""
        sandbox1 = Sandbox(
            id="sbx_001",
            session_id="sbx_001",
            config=SandboxConfig(),
            state=SandboxState.RUNNING,
            workspace_path="/tmp/ws1",
        )
        sandbox2 = Sandbox(
            id="sbx_002",
            session_id="sbx_002",
            config=SandboxConfig(),
            state=SandboxState.STOPPED,
            workspace_path="/tmp/ws2",
        )

        state_store.save(sandbox1)
        state_store.save(sandbox2)

        all_sandboxes = state_store.list_all()

        assert len(all_sandboxes) == 2
        ids = {s.id for s in all_sandboxes}
        assert ids == {"sbx_001", "sbx_002"}

    def test_list_all_returns_empty_when_no_sandboxes(self, state_store) -> None:
        """Should return empty list when no sandboxes exist."""
        all_sandboxes = state_store.list_all()
        assert all_sandboxes == []

    def test_update_sandbox_state(self, state_store, sample_sandbox: Sandbox) -> None:
        """Should update sandbox state when saved again."""
        state_store.save(sample_sandbox)

        # Update state
        sample_sandbox.state = SandboxState.STOPPED
        state_store.save(sample_sandbox)

        loaded = state_store.load(sample_sandbox.id)
        assert loaded is not None
        assert loaded.state == SandboxState.STOPPED

    def test_preserves_complex_config(self, state_store) -> None:
        """Should preserve complex configuration through save/load cycle."""
        sandbox = Sandbox(
            id="sbx_complex",
            session_id="sbx_complex",
            config=SandboxConfig(
                agent=AgentType.CODEX,
                template="web-app",
                guardrails=GuardrailsConfig(
                    network=NetworkConfig(
                        enabled=True,
                        allow_domains=["custom.example.com", "api.test.com"],
                    ),
                    allow_write_paths=[".", "output/"],
                    deny_write_paths=["secrets/"],
                    timeout_minutes=30,
                ),
                port_mappings={3000: 3001, 8080: 8081},
            ),
            state=SandboxState.RUNNING,
            workspace_path="/home/user/workspace",
        )

        state_store.save(sandbox)
        loaded = state_store.load(sandbox.id)

        assert loaded is not None
        assert loaded.config.agent == AgentType.CODEX
        assert loaded.config.template == "web-app"
        assert loaded.config.guardrails.timeout_minutes == 30
        assert "custom.example.com" in loaded.config.guardrails.network.allow_domains
        assert loaded.config.port_mappings[3000] == 3001


class TestSandboxStateStoreEdgeCases:
    """Edge case tests for SandboxStateStore."""

    def test_handles_corrupted_json(self, state_store, temp_state_dir: Path) -> None:
        """Should handle corrupted JSON gracefully."""
        sandbox_dir = temp_state_dir / "sbx_corrupted"
        sandbox_dir.mkdir(parents=True)
        (sandbox_dir / "state.json").write_text("{ invalid json }")

        loaded = state_store.load("sbx_corrupted")
        assert loaded is None

    def test_handles_missing_fields_in_json(self, state_store, temp_state_dir: Path) -> None:
        """Should handle JSON with missing fields."""
        sandbox_dir = temp_state_dir / "sbx_partial"
        sandbox_dir.mkdir(parents=True)
        (sandbox_dir / "state.json").write_text('{"id": "sbx_partial"}')

        # Should not crash, but may return None or raise appropriate error
        state_store.load("sbx_partial")
        # Implementation can choose to return None or raise - either is acceptable
        # The important thing is it doesn't crash unexpectedly

    def test_ignores_non_sandbox_directories(self, state_store, temp_state_dir: Path) -> None:
        """Should ignore directories without state.json."""
        # Create a random directory
        (temp_state_dir / "random_dir").mkdir()
        (temp_state_dir / "another_file.txt").write_text("not a sandbox")

        # Should not include these in listing
        all_sandboxes = state_store.list_all()
        assert all_sandboxes == []
