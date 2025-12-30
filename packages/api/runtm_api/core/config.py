"""Configuration management for Runtm API."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is loaded from project root before reading settings
from runtm_shared.env import ensure_env_loaded  # noqa: F401
from runtm_shared.types import AuthMode

# Load .env file from project root
ensure_env_loaded()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Don't specify env_file here - we load it via runtm_shared.env
        # This allows the .env to be in the project root, not the current directory
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://runtm:runtm@localhost:5432/runtm"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Authentication
    auth_mode: AuthMode = AuthMode.SINGLE_TENANT
    api_token: str = ""  # Required in production (single-tenant mode)

    # Token hashing peppers (versioned for rotation)
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    token_pepper_v1: str = ""  # Original pepper (required for multi-tenant)
    token_pepper_v2: str = ""  # For rotation (empty until needed)
    current_pepper_version: int = 1  # Version for new keys

    # Migration window: comma-separated versions to try during rotation
    # e.g., "1,2" during rotation, "2" after migration complete
    pepper_migration_versions: str = ""

    # Admin API key for internal token management routes
    # Required for POST /internal/v0/tokens
    admin_api_key: str = ""

    # Enable internal HTTP routes (disabled by default, use CLI instead)
    enable_internal_routes: bool = False

    # Storage
    artifact_storage_path: str = "/artifacts"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_hour: int = 10

    # Build optimization
    # Remote builder (default True): Builds AND deploys on Fly's infra in one step
    # Set to False to build locally with Docker, then push to Fly registry
    use_remote_builder: bool = True

    # Custom domain configuration
    # When set, deployments will get URLs like <app>.runtm.com instead of <app>.fly.dev
    # Requires DNS provider configuration (Cloudflare) to auto-create CNAME records
    runtm_base_domain: str = ""  # e.g., "runtm.com" - empty means use provider URLs

    # DNS Provider Configuration
    # Used to automatically create CNAME records for custom domain URLs
    # e.g., runtm-abc123.runtm.com -> runtm-abc123.fly.dev
    dns_provider: str = ""  # "cloudflare" or empty to disable

    # Cloudflare DNS Configuration
    # Required when dns_provider = "cloudflare"
    # Get from Cloudflare Dashboard: domain > API section (right sidebar)
    cloudflare_api_token: str = ""  # API token with Zone.DNS edit permission
    cloudflare_zone_id: str = ""  # Zone ID for runtm.com

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug

    @property
    def dns_enabled(self) -> bool:
        """Check if DNS provider is configured."""
        return bool(self.dns_provider and self.runtm_base_domain)

    @property
    def peppers(self) -> dict[int, str]:
        """Get all configured peppers as version -> value map.

        Used for HMAC-based token hashing with rotation support.
        """
        result = {}
        if self.token_pepper_v1:
            result[1] = self.token_pepper_v1
        if self.token_pepper_v2:
            result[2] = self.token_pepper_v2
        return result

    @property
    def migration_versions(self) -> set[int]:
        """Get pepper versions to try during migration window.

        During pepper rotation, set pepper_migration_versions="1,2"
        to allow verification against both old and new peppers.
        """
        if not self.pepper_migration_versions:
            return set()
        return {int(v.strip()) for v in self.pepper_migration_versions.split(",") if v.strip()}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to avoid re-reading environment on every call.
    """
    return Settings()
