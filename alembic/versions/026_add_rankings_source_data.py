"""Add source_data JSONB to rankings for full import/PDF column storage.

Revision ID: 026
Revises: 025
Create Date: 2026-03-01

Stores all columns from each source (Heyball 18 cols, WPA Men/Women, WPBA PDF)
so the UI can display them. First-class columns remain for core fields; extra
columns from scrapes/imports go into source_data (PostgreSQL JSONB).
Ref: PostgreSQL JSONB docs https://www.postgresql.org/docs/current/datatype-json.html
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rankings",
        sa.Column("source_data", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("rankings", "source_data")
