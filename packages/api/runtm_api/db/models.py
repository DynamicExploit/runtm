"""SQLAlchemy models for Runtm API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from runtm_shared.types import DeploymentState, LogType


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Deployment(Base):
    """Deployment record.

    Tracks the lifecycle of a deployment from creation to ready/failed.
    """

    __tablename__ = "deployments"

    # Primary key (internal UUID)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Human-friendly deployment ID (e.g., dep_abc123def456)
    deployment_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    # Multi-tenant isolation
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", index=True
    )

    # Legacy owner_id (kept for backwards compatibility, may be removed)
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    api_key_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Deployment metadata
    name: Mapped[str] = mapped_column(String(63), nullable=False)
    state: Mapped[DeploymentState] = mapped_column(
        Enum(DeploymentState, native_enum=False),
        nullable=False,
        default=DeploymentState.QUEUED,
    )

    # Storage reference
    artifact_key: Mapped[str] = mapped_column(String(256), nullable=False)

    # Parsed manifest (for quick access)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Error message (populated on failure)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Deployment URL (populated when ready)
    url: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Version tracking for redeployments
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(nullable=False, default=True)
    previous_deployment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Discovery metadata from runtm.discovery.yaml (for search/discoverability)
    discovery_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Source hash for config-only deploys (git SHA or source tree hash)
    # Used to validate --config-only deploys haven't changed source code
    src_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Config-only deploy flag (skip build, reuse previous image)
    config_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # App lifespan - NULL means forever, set by policy provider
    # When set, app should be stopped/destroyed by reaper job after this time
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    provider_resource: Mapped[Optional[ProviderResource]] = relationship(
        "ProviderResource",
        back_populates="deployment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    build_logs: Mapped[list[BuildLog]] = relationship(
        "BuildLog",
        back_populates="deployment",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_deployments_owner_id", "owner_id"),
        Index("ix_deployments_state", "state"),
        Index("ix_deployments_created_at", "created_at"),
    )


class ProviderResource(Base):
    """Provider-specific resource mapping.

    Maps deployment_id to provider identifiers (Fly app, machine, etc.).
    """

    __tablename__ = "provider_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to deployment
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Provider type (e.g., "fly", "cloudrun")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)

    # Provider-specific identifiers
    app_name: Mapped[str] = mapped_column(String(128), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    image_ref: Mapped[str] = mapped_column(String(256), nullable=False)

    # Image label for rollbacks/reuse (e.g., "dep-abc123")
    # Used with `flyctl deploy --image registry.fly.io/{app}:{label}`
    image_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    deployment: Mapped[Deployment] = relationship(
        "Deployment",
        back_populates="provider_resource",
    )

    # Indexes
    __table_args__ = (
        Index("ix_provider_resources_app_name", "app_name"),
        Index("ix_provider_resources_provider", "provider"),
    )


class IdempotencyKey(Base):
    """Idempotency key mapping.

    Maps Idempotency-Key header to deployment for safe retries.
    """

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # The idempotency key from request header
    key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # Associated deployment
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # TTL for cleanup (24 hours by default)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Indexes
    __table_args__ = (Index("ix_idempotency_keys_expires_at", "expires_at"),)


class BuildLog(Base):
    """Build and deploy log entries.

    Stores captured logs from build and deploy phases.
    """

    __tablename__ = "build_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to deployment
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Log type (build or deploy)
    log_type: Mapped[LogType] = mapped_column(
        Enum(LogType, native_enum=False),
        nullable=False,
    )

    # Log content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    deployment: Mapped[Deployment] = relationship(
        "Deployment",
        back_populates="build_logs",
    )

    # Indexes
    __table_args__ = (
        Index("ix_build_logs_deployment_id", "deployment_id"),
        Index("ix_build_logs_log_type", "log_type"),
    )


# =============================================================================
# Telemetry Models
# =============================================================================


class TelemetrySpan(Base):
    """Distributed tracing span.

    Stores spans from CLI, Worker, and API for distributed tracing.
    Spans can be linked to deployments for deployment-specific traces.
    """

    __tablename__ = "telemetry_spans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Trace context (W3C Trace Context compatible)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Span metadata
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unset")

    # Timing (nanoseconds for precision)
    start_time_ns: Mapped[int] = mapped_column(nullable=False)
    end_time_ns: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Attributes (JSONB for flexibility)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Link to deployment (optional)
    deployment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    # Source service
    service_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Multi-tenant support
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Indexes
    __table_args__ = (Index("ix_telemetry_spans_trace_parent", "trace_id", "parent_span_id"),)

    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.end_time_ns is None:
            return None
        return (self.end_time_ns - self.start_time_ns) / 1_000_000


class TelemetryEvent(Base):
    """Discrete telemetry event.

    Stores events like lifecycle events, errors, etc.
    Events can be standalone or attached to spans via trace context.
    """

    __tablename__ = "telemetry_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Event metadata
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timestamp_ns: Mapped[int] = mapped_column(nullable=False)

    # Attributes (JSONB for flexibility)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Optional trace context
    trace_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    span_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Link to deployment (optional)
    deployment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    # Source service
    service_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Multi-tenant support
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class TelemetryMetric(Base):
    """Aggregated telemetry metric.

    Stores metrics like counters, histograms, and gauges.
    Metrics can be pre-aggregated into time buckets for efficient querying.
    """

    __tablename__ = "telemetry_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Metric metadata
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # counter, histogram, gauge
    value: Mapped[float] = mapped_column(nullable=False)

    # Labels (JSONB for flexibility, low-cardinality)
    labels: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Timing
    timestamp_ns: Mapped[int] = mapped_column(nullable=False)

    # Aggregation period (for pre-aggregated metrics)
    bucket_period: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )  # raw, hour, day

    # Source service
    service_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Multi-tenant support
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Indexes
    __table_args__ = (Index("ix_telemetry_metrics_name_created", "name", "created_at"),)


# =============================================================================
# Multi-Tenant Authentication Models
# =============================================================================


class ApiKey(Base):
    """API key for multi-tenant authentication.

    Security features:
    - pepper_version: Enables pepper rotation without breaking existing keys
    - key_prefix (16 chars): Reduces DB candidates to near-O(1) lookup
    - key_hash: HMAC-SHA256, NOT unique (allows hash strategy changes)
    - scopes: Validated on write to enum-only values

    The raw key is never stored - only shown once at creation.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant isolation (org/workspace) - the isolation boundary
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Principal (user or service account within tenant)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Token lookup: 16-char prefix for near-O(1) narrowing, hash for verification
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # NOT unique (hash strategy may change)

    # Pepper versioning for rotation support
    # When rotating: add new pepper, create new keys with new version
    # During migration window: verify against both versions
    pepper_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Metadata
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scopes: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # Validated on write to enum-only

    # Lifecycle
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Indexes for efficient lookup and tenant queries
    __table_args__ = (
        # Fast lookup: prefix + not revoked
        Index(
            "ix_api_keys_prefix_not_revoked",
            "key_prefix",
            postgresql_where=text("is_revoked = false"),
        ),
        # Tenant + principal for listing keys
        Index("ix_api_keys_tenant_principal", "tenant_id", "principal_id"),
    )


# =============================================================================
# Usage Tracking Models
# =============================================================================


class UsageEvent(Base):
    """Append-only usage events for audit/reconciliation/billing disputes.

    Includes full attribution:
    - who: principal_id (user/service account)
    - how: api_key_id (which API key was used)
    - correlation: request_id, deployment_id

    These records are NEVER deleted - they form the audit trail.
    """

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant for isolation
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Attribution: who did it
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Correlation
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    deployment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # deploy, destroy, etc.
    event_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Indexes for efficient queries
    __table_args__ = (Index("ix_usage_events_tenant_created", "tenant_id", "created_at"),)


class UsageCounter(Base):
    """Upsertable counters for fast quota checks.

    Aggregated by (tenant_id, resource_type, period) for quick lookups.
    Uses ON CONFLICT for race-safe increments.
    """

    __tablename__ = "usage_counters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., "2025-01"
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Unique constraint for upsert
    __table_args__ = (
        Index(
            "ix_usage_counters_unique",
            "tenant_id",
            "resource_type",
            "period",
            unique=True,
        ),
    )
