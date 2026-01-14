"""Sandbox and session state persistence.

Stores sandbox metadata in ~/.runtm/sandboxes/{sandbox_id}/state.json
Stores session metadata in ~/.runtm/sandboxes/{session_id}/session.json
Tracks active session in ~/.runtm/active_session
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
    Session,
    SessionConstraints,
    SessionMode,
    SessionState,
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

    # =========================================================================
    # Session persistence methods
    # =========================================================================

    def save_session(self, session: Session) -> None:
        """Save session state to disk.

        Args:
            session: Session to save.
        """
        session_dir = self.state_dir / session.id
        session_dir.mkdir(parents=True, exist_ok=True)

        session_file = session_dir / "session.json"
        data = _serialize_session(session)

        session_file.write_text(json.dumps(data, indent=2))
        logger.debug("Saved session state", session_id=session.id, path=str(session_file))

    def load_session(self, session_id: str) -> Session | None:
        """Load session state from disk.

        Args:
            session_id: ID of session to load.

        Returns:
            Session object, or None if not found or corrupted.
        """
        session_file = self.state_dir / session_id / "session.json"

        if not session_file.exists():
            logger.debug("Session state file not found", session_id=session_id)
            return None

        try:
            data = json.loads(session_file.read_text())
            session = _deserialize_session(data)
            logger.debug("Loaded session state", session_id=session_id)
            return session
        except json.JSONDecodeError as e:
            logger.warning("Corrupted session state file", session_id=session_id, error=str(e))
            return None
        except (KeyError, ValueError) as e:
            logger.warning("Invalid session state data", session_id=session_id, error=str(e))
            return None

    def delete_session(self, session_id: str) -> None:
        """Delete session state from disk.

        Args:
            session_id: ID of session to delete.
        """
        session_file = self.state_dir / session_id / "session.json"

        if session_file.exists():
            session_file.unlink()
            logger.debug("Deleted session state", session_id=session_id)

    def list_sessions(self) -> list[Session]:
        """List all sessions.

        Returns:
            List of all valid sessions, sorted by created_at (newest first).
        """
        sessions: list[Session] = []

        if not self.state_dir.exists():
            return sessions

        for session_dir in self.state_dir.iterdir():
            if not session_dir.is_dir():
                continue

            session_file = session_dir / "session.json"
            if not session_file.exists():
                continue

            session = self.load_session(session_dir.name)
            if session is not None:
                sessions.append(session)

        # Sort by created_at descending (newest first)
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions


def _serialize_session(session: Session) -> dict:
    """Serialize a Session to a JSON-compatible dict."""
    data = asdict(session)

    # Convert enums to strings
    data["mode"] = session.mode.value
    data["state"] = session.state.value
    data["agent"] = session.agent.value

    # Convert datetimes to ISO format
    if isinstance(data["created_at"], datetime):
        data["created_at"] = data["created_at"].isoformat()
    if isinstance(data["updated_at"], datetime):
        data["updated_at"] = data["updated_at"].isoformat()

    return data


def _deserialize_session(data: dict) -> Session:
    """Deserialize a dict to a Session object."""
    # Parse constraints
    constraints_data = data.get("constraints", {})
    constraints = SessionConstraints(
        allow_deploy=constraints_data.get("allow_deploy", True),
        allow_network=constraints_data.get("allow_network", True),
        allow_install=constraints_data.get("allow_install", True),
    )

    # Parse datetimes
    created_at_str = data.get("created_at")
    if isinstance(created_at_str, str):
        created_at = datetime.fromisoformat(created_at_str)
    else:
        created_at = datetime.now(tz=None)

    updated_at_str = data.get("updated_at")
    if isinstance(updated_at_str, str):
        updated_at = datetime.fromisoformat(updated_at_str)
    else:
        updated_at = datetime.now(tz=None)

    return Session(
        id=data["id"],
        name=data.get("name"),
        mode=SessionMode(data.get("mode", "autopilot")),
        state=SessionState(data.get("state", "running")),
        agent=AgentType(data.get("agent", "claude-code")),
        sandbox_id=data.get("sandbox_id", ""),
        workspace_path=data.get("workspace_path", ""),
        initial_prompt=data.get("initial_prompt"),
        claude_session_id=data.get("claude_session_id"),
        constraints=constraints,
        created_at=created_at,
        updated_at=updated_at,
    )


class ActiveSessionTracker:
    """Track the currently active session.

    Stores the active session ID in ~/.runtm/active_session (global)
    and per-terminal sessions in ~/.runtm/terminal_sessions/{terminal_id}.
    Used by `runtm prompt` and `runtm attach` to target sessions by default.
    """

    def __init__(self, state_dir: Path | None = None):
        """Initialize the tracker.

        Args:
            state_dir: Base state directory. Defaults to ~/.runtm/
        """
        if state_dir is None:
            state_dir = Path.home() / ".runtm"

        self.state_dir = state_dir
        self.active_file = self.state_dir / "active_session"
        self.sandboxes_dir = self.state_dir / "sandboxes"
        self.terminal_sessions_dir = self.state_dir / "terminal_sessions"

    def _get_terminal_id(self) -> str | None:
        """Get a unique identifier for the current terminal session.

        Uses TERM_SESSION_ID (macOS Terminal/iTerm2), WINDOWID (X11),
        or falls back to TTY device name.

        Returns:
            Terminal identifier string, or None if not in a terminal.
        """
        import hashlib
        import os
        import sys

        # Try macOS Terminal.app / iTerm2 session ID
        term_session = os.environ.get("TERM_SESSION_ID")
        if term_session:
            return hashlib.sha256(term_session.encode()).hexdigest()[:16]

        # Try X11 window ID
        window_id = os.environ.get("WINDOWID")
        if window_id:
            return hashlib.sha256(window_id.encode()).hexdigest()[:16]

        # Fall back to TTY device name
        try:
            if sys.stdout.isatty():
                tty_name = os.ttyname(sys.stdout.fileno())
                return hashlib.sha256(tty_name.encode()).hexdigest()[:16]
        except (OSError, AttributeError):
            pass

        return None

    def set_active(self, session_id: str) -> None:
        """Set the active session (both global and per-terminal).

        Args:
            session_id: Session ID to set as active.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Set global active session
        self.active_file.write_text(session_id)
        logger.debug("Set global active session", session_id=session_id)

        # Set per-terminal active session
        terminal_id = self._get_terminal_id()
        if terminal_id:
            self.terminal_sessions_dir.mkdir(parents=True, exist_ok=True)
            terminal_file = self.terminal_sessions_dir / terminal_id
            terminal_file.write_text(session_id)
            logger.debug(
                "Set terminal active session",
                session_id=session_id,
                terminal_id=terminal_id,
            )

    def get_active(self, terminal_only: bool = False) -> str | None:
        """Get the active session ID.

        Checks for a per-terminal session first, then falls back to global.

        Args:
            terminal_only: If True, only return terminal-specific session.

        Returns:
            Session ID if one is active and valid, None otherwise.
        """
        # First, try per-terminal session
        terminal_id = self._get_terminal_id()
        if terminal_id:
            terminal_file = self.terminal_sessions_dir / terminal_id
            if terminal_file.exists():
                session_id = terminal_file.read_text().strip()
                if session_id:
                    # Verify session still exists
                    session_file = self.sandboxes_dir / session_id / "session.json"
                    if session_file.exists():
                        logger.debug(
                            "Found terminal active session",
                            session_id=session_id,
                            terminal_id=terminal_id,
                        )
                        return session_id
                    else:
                        # Clean up stale terminal session
                        terminal_file.unlink()
                        logger.debug(
                            "Cleaned up stale terminal session",
                            terminal_id=terminal_id,
                        )

        if terminal_only:
            return None

        # Fall back to global active session
        if not self.active_file.exists():
            return None

        session_id = self.active_file.read_text().strip()
        if not session_id:
            return None

        # Verify session still exists
        session_file = self.sandboxes_dir / session_id / "session.json"
        if not session_file.exists():
            logger.debug("Active session no longer exists", session_id=session_id)
            self.clear_active()
            return None

        return session_id

    def clear_active(self) -> None:
        """Clear the active session (both global and per-terminal)."""
        if self.active_file.exists():
            self.active_file.unlink()
            logger.debug("Cleared global active session")

        # Clear per-terminal session
        terminal_id = self._get_terminal_id()
        if terminal_id:
            terminal_file = self.terminal_sessions_dir / terminal_id
            if terminal_file.exists():
                terminal_file.unlink()
                logger.debug("Cleared terminal active session", terminal_id=terminal_id)
