"""Replace 'Competitors Pool' with 'CP' in ranking_types.display_name.

Revision ID: 030
Revises: 029
Create Date: 2026-03-01

Updates any display_name that contains 'Competitors Pool' to use 'CP' instead,
so the app shows 'CP' everywhere and the phrase 'Competitors Pool' is removed.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "ranking_types" not in inspector.get_table_names():
        return
    op.execute(text("""
        UPDATE ranking_types
        SET display_name = REPLACE(display_name, 'Competitors Pool', 'CP')
        WHERE display_name LIKE '%Competitors Pool%'
    """))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "ranking_types" not in inspector.get_table_names():
        return
    op.execute(text("""
        UPDATE ranking_types
        SET display_name = REPLACE(display_name, 'CP', 'Competitors Pool')
        WHERE display_name LIKE '%CP%' AND code LIKE 'Competitors_Pool_%'
    """))
