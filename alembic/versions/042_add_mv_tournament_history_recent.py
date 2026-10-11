"""Add mv_tournament_history_recent materialized view.

Revision ID: 042
Revises: 041
Create Date: 2026-03-13

Used by Tournament History list and Leaderboard for consistent real-tournament filtering.
"""

from alembic import op
from sqlalchemy import text

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_tournament_history_recent AS
        SELECT id, tournament_id, name, year, date, location, association, championship, prize_pool, status
        FROM tournament_history
    """))
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_tournament_history_recent_id
        ON mv_tournament_history_recent (tournament_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_mv_tournament_history_recent_date
        ON mv_tournament_history_recent (date DESC)
    """))


def downgrade():
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_tournament_history_recent"))
