"""Rankings: one row per (ranking_system, snapshot_date, rank) per PostgreSQL best practice.

Revision ID: 027
Revises: 026
Create Date: 2026-03-01

Per PostgreSQL docs (5.5.3 Unique Constraints, 11.6 Unique Indexes): use a composite
unique constraint on the columns that identify one row. Here, list position is
(ranking_system, snapshot_date, rank); the same player_name may appear at different
ranks. This allows import "copy-paste" semantics: row N in import = row at rank N.

- Drop UNIQUE(player_name, ranking_system, snapshot_date)
- Add UNIQUE(ranking_system, snapshot_date, rank)
Ref: https://www.postgresql.org/docs/current/ddl-constraints.html
     https://www.postgresql.org/docs/current/indexes-unique.html
"""

from alembic import op
from sqlalchemy import text

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade():
    # Remove duplicate (ranking_system, snapshot_date, rank) rows keeping smallest id
    op.execute(text("""
        DELETE FROM rankings r
        USING rankings r2
        WHERE r.ranking_system = r2.ranking_system
          AND r.snapshot_date = r2.snapshot_date
          AND r.rank = r2.rank
          AND r.id > r2.id
    """))
    # Drop old unique: one row per (player_name, ranking_system, snapshot_date)
    op.execute(text("""
        ALTER TABLE rankings
        DROP CONSTRAINT IF EXISTS rankings_player_name_ranking_system_snapshot_date_key
    """))
    # Add unique: one row per (ranking_system, snapshot_date, rank) — list position
    op.create_unique_constraint(
        "rankings_ranking_system_snapshot_date_rank_key",
        "rankings",
        ["ranking_system", "snapshot_date", "rank"],
    )


def downgrade():
    op.drop_constraint(
        "rankings_ranking_system_snapshot_date_rank_key",
        "rankings",
        type_="unique",
    )
    op.create_unique_constraint(
        "rankings_player_name_ranking_system_snapshot_date_key",
        "rankings",
        ["player_name", "ranking_system", "snapshot_date"],
    )
