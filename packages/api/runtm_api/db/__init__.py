"""Database module."""

from runtm_api.db.models import (
    ApiKey,
    Base,
    BuildLog,
    Deployment,
    IdempotencyKey,
    ProviderResource,
    TelemetryEvent,
    TelemetryMetric,
    TelemetrySpan,
    UsageCounter,
    UsageEvent,
)
from runtm_api.db.repository import (
    ApiKeyRepository,
    DeploymentRepository,
    TenantRepository,
)
from runtm_api.db.session import create_session, get_db

__all__ = [
    "Base",
    "Deployment",
    "ProviderResource",
    "IdempotencyKey",
    "BuildLog",
    "TelemetrySpan",
    "TelemetryEvent",
    "TelemetryMetric",
    # Multi-tenant auth
    "ApiKey",
    # Usage tracking
    "UsageEvent",
    "UsageCounter",
    # Repositories
    "TenantRepository",
    "DeploymentRepository",
    "ApiKeyRepository",
    # Session helpers
    "get_db",
    "create_session",
]
