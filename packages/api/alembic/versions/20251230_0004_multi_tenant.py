"""Multi-tenant authentication and usage tracking

Revision ID: 0004
Revises: 0003
Create Date: 2025-12-30

Adds:
- tenant_id to deployments table for multi-tenant isolation
- api_keys table for API key authentication
- usage_events table for audit trail
- usage_counters table for quota tracking
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Add tenant_id to deployments table
    # =========================================================================
    # Add nullable first, backfill, then make non-null
    op.add_column(
        "deployments",
        sa.Column("tenant_id", sa.String(64), nullable=True),
    )

    # Backfill existing records with "default" tenant
    op.execute("UPDATE deployments SET tenant_id = 'default' WHERE tenant_id IS NULL")

    # Make non-nullable
    op.alter_column("deployments", "tenant_id", nullable=False)

    # Create indexes for tenant isolation
    op.create_index("ix_deployments_tenant_id", "deployments", ["tenant_id"])
    op.create_index("ix_deployments_tenant_created", "deployments", ["tenant_id", "created_at"])

    # CRITICAL: Unique constraint scoped to tenant
    # Prevents cross-tenant deployment_id collisions
    op.create_index(
        "ix_deployments_tenant_deployment_id",
        "deployments",
        ["tenant_id", "deployment_id"],
        unique=True,
    )

    # Update the unique active deployment constraint to include tenant
    # Drop old constraint first
    op.execute("DROP INDEX IF EXISTS ix_deployments_unique_active_name")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_deployments_unique_active_name
        ON deployments (tenant_id, name)
        WHERE is_latest = true AND state NOT IN ('DESTROYED', 'FAILED')
    """
    )

    # =========================================================================
    # Create api_keys table
    # =========================================================================
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("pepper_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes for api_keys
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index(
        "ix_api_keys_prefix_not_revoked",
        "api_keys",
        ["key_prefix"],
        postgresql_where=sa.text("is_revoked = false"),
    )
    op.create_index("ix_api_keys_tenant_principal", "api_keys", ["tenant_id", "principal_id"])

    # =========================================================================
    # Create usage_events table (append-only audit trail)
    # =========================================================================
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("api_key_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("deployment_id", sa.String(32), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column(
            "event_metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes for usage_events
    op.create_index("ix_usage_events_tenant_id", "usage_events", ["tenant_id"])
    op.create_index("ix_usage_events_tenant_created", "usage_events", ["tenant_id", "created_at"])
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"])
    op.create_index("ix_usage_events_deployment_id", "usage_events", ["deployment_id"])
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])

    # =========================================================================
    # Create usage_counters table (for fast quota checks)
    # =========================================================================
    op.create_table(
        "usage_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Unique constraint for upsert (ON CONFLICT)
    op.create_index(
        "ix_usage_counters_unique",
        "usage_counters",
        ["tenant_id", "resource_type", "period"],
        unique=True,
    )


def downgrade() -> None:
    # Drop usage tables
    op.drop_table("usage_counters")
    op.drop_table("usage_events")

    # Drop api_keys table
    op.drop_index("ix_api_keys_tenant_principal", table_name="api_keys")
    op.drop_index("ix_api_keys_prefix_not_revoked", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")

    # Remove tenant_id from deployments
    op.execute("DROP INDEX IF EXISTS ix_deployments_unique_active_name")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_deployments_unique_active_name
        ON deployments (COALESCE(owner_id, ''), name)
        WHERE is_latest = true AND state NOT IN ('DESTROYED', 'FAILED')
    """
    )
    op.drop_index("ix_deployments_tenant_deployment_id", table_name="deployments")
    op.drop_index("ix_deployments_tenant_created", table_name="deployments")
    op.drop_index("ix_deployments_tenant_id", table_name="deployments")
    op.drop_column("deployments", "tenant_id")
