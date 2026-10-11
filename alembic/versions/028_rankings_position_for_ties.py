"""Rankings: position column for tied ranks (WPA, Heyball, WPBA, Artistic).

Revision ID: 028
Revises: 027
Create Date: 2026-03-01

Supports tied ranks: two players can be rank 51, next is 53. Unique key is
(ranking_system, snapshot_date, position) where position = 1-based list order;
rank is stored as-is from source and can repeat.

- Add position INTEGER NOT NULL (after backfill)
- Backfill position = row order per (system, date) by rank, id
- Drop UNIQUE(ranking_system, snapshot_date, rank)
- Add UNIQUE(ranking_system, snapshot_date, position)
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade():
    # Add position nullable first for backfill
    op.add_column("rankings", sa.Column("position", sa.Integer(), nullable=True))
    conn = op.get_bind()
    # Backfill: position = row number per (ranking_system, snapshot_date) order by rank, id
    conn.execute(text("""
        UPDATE rankings r
        SET position = t.rn
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY ranking_system, snapshot_date ORDER BY rank ASC, id ASC) AS rn
            FROM rankings
        ) t
        WHERE r.id = t.id
    """))
    op.alter_column(
        "rankings",
        "position",
        existing_type=sa.Integer(),
        nullable=False,
    )
    # Drop unique on rank (so rank can have ties)
    op.drop_constraint(
        "rankings_ranking_system_snapshot_date_rank_key",
        "rankings",
        type_="unique",
    )
    # Unique on position (one row per list slot)
    op.create_unique_constraint(
        "rankings_ranking_system_snapshot_date_position_key",
        "rankings",
        ["ranking_system", "snapshot_date", "position"],
    )


def downgrade():
    op.drop_constraint(
        "rankings_ranking_system_snapshot_date_position_key",
        "rankings",
        type_="unique",
    )
    op.create_unique_constraint(
        "rankings_ranking_system_snapshot_date_rank_key",
        "rankings",
        ["ranking_system", "snapshot_date", "rank"],
    )
    op.drop_column("rankings", "position")