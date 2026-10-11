"""Add player_name_aliases table for fuzzy name resolution.

Revision ID: 019
Revises: 018
Create Date: 2026-02-17

Stores scraped_name -> canonical_name mappings so that when a scrape returns
a name that fuzzy-matches an existing player, we update the existing row
instead of creating a duplicate. Ensures country, license, fargo persist.
"""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    """Create player_name_aliases table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Check if players table exists (foreign key requirement)
    if 'players' not in inspector.get_table_names():
        print("⚠ players table not found, skipping migration (run schema_postgres.sql first)")
        return
    
    op.create_table(
        "player_name_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scraped_name", sa.String(255), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("ranking_system", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_player_name_aliases_lookup",
        "player_name_aliases",
        ["scraped_name", "ranking_system"],
        unique=True,
    )


def downgrade():
    """Drop player_name_aliases table."""
    op.drop_index("idx_player_name_aliases_lookup", table_name="player_name_aliases")
    op.drop_table("player_name_aliases")
