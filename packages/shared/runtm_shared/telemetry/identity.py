"""Identity management for telemetry correlation.

Manages install_id (persistent per-machine) and session_id (per-invocation).
"""

from __future__ import annotations

import json
import platform
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class TelemetryIdentity(BaseModel):
    """Persistent telemetry identity stored on disk."""

    install_id: str = Field(description="Unique ID for this installation")
    last_version: Optional[str] = Field(default=None, description="Last CLI version seen")
    first_run_sent: bool = Field(default=False, description="Whether first_run event was sent")


class IdentityManager:
    """Manages telemetry identity (install_id, session_id).

    - install_id: Random UUID generated once, stored in ~/.runtm/telemetry.json
    - session_id: Random UUID generated per CLI invocation
    - Detects first run and version upgrades
    """

    DEFAULT_PATH = Path.home() / ".runtm" / "telemetry.json"

    def __init__(self, identity_path: Optional[Path] = None) -> None:
        """Initialize identity manager.

        Args:
            identity_path: Path to identity file (defaults to ~/.runtm/telemetry.json)
        """
        self._identity_path = identity_path or self.DEFAULT_PATH
        self._identity: Optional[TelemetryIdentity] = None
        self._session_id: str = str(uuid.uuid4())
        self._is_first_run: bool = False
        self._previous_version: Optional[str] = None

    @property
    def install_id(self) -> str:
        """Get or create the installation ID."""
        if self._identity is None:
            self._load_or_create_identity()
        assert self._identity is not None
        return self._identity.install_id

    @property
    def session_id(self) -> str:
        """Get the session ID (unique per CLI invocation)."""
        return self._session_id

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run (install_id was just created)."""
        if self._identity is None:
            self._load_or_create_identity()
        return self._is_first_run

    @property
    def previous_version(self) -> Optional[str]:
        """Get the previous CLI version (for upgrade detection)."""
        if self._identity is None:
            self._load_or_create_identity()
        return self._previous_version

    def mark_first_run_sent(self) -> None:
        """Mark that the first_run event has been sent."""
        if self._identity is None:
            self._load_or_create_identity()
        assert self._identity is not None
        self._identity.first_run_sent = True
        self._save_identity()

    def update_version(self, current_version: str) -> None:
        """Update the stored version after detecting an upgrade.

        Args:
            current_version: The current CLI version
        """
        if self._identity is None:
            self._load_or_create_identity()
        assert self._identity is not None
        self._identity.last_version = current_version
        self._save_identity()

    def should_send_first_run(self) -> bool:
        """Check if we should send the first_run event."""
        if self._identity is None:
            self._load_or_create_identity()
        assert self._identity is not None
        return self._is_first_run and not self._identity.first_run_sent

    def is_upgrade(self, current_version: str) -> bool:
        """Check if this is a version upgrade.

        Args:
            current_version: The current CLI version

        Returns:
            True if upgrading from a different version
        """
        if self._identity is None:
            self._load_or_create_identity()
        return self._previous_version is not None and self._previous_version != current_version

    def get_system_info(self) -> dict[str, str]:
        """Get system information for first_run event.

        Returns:
            Dict with os, arch, python_version
        """
        return {
            "os": platform.system().lower(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
        }

    def _load_or_create_identity(self) -> None:
        """Load existing identity or create a new one."""
        if self._identity_path.exists():
            try:
                data = json.loads(self._identity_path.read_text())
                self._identity = TelemetryIdentity.model_validate(data)
                self._previous_version = self._identity.last_version
                self._is_first_run = False
            except (json.JSONDecodeError, ValueError):
                # Corrupted file, recreate
                self._create_new_identity()
        else:
            self._create_new_identity()

    def _create_new_identity(self) -> None:
        """Create a new identity."""
        self._identity = TelemetryIdentity(
            install_id=str(uuid.uuid4()),
            last_version=None,
            first_run_sent=False,
        )
        self._is_first_run = True
        self._previous_version = None
        self._save_identity()

    def _save_identity(self) -> None:
        """Save identity to disk."""
        if self._identity is None:
            return

        try:
            self._identity_path.parent.mkdir(parents=True, exist_ok=True)
            self._identity_path.write_text(json.dumps(self._identity.model_dump(), indent=2))
        except OSError:
            # Best effort - don't fail if we can't write
            pass
