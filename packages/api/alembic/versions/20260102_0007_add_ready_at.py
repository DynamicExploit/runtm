"""Add ready_at timestamp to deployments.

Captures the exact time a deployment transitioned to 'ready' state.
This is different from updated_at which changes whenever the record is modified
(e.g., when is_latest is set to false by a newer deployment).

Revision ID: 0007
Revises: 0006
Create Date: 2026-01-02

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ready_at column to deployments table."""
    op.add_column(
        "deployments",
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Backfill existing ready deployments with a reasonable estimate
    # For deployments that are already ready, we estimate ready_at as created_at + some buffer
    # This isn't perfect but gives us a starting point
    # Note: We can't perfectly recover the original ready time, but we can make a reasonable estimate
    op.execute("""
        UPDATE deployments 
        SET ready_at = updated_at 
        WHERE state = 'ready' AND is_latest = true
    """)
    
    # For older superseded deployments, try to estimate from the next deployment's created_at
    # This is complex, so we'll leave those as NULL for now - they'll just show as "N/A" in dashboard


def downgrade() -> None:
    """Remove ready_at column from deployments table."""
    op.drop_column("deployments", "ready_at")

