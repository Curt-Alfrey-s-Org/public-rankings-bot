"""Add est_rating_trend to players for UI trending indicator.

Revision ID: 038
Revises: 037
Create Date: 2026-03-09

Stores last EST change direction: 1 = up, -1 = down, 0 = stable.
Updated whenever est_rating is updated in live_rating_engine.
"""

from alembic import op
import sqlalchemy as sa

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("est_rating_trend", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "est_rating_trend")
