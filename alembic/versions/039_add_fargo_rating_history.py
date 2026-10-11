"""Add fargo_rating_history table to keep previous Fargo ratings.

Revision ID: 039
Revises: 038
Create Date: 2026-03-09

Stores each Fargo rating change so previous values are preserved for
trending, charts, and accuracy analysis. Populated when Fargo is updated
via sync, manual import, or backfill.
"""

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS fargo_rating_history (
            id SERIAL PRIMARY KEY,
            player_id VARCHAR(255) NOT NULL,
            player_name VARCHAR(255) NOT NULL,
            ranking_system VARCHAR(32),
            old_fargo_rating DOUBLE PRECISION,
            new_fargo_rating DOUBLE PRECISION NOT NULL,
            fargo_source VARCHAR(64),
            snapshot_date DATE NOT NULL,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archive_reason VARCHAR(64) DEFAULT 'update',
            confidence_score DOUBLE PRECISION DEFAULT 0.8,
            data_quality VARCHAR(32) DEFAULT 'verified'
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fargo_history_player_date "
        "ON fargo_rating_history(player_id, snapshot_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fargo_history_player_name "
        "ON fargo_rating_history(player_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_fargo_history_player_name")
    op.execute("DROP INDEX IF EXISTS idx_fargo_history_player_date")
    op.execute("DROP TABLE IF EXISTS fargo_rating_history")
