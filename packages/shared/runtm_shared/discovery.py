"""App discovery metadata for searchability and reuse.

This module defines the schema for runtm.discovery.yaml, which allows
agents to describe deployed apps for discoverability.

Design principles:
- Agent-writable (not in .cursorignore)
- Optional with warning at deploy (never blocks)
- Template-specific guidance (OpenAPI for APIs, not static sites)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict


class ApiDiscovery(BaseModel):
    """API-specific discovery info (for backend-service, web-app)."""

    model_config = ConfigDict(extra="allow")

    openapi_path: str = "/openapi.json"
    endpoints: Optional[List[str]] = None


class GeneratedInfo(BaseModel):
    """Metadata about when/how the discovery file was generated."""

    model_config = ConfigDict(extra="allow")

    by: Optional[str] = None  # cursor, claude-code, github-copilot, etc.
    at: Optional[datetime] = None


class AppDiscovery(BaseModel):
    """App discovery metadata for searchability and reuse.

    Example runtm.discovery.yaml:
        description: |
          A webhook processor that receives Stripe events and updates
          user subscription status in real-time.

        summary: Stripe webhook handler for subscription management

        capabilities:
          - Processes Stripe webhook events
          - Validates webhook signatures

        use_cases:
          - SaaS billing integration
          - Subscription lifecycle management

        tags:
          - stripe
          - webhooks
          - billing

        api:
          openapi_path: /openapi.json

        generated:
          by: cursor
          at: 2024-12-29T10:30:00Z
    """

    model_config = ConfigDict(extra="allow")

    description: Optional[str] = None
    summary: Optional[str] = None
    capabilities: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    api: Optional[ApiDiscovery] = None
    generated: Optional[GeneratedInfo] = None

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "AppDiscovery":
        """Parse discovery metadata from YAML string.

        Args:
            yaml_content: YAML content as string

        Returns:
            Parsed AppDiscovery object

        Raises:
            ValueError: If YAML is invalid
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

        if data is None:
            return cls()

        if not isinstance(data, dict):
            raise ValueError("Discovery file must be a YAML dictionary")

        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: Path) -> "AppDiscovery":
        """Parse discovery metadata from file.

        Args:
            path: Path to runtm.discovery.yaml file

        Returns:
            Parsed AppDiscovery object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def to_yaml(self) -> str:
        """Serialize discovery metadata to YAML string.

        Returns:
            YAML representation of the discovery metadata
        """
        data = self.model_dump(exclude_none=True)
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    def is_empty(self) -> bool:
        """Check if discovery metadata is effectively empty (all TODOs or None).

        Returns:
            True if no meaningful content has been added
        """
        # Check if description is empty or just TODO
        if self.description and "TODO" not in self.description:
            return False
        if self.summary and "TODO" not in str(self.summary):
            return False
        if self.capabilities and len(self.capabilities) > 0:
            # Check if any capability is not a TODO
            for cap in self.capabilities:
                if "TODO" not in cap:
                    return False
        if self.tags and len(self.tags) > 0:
            return False
        return True

