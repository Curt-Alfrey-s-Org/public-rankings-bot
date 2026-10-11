"""Add tournaments.is_test_tournament column to filter test tournaments.

Revision ID: 021
Revises: 020
Create Date: 2026-02-20

Adds tournaments.is_test_tournament (BOOLEAN, nullable, default FALSE) 
to allow filtering test tournaments from production views.
Fixes: column tournaments.is_test_tournament does not exist.
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tournaments" not in inspector.get_table_names():
        return
    existing = [col["name"] for col in inspector.get_columns("tournaments")]
    if "is_test_tournament" not in existing:
        op.add_column("tournaments", sa.Column("is_test_tournament", sa.Boolean(), nullable=True, server_default='FALSE'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tournaments" not in inspector.get_table_names():
        return
    existing = [col["name"] for col in inspector.get_columns("tournaments")]
    if "is_test_tournament" in existing:
        op.drop_column("tournaments", "is_test_tournament")
