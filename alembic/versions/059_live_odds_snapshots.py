"""Live odds snapshots for in-match win probability (Phase 3).

Revision ID: 059
Revises: 058
Create Date: 2026-07-12

Stores odds after each rack / score update / state change for validation and UI.
Also denormalizes latest odds onto matches for cheap bracket reads.
"""

from alembic import op
from sqlalchemy import text

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS live_odds_snapshots (
                id BIGSERIAL PRIMARY KEY,
                match_id TEXT NOT NULL,
                tournament_id TEXT,
                operator_id TEXT,
                player2_id TEXT,
                p1_score INTEGER NOT NULL DEFAULT 0,
                p2_score INTEGER NOT NULL DEFAULT 0,
                race_to INTEGER,
                p1_race INTEGER,
                p2_race INTEGER,
                p1_rating_used DOUBLE PRECISION,
                p2_rating_used DOUBLE PRECISION,
                rating_source TEXT,
                p_rack_p1 DOUBLE PRECISION,
                p1_win_prob DOUBLE PRECISION NOT NULL,
                p2_win_prob DOUBLE PRECISION NOT NULL,
                odds_trigger TEXT NOT NULL DEFAULT 'score_update',
                game_id INTEGER,
                formula_version TEXT NOT NULL DEFAULT 'live_odds_v1',
                context JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_live_odds_snapshots_match_created "
            "ON live_odds_snapshots (match_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_live_odds_snapshots_tournament_created "
            "ON live_odds_snapshots (tournament_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE matches ADD COLUMN IF NOT EXISTS live_p1_win_prob DOUBLE PRECISION"
        )
    )
    op.execute(
        text(
            "ALTER TABLE matches ADD COLUMN IF NOT EXISTS live_p2_win_prob DOUBLE PRECISION"
        )
    )
    op.execute(
        text(
            "ALTER TABLE matches ADD COLUMN IF NOT EXISTS odds_updated_at TIMESTAMPTZ"
        )
    )


def downgrade() -> None:
    op.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS odds_updated_at"))
    op.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS live_p2_win_prob"))
    op.execute(text("ALTER TABLE matches DROP COLUMN IF EXISTS live_p1_win_prob"))
    op.execute(text("DROP INDEX IF EXISTS ix_live_odds_snapshots_tournament_created"))
    op.execute(text("DROP INDEX IF EXISTS ix_live_odds_snapshots_match_created"))
    op.execute(text("DROP TABLE IF EXISTS live_odds_snapshots"))
