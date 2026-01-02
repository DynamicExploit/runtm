"""Deploy optimization columns

Revision ID: 0005
Revises: 0004
Create Date: 2025-12-31

Adds columns for deploy time optimization:
- src_hash: Source hash for config-only deploy validation
- config_only: Flag to skip build and reuse previous image
- image_label: Image label for rollbacks/reuse
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Add deploy optimization columns to deployments table
    # =========================================================================

    # src_hash: Used to validate --config-only deploys haven't changed source code
    # Stores git SHA (preferred) or source tree hash
    op.add_column(
        "deployments",
        sa.Column("src_hash", sa.String(64), nullable=True),
    )

    # config_only: Flag indicating this deployment skips build and reuses previous image
    # Default False for backwards compatibility
    op.add_column(
        "deployments",
        sa.Column("config_only", sa.Boolean(), nullable=False, server_default="false"),
    )

    # =========================================================================
    # Add image_label to provider_resources table
    # =========================================================================

    # image_label: Used for rollbacks and config-only deploys
    # Format: e.g., "dep-abc123" (deployment ID prefix)
    # Used with: flyctl deploy --image registry.fly.io/{app}:{label}
    op.add_column(
        "provider_resources",
        sa.Column("image_label", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    # Remove image_label from provider_resources
    op.drop_column("provider_resources", "image_label")

    # Remove deploy optimization columns from deployments
    op.drop_column("deployments", "config_only")
    op.drop_column("deployments", "src_hash")
