"""Add discovery_json column for app discovery metadata

Revision ID: 0003
Revises: 0002
Create Date: 2025-12-29

Adds discovery_json JSONB column to store runtm.discovery.yaml metadata
for search and discoverability features. Includes GIN index for fast
full-text search on JSONB content.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add discovery_json column for storing runtm.discovery.yaml content
    op.add_column(
        "deployments",
        sa.Column("discovery_json", postgresql.JSONB, nullable=True),
    )

    # Add GIN index for fast JSONB containment and text search
    op.create_index(
        "ix_deployments_discovery_gin",
        "deployments",
        ["discovery_json"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_deployments_discovery_gin", table_name="deployments")
    op.drop_column("deployments", "discovery_json")

