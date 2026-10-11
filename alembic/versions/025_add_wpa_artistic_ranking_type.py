"""Add WPA_Artistic (Artistic Pool Professional) to ranking_types.

Revision ID: 025
Revises: 024
Create Date: 2026-03-01

Displayed as 'Artistic Pool Professional' on the rankings page.
Data is scraped from https://wpapool.com/previous-ranking/ (ARTISTIC POOL PROFESSIONAL RANKINGS section).
"""

from alembic import op
from sqlalchemy import text

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("""
        INSERT INTO ranking_types (code, display_name, org_code, division, is_active)
        VALUES ('WPA_Artistic', 'Artistic Pool Professional', 'WPA', 'Artistic', true)
        ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, is_active = true
    """))


def downgrade():
    op.execute(text("""
        UPDATE ranking_types SET is_active = false WHERE code = 'WPA_Artistic'
    """))
