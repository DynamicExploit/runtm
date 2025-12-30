"""URL construction utilities for Runtm deployments.

This module handles constructing deployment URLs, supporting both:
- Default Fly.io URLs: <app>.fly.dev
- Custom domain URLs: <app>.runtm.com (when RUNTM_BASE_DOMAIN is set)

When a custom base domain is configured, deployments automatically get
a subdomain on that domain (e.g., my-app.runtm.com).
"""

from __future__ import annotations

import os


def get_base_domain() -> str:
    """Get the configured base domain for deployments.

    Returns:
        Base domain (e.g., "runtm.com") or empty string for default fly.dev
    """
    return os.environ.get("RUNTM_BASE_DOMAIN", "")


def construct_deployment_url(app_name: str, base_domain: str | None = None) -> str:
    """Construct the public URL for a deployment.

    Args:
        app_name: Fly.io app name (e.g., "runtm-abc123")
        base_domain: Override base domain (uses env var if not provided)

    Returns:
        Full HTTPS URL for the deployment

    Examples:
        >>> construct_deployment_url("runtm-abc123")
        "https://runtm-abc123.fly.dev"  # default

        >>> construct_deployment_url("runtm-abc123", "runtm.com")
        "https://runtm-abc123.runtm.com"  # custom domain
    """
    if base_domain is None:
        base_domain = get_base_domain()

    if base_domain:
        return f"https://{app_name}.{base_domain}"
    else:
        return f"https://{app_name}.fly.dev"


def get_subdomain_for_app(app_name: str, base_domain: str | None = None) -> str | None:
    """Get the subdomain hostname for automatic certificate provisioning.

    Only returns a value when a custom base domain is configured.
    This subdomain should be added as a certificate to the Fly app.

    Args:
        app_name: Fly.io app name
        base_domain: Override base domain

    Returns:
        Subdomain hostname (e.g., "runtm-abc123.runtm.com") or None
    """
    if base_domain is None:
        base_domain = get_base_domain()

    if base_domain:
        return f"{app_name}.{base_domain}"
    return None

