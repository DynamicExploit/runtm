"""Initial schema: deployments, provider_resources, idempotency_keys, build_logs

Revision ID: 0001
Revises:
Create Date: 2025-12-15

Full database schema for Runtm including:
- deployments: Core deployment records with version tracking for redeployments
- provider_resources: Fly.io/Cloud Run resource mappings
- idempotency_keys: Safe retry support
- build_logs: Build and deploy log storage
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Deployments table
    # =========================================================================
    # Core deployment records. Each deployment represents a single version
    # of a project deployed to a URL. Redeployments create new records
    # linked via previous_deployment_id.
    op.create_table(
        "deployments",
        # Primary key (internal UUID)
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Human-friendly deployment ID (e.g., dep_abc123def456)
        sa.Column("deployment_id", sa.String(32), unique=True, nullable=False),
        # Multi-tenant fields (nullable for single-tenant mode)
        sa.Column("owner_id", sa.String(64), nullable=True),
        sa.Column("api_key_id", sa.String(64), nullable=True),
        # Deployment metadata
        sa.Column("name", sa.String(63), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, default="queued"),
        sa.Column("artifact_key", sa.String(256), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("url", sa.String(256), nullable=True),
        # Version tracking for redeployments (CI/CD support)
        # - version: increments on each redeploy (1, 2, 3, ...)
        # - is_latest: only one deployment per name should be true
        # - previous_deployment_id: links to the deployment this replaced
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("previous_deployment_id", sa.String(32), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_deployments_deployment_id", "deployments", ["deployment_id"])
    op.create_index("ix_deployments_owner_id", "deployments", ["owner_id"])
    op.create_index("ix_deployments_state", "deployments", ["state"])
    op.create_index("ix_deployments_created_at", "deployments", ["created_at"])
    op.create_index("ix_deployments_name", "deployments", ["name"])
    op.create_index("ix_deployments_name_is_latest", "deployments", ["name", "is_latest"])

    # Partial unique index: only one is_latest=true per (owner_id, name)
    # This ensures at most one active deployment per name per owner
    # Excludes destroyed/failed deployments from the constraint
    # Note: SQLAlchemy with native_enum=False stores enum names (uppercase), not values
    op.execute("""
        CREATE UNIQUE INDEX ix_deployments_unique_active_name
        ON deployments (COALESCE(owner_id, ''), name)
        WHERE is_latest = true AND state NOT IN ('DESTROYED', 'FAILED')
    """)

    # =========================================================================
    # Provider resources table
    # =========================================================================
    # Maps deployments to provider-specific resources (Fly.io machines, etc.)
    op.create_table(
        "provider_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("app_name", sa.String(128), nullable=False),
        sa.Column("machine_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("image_ref", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_provider_resources_app_name", "provider_resources", ["app_name"])
    op.create_index("ix_provider_resources_provider", "provider_resources", ["provider"])

    # =========================================================================
    # Idempotency keys table
    # =========================================================================
    # Maps Idempotency-Key headers to deployments for safe retries
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"])
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])

    # =========================================================================
    # Build logs table
    # =========================================================================
    # Stores build and deploy logs for each deployment
    op.create_table(
        "build_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("log_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_build_logs_deployment_id", "build_logs", ["deployment_id"])
    op.create_index("ix_build_logs_log_type", "build_logs", ["log_type"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_deployments_unique_active_name")
    op.drop_table("build_logs")
    op.drop_table("idempotency_keys")
    op.drop_table("provider_resources")
    op.drop_table("deployments")
