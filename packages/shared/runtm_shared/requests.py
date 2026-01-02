"""Pydantic models for runtm.requests.yaml - agent-proposed changes.

The requests file allows AI agents to propose changes (env vars, egress,
connections, features) that require human approval before deploy.

In v1, this is informational only (warn, don't block). In org mode,
approval may be required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from runtm_shared.manifest import EnvVar, EnvVarType


class RequestedFeatures(BaseModel):
    """Features requested by the agent.

    Allows agents to enable optional template features like database and auth.
    """

    model_config = ConfigDict(extra="forbid")

    database: bool | None = None
    auth: bool | None = None
    reason: str | None = None  # Why the agent needs these features

    def has_changes(self) -> bool:
        """Check if any features are being requested."""
        return self.database is not None or self.auth is not None


class RequestedEnvVar(BaseModel):
    """An env var requested by the agent.

    Similar to EnvVar but includes a 'reason' field explaining why it's needed.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    type: EnvVarType = EnvVarType.STRING
    required: bool = False
    secret: bool = False
    description: str | None = None
    reason: str | None = None  # Why the agent needs this

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate env var name format."""
        if not v:
            raise ValueError("env var name cannot be empty")
        if not v.replace("_", "").isalnum():
            raise ValueError("env var name must be alphanumeric with underscores")
        if not v[0].isalpha():
            raise ValueError("env var name must start with a letter")
        return v

    def to_env_var(self) -> EnvVar:
        """Convert to a manifest EnvVar (drops reason field)."""
        return EnvVar(
            name=self.name,
            type=self.type,
            required=self.required,
            secret=self.secret,
            description=self.description,
        )


class RequestedConnection(BaseModel):
    """A connection requested by the agent."""

    model_config = ConfigDict(extra="forbid")

    name: str
    env_vars: list[str]
    reason: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate connection name format."""
        if not v:
            raise ValueError("connection name cannot be empty")
        return v.lower()


class RequestedChanges(BaseModel):
    """Changes requested by the agent."""

    model_config = ConfigDict(extra="forbid")

    features: RequestedFeatures | None = None
    env_vars: list[RequestedEnvVar] = []
    egress_allowlist: list[str] = []
    connections: list[RequestedConnection] = []


class RequestsFile(BaseModel):
    """Schema for runtm.requests.yaml - agent-proposed changes.

    Example:
        requested:
          features:
            database: true
            auth: true
            reason: "App needs user accounts and data persistence"
          env_vars:
            - name: AUTH_SECRET
              type: string
              secret: true
              required: true
              reason: "Required for auth feature"
            - name: ALPHAVANTAGE_API_KEY
              type: string
              secret: true
              required: false
              reason: "Optional API for stock data"
          egress_allowlist:
            - "api.alphavantage.co"
          connections:
            - name: alpha_vantage
              env_vars: [ALPHAVANTAGE_API_KEY]
        notes:
          - "Default impl scrapes Yahoo; API is more stable"
    """

    model_config = ConfigDict(extra="forbid")

    requested: RequestedChanges = RequestedChanges()
    notes: list[str] = []

    @classmethod
    def from_yaml(cls, yaml_content: str) -> RequestsFile:
        """Parse requests file from YAML string.

        Args:
            yaml_content: YAML content as string

        Returns:
            Parsed RequestsFile object

        Raises:
            ValueError: If YAML is invalid or validation fails
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Requests file must be a YAML dictionary")

        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: Path) -> RequestsFile:
        """Parse requests file from disk.

        Args:
            path: Path to runtm.requests.yaml

        Returns:
            Parsed RequestsFile object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or validation fails
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def to_yaml(self) -> str:
        """Serialize to YAML string.

        Returns:
            YAML representation of the requests file
        """
        data = self.to_dict()
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        data: dict[str, Any] = {"requested": {}}

        if self.requested.features and self.requested.features.has_changes():
            features_dict = {}
            if self.requested.features.database is not None:
                features_dict["database"] = self.requested.features.database
            if self.requested.features.auth is not None:
                features_dict["auth"] = self.requested.features.auth
            if self.requested.features.reason:
                features_dict["reason"] = self.requested.features.reason
            data["requested"]["features"] = features_dict

        if self.requested.env_vars:
            data["requested"]["env_vars"] = [
                {k: v for k, v in ev.model_dump(mode="json").items() if v is not None}
                for ev in self.requested.env_vars
            ]

        if self.requested.egress_allowlist:
            data["requested"]["egress_allowlist"] = self.requested.egress_allowlist

        if self.requested.connections:
            data["requested"]["connections"] = [
                {k: v for k, v in conn.model_dump(mode="json").items() if v is not None}
                for conn in self.requested.connections
            ]

        if self.notes:
            data["notes"] = self.notes

        return data

    def is_empty(self) -> bool:
        """Check if there are no pending requests."""
        has_features = self.requested.features and self.requested.features.has_changes()
        return (
            not has_features
            and not self.requested.env_vars
            and not self.requested.egress_allowlist
            and not self.requested.connections
        )

    def get_summary(self) -> str:
        """Get a human-readable summary of pending requests."""
        parts = []
        if self.requested.features and self.requested.features.has_changes():
            feature_parts = []
            if self.requested.features.database:
                feature_parts.append("database")
            if self.requested.features.auth:
                feature_parts.append("auth")
            if feature_parts:
                parts.append(f"features: {', '.join(feature_parts)}")
        if self.requested.env_vars:
            parts.append(f"{len(self.requested.env_vars)} env vars")
        if self.requested.egress_allowlist:
            parts.append(f"{len(self.requested.egress_allowlist)} egress domains")
        if self.requested.connections:
            parts.append(f"{len(self.requested.connections)} connections")

        if not parts:
            return "No pending requests"

        return f"Pending: {', '.join(parts)}"
