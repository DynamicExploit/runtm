"""Telemetry tables: spans, events, metrics

Revision ID: 0002
Revises: 0001
Create Date: 2025-12-28

Add tables for storing telemetry data:
- telemetry_spans: Distributed tracing spans
- telemetry_events: Discrete events (lifecycle, errors)
- telemetry_metrics: Aggregated metrics (counters, histograms)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Telemetry spans table
    # =========================================================================
    # Stores distributed tracing spans from CLI, Worker, and API.
    # Each span represents an operation with timing and attributes.
    op.create_table(
        "telemetry_spans",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Trace context (W3C Trace Context compatible)
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("span_id", sa.String(16), nullable=False),
        sa.Column("parent_span_id", sa.String(16), nullable=True),
        # Span metadata
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unset"),
        # Timing (nanoseconds for precision)
        sa.Column("start_time_ns", sa.BigInteger(), nullable=False),
        sa.Column("end_time_ns", sa.BigInteger(), nullable=True),
        # Attributes (JSONB for flexibility)
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        # Link to deployment (optional, for deployment-specific traces)
        sa.Column("deployment_id", sa.String(32), nullable=True),
        # Source service
        sa.Column("service_name", sa.String(64), nullable=True),
        # Multi-tenant support
        sa.Column("owner_id", sa.String(64), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Indexes for common query patterns
    op.create_index("ix_telemetry_spans_trace_id", "telemetry_spans", ["trace_id"])
    op.create_index("ix_telemetry_spans_deployment_id", "telemetry_spans", ["deployment_id"])
    op.create_index("ix_telemetry_spans_owner_id", "telemetry_spans", ["owner_id"])
    op.create_index("ix_telemetry_spans_created_at", "telemetry_spans", ["created_at"])
    op.create_index("ix_telemetry_spans_name", "telemetry_spans", ["name"])
    # Composite index for trace reconstruction
    op.create_index(
        "ix_telemetry_spans_trace_parent",
        "telemetry_spans",
        ["trace_id", "parent_span_id"],
    )

    # =========================================================================
    # Telemetry events table
    # =========================================================================
    # Stores discrete events (lifecycle events, errors, etc.)
    # Events can be standalone or attached to spans.
    op.create_table(
        "telemetry_events",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Event metadata
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("timestamp_ns", sa.BigInteger(), nullable=False),
        # Attributes (JSONB for flexibility)
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        # Optional trace context (for events attached to spans)
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("span_id", sa.String(16), nullable=True),
        # Link to deployment (optional)
        sa.Column("deployment_id", sa.String(32), nullable=True),
        # Source service
        sa.Column("service_name", sa.String(64), nullable=True),
        # Multi-tenant support
        sa.Column("owner_id", sa.String(64), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Indexes for common query patterns
    op.create_index("ix_telemetry_events_trace_id", "telemetry_events", ["trace_id"])
    op.create_index("ix_telemetry_events_deployment_id", "telemetry_events", ["deployment_id"])
    op.create_index("ix_telemetry_events_owner_id", "telemetry_events", ["owner_id"])
    op.create_index("ix_telemetry_events_created_at", "telemetry_events", ["created_at"])
    op.create_index("ix_telemetry_events_name", "telemetry_events", ["name"])

    # =========================================================================
    # Telemetry metrics table
    # =========================================================================
    # Stores aggregated metrics (counters, histograms, gauges).
    # Metrics can be pre-aggregated into time buckets for efficient querying.
    op.create_table(
        "telemetry_metrics",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Metric metadata
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("metric_type", sa.String(16), nullable=False),  # counter, histogram, gauge
        sa.Column("value", sa.Float(), nullable=False),
        # Labels (JSONB for flexibility, low-cardinality)
        sa.Column("labels", postgresql.JSONB, nullable=False, server_default="{}"),
        # Timing
        sa.Column("timestamp_ns", sa.BigInteger(), nullable=False),
        # Aggregation period (for pre-aggregated metrics)
        sa.Column("bucket_period", sa.String(16), nullable=True),  # raw, hour, day
        # Source service
        sa.Column("service_name", sa.String(64), nullable=True),
        # Multi-tenant support
        sa.Column("owner_id", sa.String(64), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Indexes for common query patterns
    op.create_index("ix_telemetry_metrics_name", "telemetry_metrics", ["name"])
    op.create_index("ix_telemetry_metrics_owner_id", "telemetry_metrics", ["owner_id"])
    op.create_index("ix_telemetry_metrics_created_at", "telemetry_metrics", ["created_at"])
    op.create_index("ix_telemetry_metrics_metric_type", "telemetry_metrics", ["metric_type"])
    # Composite index for metric querying
    op.create_index(
        "ix_telemetry_metrics_name_created",
        "telemetry_metrics",
        ["name", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("telemetry_metrics")
    op.drop_table("telemetry_events")
    op.drop_table("telemetry_spans")

