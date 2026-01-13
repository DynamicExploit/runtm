"""Sandbox state persistence.

Stores sandbox metadata in ~/.runtm/sandboxes/{sandbox_id}/state.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import structlog
from runtm_shared.types import (
    AgentType,
    GuardrailsConfig,
    NetworkConfig,
    Sandbox,
    SandboxConfig,
    SandboxState,
)

logger = structlog.get_logger()


def _serialize_sandbox(sandbox: Sandbox) -> dict:
    """Serialize a Sandbox to a JSON-compatible dict."""
    data = asdict(sandbox)

    # Convert enums to strings
    data["state"] = sandbox.state.value
    data["config"]["agent"] = sandbox.config.agent.value

    # Convert datetime to ISO format
    if isinstance(data["created_at"], datetime):
        data["created_at"] = data["created_at"].isoformat()

    return data


def _deserialize_sandbox(data: dict) -> Sandbox:
    """Deserialize a dict to a Sandbox object."""
    # Parse nested config
    config_data = data.get("config", {})
    guardrails_data = config_data.get("guardrails", {})
    network_data = guardrails_data.get("network", {})

    network_config = NetworkConfig(
        enabled=network_data.get("enabled", True),
        allow_domains=network_data.get("allow_domains", []),
    )

    guardrails_config = GuardrailsConfig(
        network=network_config,
        allow_write_paths=guardrails_data.get("allow_write_paths", ["."]),
        deny_write_paths=guardrails_data.get("deny_write_paths", []),
        timeout_minutes=guardrails_data.get("timeout_minutes", 60),
    )

    # Convert port_mappings keys from strings to ints (JSON only supports string keys)
    raw_port_mappings = config_data.get("port_mappings", {"3000": 3000, "8080": 8080})
    port_mappings = {int(k): v for k, v in raw_port_mappings.items()}

    sandbox_config = SandboxConfig(
        agent=AgentType(config_data.get("agent", "claude-code")),
        template=config_data.get("template"),
        guardrails=guardrails_config,
        port_mappings=port_mappings,
    )

    # Parse created_at
    created_at_str = data.get("created_at")
    if isinstance(created_at_str, str):
        created_at = datetime.fromisoformat(created_at_str)
    else:
        created_at = datetime.now(tz=None)

    return Sandbox(
        id=data["id"],
        session_id=data.get("session_id", data["id"]),
        config=sandbox_config,
        state=SandboxState(data.get("state", "running")),
        workspace_path=data.get("workspace_path", ""),
        created_at=created_at,
        pid=data.get("pid"),
    )


class SandboxStateStore:
    """Persist sandbox state to filesystem.

    Stores each sandbox's state in:
    {state_dir}/{sandbox_id}/state.json
    """

    def __init__(self, state_dir: Path | None = None):
        """Initialize the state store.

        Args:
            state_dir: Directory to store state files.
                       Defaults to ~/.runtm/sandboxes/
        """
        if state_dir is None:
            state_dir = Path.home() / ".runtm" / "sandboxes"

        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save(self, sandbox: Sandbox) -> None:
        """Save sandbox state to disk.

        Args:
            sandbox: Sandbox to save.
        """
        sandbox_dir = self.state_dir / sandbox.id
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        state_file = sandbox_dir / "state.json"
        data = _serialize_sandbox(sandbox)

        state_file.write_text(json.dumps(data, indent=2))
        logger.debug("Saved sandbox state", sandbox_id=sandbox.id, path=str(state_file))

    def load(self, sandbox_id: str) -> Sandbox | None:
        """Load sandbox state from disk.

        Args:
            sandbox_id: ID of sandbox to load.

        Returns:
            Sandbox object, or None if not found or corrupted.
        """
        state_file = self.state_dir / sandbox_id / "state.json"

        if not state_file.exists():
            logger.debug("Sandbox state file not found", sandbox_id=sandbox_id)
            return None

        try:
            data = json.loads(state_file.read_text())
            sandbox = _deserialize_sandbox(data)
            logger.debug("Loaded sandbox state", sandbox_id=sandbox_id)
            return sandbox
        except json.JSONDecodeError as e:
            logger.warning("Corrupted sandbox state file", sandbox_id=sandbox_id, error=str(e))
            return None
        except (KeyError, ValueError) as e:
            logger.warning("Invalid sandbox state data", sandbox_id=sandbox_id, error=str(e))
            return None

    def delete(self, sandbox_id: str) -> None:
        """Delete sandbox state from disk.

        Args:
            sandbox_id: ID of sandbox to delete.
        """
        state_file = self.state_dir / sandbox_id / "state.json"

        if state_file.exists():
            state_file.unlink()
            logger.debug("Deleted sandbox state", sandbox_id=sandbox_id)

    def list_all(self) -> list[Sandbox]:
        """List all sandboxes.

        Returns:
            List of all valid sandboxes.
        """
        sandboxes: list[Sandbox] = []

        if not self.state_dir.exists():
            return sandboxes

        for sandbox_dir in self.state_dir.iterdir():
            if not sandbox_dir.is_dir():
                continue

            state_file = sandbox_dir / "state.json"
            if not state_file.exists():
                continue

            sandbox = self.load(sandbox_dir.name)
            if sandbox is not None:
                sandboxes.append(sandbox)

        return sandboxes
