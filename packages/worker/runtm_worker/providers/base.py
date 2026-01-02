"""Abstract provider interface for deployment backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from runtm_shared.types import CustomDomainInfo, MachineConfig, ProviderResource


@dataclass
class DeployResult:
    """Result of a deployment operation."""

    success: bool
    resource: Optional[ProviderResource] = None
    error: Optional[str] = None
    logs: str = ""


@dataclass
class ProviderStatus:
    """Status of a deployed resource."""

    state: str  # running, stopped, starting, failed
    healthy: bool
    url: Optional[str] = None
    error: Optional[str] = None


class DeployProvider(ABC):
    """Abstract interface for deployment providers.

    Implementations:
        - FlyProvider: Fly.io Machines
        - CloudRunProvider: Google Cloud Run (future)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'fly', 'cloudrun')."""
        ...

    @abstractmethod
    def deploy(
        self,
        deployment_id: str,
        config: MachineConfig,
    ) -> DeployResult:
        """Deploy a container to the provider.

        Args:
            deployment_id: Unique deployment identifier
            config: Machine configuration

        Returns:
            DeployResult with provider resource mapping or error
        """
        ...

    @abstractmethod
    def redeploy(
        self,
        resource: ProviderResource,
        config: MachineConfig,
    ) -> DeployResult:
        """Redeploy an existing resource with a new image/config.

        Updates an existing deployment rather than creating a new one.
        The URL and app name remain stable.

        Args:
            resource: Existing provider resource to update
            config: New machine configuration

        Returns:
            DeployResult with updated provider resource or error
        """
        ...

    @abstractmethod
    def get_status(self, resource: ProviderResource) -> ProviderStatus:
        """Get status of a deployed resource.

        Args:
            resource: Provider resource from previous deploy

        Returns:
            Current status of the resource
        """
        ...

    @abstractmethod
    def destroy(self, resource: ProviderResource) -> bool:
        """Tear down a deployed resource.

        Args:
            resource: Provider resource to destroy

        Returns:
            True if successfully destroyed
        """
        ...

    @abstractmethod
    def get_logs(
        self,
        resource: ProviderResource,
        lines: int = 100,
    ) -> str:
        """Get runtime logs from a deployed resource.

        Args:
            resource: Provider resource
            lines: Number of lines to retrieve

        Returns:
            Log content as string
        """
        ...

    def health_check(
        self,
        resource: ProviderResource,
        path: str = "/health",
        timeout_seconds: int = 30,
    ) -> bool:
        """Check if deployed resource is healthy.

        Default implementation calls get_status.
        Providers may override for direct HTTP health checks.

        Args:
            resource: Provider resource
            path: Health check path
            timeout_seconds: Timeout for health check

        Returns:
            True if healthy
        """
        status = self.get_status(resource)
        return status.healthy

    @abstractmethod
    def add_custom_domain(
        self,
        resource: ProviderResource,
        hostname: str,
    ) -> CustomDomainInfo:
        """Add a custom domain to a deployed resource.

        Creates a certificate for the hostname and returns DNS configuration.

        Args:
            resource: Provider resource (must be deployed)
            hostname: Custom domain (e.g., "api.example.com")

        Returns:
            CustomDomainInfo with DNS records and certificate status
        """
        ...

    @abstractmethod
    def get_custom_domain_status(
        self,
        resource: ProviderResource,
        hostname: str,
    ) -> CustomDomainInfo:
        """Get status of a custom domain configuration.

        Args:
            resource: Provider resource
            hostname: Custom domain to check

        Returns:
            CustomDomainInfo with current status
        """
        ...

    @abstractmethod
    def remove_custom_domain(
        self,
        resource: ProviderResource,
        hostname: str,
    ) -> bool:
        """Remove a custom domain from a deployed resource.

        Args:
            resource: Provider resource
            hostname: Custom domain to remove

        Returns:
            True if successfully removed
        """
        ...
