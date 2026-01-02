"""Abstract DNS provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DnsRecord:
    """DNS record information."""

    record_type: str  # "CNAME", "A", "AAAA", etc.
    name: str  # subdomain or full hostname
    value: str  # target for CNAME, IP for A/AAAA
    proxied: bool = False  # for Cloudflare proxy mode
    ttl: int = 3600  # TTL in seconds


class DnsProvider(ABC):
    """Abstract interface for DNS providers.

    Implementations:
        - CloudflareDnsProvider: Cloudflare DNS API
        - Route53DnsProvider: AWS Route53 (future)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'cloudflare', 'route53')."""
        ...

    @abstractmethod
    def create_cname(
        self,
        subdomain: str,
        domain: str,
        target: str,
        proxied: bool = False,
    ) -> bool:
        """Create a CNAME record.

        Args:
            subdomain: Subdomain part (e.g., "runtm-abc123")
            domain: Base domain (e.g., "runtm.com")
            target: Target hostname (e.g., "runtm-abc123.fly.dev")
            proxied: Whether to proxy through CDN (Cloudflare only)

        Returns:
            True if record created successfully
        """
        ...

    @abstractmethod
    def delete_record(
        self,
        subdomain: str,
        domain: str,
    ) -> bool:
        """Delete a DNS record.

        Args:
            subdomain: Subdomain part (e.g., "runtm-abc123")
            domain: Base domain (e.g., "runtm.com")

        Returns:
            True if record deleted successfully
        """
        ...

    @abstractmethod
    def record_exists(
        self,
        subdomain: str,
        domain: str,
    ) -> bool:
        """Check if a DNS record exists.

        Args:
            subdomain: Subdomain part
            domain: Base domain

        Returns:
            True if record exists
        """
        ...

    @abstractmethod
    def get_record(
        self,
        subdomain: str,
        domain: str,
    ) -> DnsRecord | None:
        """Get an existing DNS record.

        Args:
            subdomain: Subdomain part
            domain: Base domain

        Returns:
            DnsRecord if found, None otherwise
        """
        ...

    def upsert_cname(
        self,
        subdomain: str,
        domain: str,
        target: str,
        proxied: bool = False,
    ) -> bool:
        """Create or update a CNAME record (idempotent).

        Args:
            subdomain: Subdomain part
            domain: Base domain
            target: Target hostname
            proxied: Whether to proxy through CDN

        Returns:
            True if record created/updated successfully
        """
        # Check if record exists with same target
        existing = self.get_record(subdomain, domain)
        if existing and existing.value == target:
            # Already exists with correct target, no action needed
            return True

        if existing:
            # Delete existing record before creating new one
            self.delete_record(subdomain, domain)

        # Create new record
        return self.create_cname(subdomain, domain, target, proxied)
