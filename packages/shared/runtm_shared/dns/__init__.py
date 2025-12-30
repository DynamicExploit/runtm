"""DNS provider abstraction for automatic DNS record management.

This module provides a pluggable interface for DNS providers (Cloudflare, Route53, etc.)
to automatically create DNS records when deployments happen.

When RUNTM_BASE_DOMAIN is set (e.g., "runtm.com"), the deploy pipeline will:
1. Deploy to provider (Fly, AWS, GCP, etc.)
2. Create CNAME record: <app>.runtm.com -> <app>.fly.dev
3. Add SSL certificate for <app>.runtm.com
4. Return URL as https://<app>.runtm.com

This hides provider URLs and gives users consistent runtm.com URLs.
"""

from runtm_shared.dns.base import DnsProvider, DnsRecord

__all__ = [
    "DnsProvider",
    "DnsRecord",
]

