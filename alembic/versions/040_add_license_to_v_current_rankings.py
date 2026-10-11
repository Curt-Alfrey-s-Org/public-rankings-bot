"""Add license_number to v_current_rankings for Leaderboard display.

Revision ID: 040
Revises: 039
Create Date: 2026-03-12

Enables Leaderboard to show real license numbers (never fabricated RANK-xxx).
"""

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DROP VIEW IF EXISTS v_current_rankings CASCADE
    """)
    op.execute("""
        CREATE VIEW v_current_rankings AS
        SELECT
            p.player_id,
            p.first_name,
            p.last_name,
            p.nickname,
            p.license_number,
            p.avatar_url,
            p.total_points,
            p.current_rank,
            p.total_tournaments_played,
            p.hall_of_fame,
            p.hot_streak_count,
            p.fargo_score,
            p.nationality,
            ps.win_percentage_matches,
            ps.win_percentage_games,
            ps.first_place_finishes,
            ps.second_place_finishes,
            ps.third_place_finishes
        FROM players p
        LEFT JOIN player_statistics ps ON p.player_id = ps.player_id
        WHERE p.membership_status = 'active'
        ORDER BY p.current_rank ASC NULLS LAST, p.total_points DESC
    """)


def downgrade() -> None:
    op.execute("""
        DROP VIEW IF EXISTS v_current_rankings CASCADE
    """)
    op.execute("""
        CREATE VIEW v_current_rankings AS
        SELECT
            p.player_id,
            p.first_name,
            p.last_name,
            p.nickname,
            p.avatar_url,
            p.total_points,
            p.current_rank,
            p.total_tournaments_played,
            p.hall_of_fame,
            p.hot_streak_count,
            p.fargo_score,
            p.nationality,
            ps.win_percentage_matches,
            ps.win_percentage_games,
            ps.first_place_finishes,
            ps.second_place_finishes,
            ps.third_place_finishes
        FROM players p
        LEFT JOIN player_statistics ps ON p.player_id = ps.player_id
        WHERE p.membership_status = 'active'
        ORDER BY p.current_rank ASC NULLS LAST, p.total_points DESC
    """)
