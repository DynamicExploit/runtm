"""Cloudflare DNS provider implementation."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from runtm_shared.dns.base import DnsProvider, DnsRecord


class CloudflareDnsProvider(DnsProvider):
    """Cloudflare DNS API provider.

    Automatically creates CNAME records for deployments to enable
    custom domain URLs (e.g., app.runtm.com instead of app.fly.dev).

    Environment variables:
        CLOUDFLARE_API_TOKEN: API token with Zone.DNS edit permissions
        CLOUDFLARE_ZONE_ID: Zone ID for the domain (e.g., runtm.com zone)

    To get these values:
        1. Log in to Cloudflare Dashboard
        2. Select your domain (runtm.com)
        3. Zone ID is in the right sidebar under "API"
        4. Create API Token: My Profile > API Tokens > Create Token
           - Use "Edit zone DNS" template
           - Select specific zone (runtm.com)
    """

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(
        self,
        api_token: str,
        zone_id: str,
    ):
        """Initialize Cloudflare DNS provider.

        Args:
            api_token: Cloudflare API token with DNS edit permissions
            zone_id: Cloudflare Zone ID for the domain
        """
        if not api_token:
            raise ValueError("Cloudflare API token is required")
        if not zone_id:
            raise ValueError("Cloudflare Zone ID is required")

        self.api_token = api_token
        self.zone_id = zone_id

    @property
    def name(self) -> str:
        return "cloudflare"

    def _headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request to Cloudflare.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to zone)
            json: JSON body
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            CloudflareError: If request fails
        """
        url = f"{self.API_BASE}/zones/{self.zone_id}{endpoint}"

        response = httpx.request(
            method=method,
            url=url,
            headers=self._headers(),
            json=json,
            params=params,
            timeout=30.0,
        )

        data = response.json()

        if not data.get("success", False):
            errors = data.get("errors", [])
            error_msg = errors[0].get("message") if errors else "Unknown error"
            raise CloudflareError(error_msg, errors=errors)

        return data

    def _find_record(
        self,
        subdomain: str,
        domain: str,
        record_type: str = "CNAME",
    ) -> Optional[Dict[str, Any]]:
        """Find a DNS record by name.

        Args:
            subdomain: Subdomain part
            domain: Base domain
            record_type: Record type (CNAME, A, etc.)

        Returns:
            Record data if found, None otherwise
        """
        # Full record name
        name = f"{subdomain}.{domain}"

        try:
            data = self._request(
                "GET",
                "/dns_records",
                params={
                    "type": record_type,
                    "name": name,
                },
            )

            records = data.get("result", [])
            if records:
                return records[0]
            return None
        except CloudflareError:
            return None

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
            proxied: Whether to proxy through Cloudflare (orange cloud)

        Returns:
            True if record created successfully
        """
        name = f"{subdomain}.{domain}"

        try:
            self._request(
                "POST",
                "/dns_records",
                json={
                    "type": "CNAME",
                    "name": name,
                    "content": target,
                    "ttl": 1 if proxied else 3600,  # 1 = auto for proxied
                    "proxied": proxied,
                    "comment": "Created by Runtm",
                },
            )
            return True
        except CloudflareError as e:
            # Check if record already exists (error code 81057)
            if any(err.get("code") == 81057 for err in e.errors):
                # Record exists, try to update instead
                return self.upsert_cname(subdomain, domain, target, proxied)
            raise

    def delete_record(
        self,
        subdomain: str,
        domain: str,
    ) -> bool:
        """Delete a DNS record.

        Args:
            subdomain: Subdomain part
            domain: Base domain

        Returns:
            True if record deleted successfully
        """
        record = self._find_record(subdomain, domain)
        if not record:
            return True  # Already doesn't exist

        record_id = record.get("id")
        if not record_id:
            return False

        try:
            self._request("DELETE", f"/dns_records/{record_id}")
            return True
        except CloudflareError:
            return False

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
        return self._find_record(subdomain, domain) is not None

    def get_record(
        self,
        subdomain: str,
        domain: str,
    ) -> Optional[DnsRecord]:
        """Get an existing DNS record.

        Args:
            subdomain: Subdomain part
            domain: Base domain

        Returns:
            DnsRecord if found, None otherwise
        """
        record = self._find_record(subdomain, domain)
        if not record:
            return None

        return DnsRecord(
            record_type=record.get("type", "CNAME"),
            name=record.get("name", ""),
            value=record.get("content", ""),
            proxied=record.get("proxied", False),
            ttl=record.get("ttl", 3600),
        )

    def update_record(
        self,
        subdomain: str,
        domain: str,
        target: str,
        proxied: bool = False,
    ) -> bool:
        """Update an existing CNAME record.

        Args:
            subdomain: Subdomain part
            domain: Base domain
            target: New target hostname
            proxied: Whether to proxy through Cloudflare

        Returns:
            True if record updated successfully
        """
        record = self._find_record(subdomain, domain)
        if not record:
            # Record doesn't exist, create it
            return self.create_cname(subdomain, domain, target, proxied)

        record_id = record.get("id")
        if not record_id:
            return False

        name = f"{subdomain}.{domain}"

        try:
            self._request(
                "PATCH",
                f"/dns_records/{record_id}",
                json={
                    "type": "CNAME",
                    "name": name,
                    "content": target,
                    "ttl": 1 if proxied else 3600,
                    "proxied": proxied,
                },
            )
            return True
        except CloudflareError:
            return False


class CloudflareError(Exception):
    """Cloudflare API error."""

    def __init__(self, message: str, errors: Optional[list] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []

