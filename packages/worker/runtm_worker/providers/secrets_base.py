"""Abstract provider interface for secrets injection.

Follows the same pattern as DeployProvider in base.py.
Secrets are passed through to the provider, never persisted in Runtm DB.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SecretSetResult:
    """Result of setting secrets on a provider."""

    success: bool
    error: Optional[str] = None
    secrets_set: int = 0  # Count of secrets successfully set


@dataclass
class SecretListResult:
    """Result of listing secret names from a provider."""

    success: bool
    names: List[str] = None  # Only names, never values
    error: Optional[str] = None

    def __post_init__(self):
        if self.names is None:
            self.names = []


class SecretsProvider(ABC):
    """Abstract interface for secrets injection.

    Implementations:
        - FlySecretsProvider: Fly.io secrets via flyctl (v1)
        - CloudRunSecretsProvider: GCP Secret Manager (future)
        - VaultSecretsProvider: HashiCorp Vault (future)

    Security guarantees:
        - Secret VALUES are never persisted to Runtm database
        - Secret VALUES are never logged
        - Only secret NAMES are stored for validation purposes
        - Secrets are passed directly to the provider in memory
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'fly', 'cloudrun', 'vault')."""
        ...

    @abstractmethod
    def set_secrets(
        self,
        app_name: str,
        secrets: Dict[str, str],
    ) -> SecretSetResult:
        """Set secrets for an app.

        Secrets are passed directly to the provider and never persisted
        in the Runtm database.

        Args:
            app_name: Target app identifier (provider-specific)
            secrets: Key-value pairs to set (values in memory only)

        Returns:
            SecretSetResult with success/error status
        """
        ...

    @abstractmethod
    def get_secret_names(self, app_name: str) -> SecretListResult:
        """List secret names (NOT values) for an app.

        Only returns the names of secrets that are set, never the values.
        This is safe to store and log.

        Args:
            app_name: Target app identifier

        Returns:
            SecretListResult with list of secret names
        """
        ...

    @abstractmethod
    def delete_secrets(
        self,
        app_name: str,
        names: List[str],
    ) -> SecretSetResult:
        """Remove secrets from an app.

        Args:
            app_name: Target app identifier
            names: Secret names to delete

        Returns:
            SecretSetResult with success/error status
        """
        ...

    def sync_secrets(
        self,
        app_name: str,
        secrets: Dict[str, str],
        delete_missing: bool = False,
    ) -> SecretSetResult:
        """Sync secrets to match the provided set.

        Sets all provided secrets. Optionally deletes secrets that exist
        on the provider but are not in the provided set.

        Args:
            app_name: Target app identifier
            secrets: Key-value pairs representing desired state
            delete_missing: If True, delete secrets not in the provided set

        Returns:
            SecretSetResult with success/error status
        """
        # Set all provided secrets
        result = self.set_secrets(app_name, secrets)
        if not result.success:
            return result

        # Optionally delete secrets not in the provided set
        if delete_missing:
            existing = self.get_secret_names(app_name)
            if existing.success:
                to_delete = [n for n in existing.names if n not in secrets]
                if to_delete:
                    delete_result = self.delete_secrets(app_name, to_delete)
                    if not delete_result.success:
                        return SecretSetResult(
                            success=False,
                            error=f"Set succeeded but delete failed: {delete_result.error}",
                            secrets_set=result.secrets_set,
                        )

        return result

