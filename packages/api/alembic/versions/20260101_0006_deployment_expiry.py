"""Add expires_at for app lifespan limits.

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-01

Adds columns and indexes for policy-based resource limits:
- expires_at: Optional expiry timestamp for app lifespan limits
- Index on expires_at for reaper queries
- Index on (tenant_id, name) for app count queries
- Index on (tenant_id, created_at) for deploy rate queries
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # Add expires_at column for app lifespan limits
    # =========================================================================
    # NULL means no expiry (lives forever)
    # Set by policy provider when creating deployments
    op.add_column(
        "deployments",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =========================================================================
    # Indexes for policy queries
    # =========================================================================
    # Use if_not_exists for idempotency (indexes may exist from partial runs)

    # Index for reaper queries: find expired apps efficiently
    # WHERE expires_at IS NOT NULL AND expires_at <= now() AND state != 'destroyed'
    op.create_index(
        "ix_deployments_expires_at",
        "deployments",
        ["expires_at"],
        if_not_exists=True,
    )

    # Index for app count queries: count logical apps per tenant
    # COUNT(DISTINCT name) WHERE tenant_id = ? AND state != 'destroyed'
    op.create_index(
        "ix_deployments_tenant_name",
        "deployments",
        ["tenant_id", "name"],
        if_not_exists=True,
    )

    # Index for deploy rate queries: count deploys in time window
    # COUNT(*) WHERE tenant_id = ? AND created_at >= ?
    op.create_index(
        "ix_deployments_tenant_created",
        "deployments",
        ["tenant_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_deployments_tenant_created", table_name="deployments")
    op.drop_index("ix_deployments_tenant_name", table_name="deployments")
    op.drop_index("ix_deployments_expires_at", table_name="deployments")
    op.drop_column("deployments", "expires_at")
