"""Add stops_played to tournament_results (WPBA snapshots / per-event rows).

Revision ID: 048
Revises: 047
Create Date: 2026-03-23

Code paths in postgres_manager insert stops_played for rankings_snapshot_* and
wpba_evt_* tournament_results. Older DBs only had (tournament_id, player_name, placement, points).
"""

from alembic import op
from sqlalchemy import text

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'tournament_results'
            ) THEN
                ALTER TABLE tournament_results
                ADD COLUMN IF NOT EXISTS stops_played INTEGER;
            END IF;
        END $$;
        """
        )
    )


def downgrade():
    op.execute(
        text(
            """
        ALTER TABLE tournament_results DROP COLUMN IF EXISTS stops_played;
        """
        )
    )
