"""Add WPA_Heyball_Men and WPA_Heyball_Women to rankings.ranking_system CHECK.

Revision ID: 018
Revises: 017
Create Date: 2026-02-17

Supports Men's and Women's Heyball rankings from WPA previous-ranking page.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    """Expand ranking_system CHECK to include WPA_Heyball_Men and WPA_Heyball_Women."""
    conn = op.get_bind()
    
    # Check if rankings table exists
    inspector = sa.inspect(conn)
    if 'rankings' not in inspector.get_table_names():
        print("⚠ rankings table not found, skipping migration (run schema_postgres.sql first)")
        return
    
    try:
        result = conn.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'rankings'::regclass AND contype = 'c'
            AND pg_get_constraintdef(oid) LIKE '%ranking_system%'
        """))
        for row in result:
            cname = row[0]
            conn.execute(text(f'ALTER TABLE rankings DROP CONSTRAINT IF EXISTS "{cname}"'))
    except Exception:
        conn.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    op.execute(text("""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system IN (
            'WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA',
            'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic'
        ))
    """))
    op.execute(text("""
        INSERT INTO ranking_types (code, display_name, org_code, division, is_active)
        VALUES ('WPA_Heyball_Men', 'WPA Heyball Men', 'WPA', 'Heyball Men', true),
               ('WPA_Heyball_Women', 'WPA Heyball Women', 'WPA', 'Heyball Women', true)
        ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, is_active = true
    """))


def downgrade():
    """Revert CHECK to 017 state."""
    conn = op.get_bind()
    try:
        result = conn.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'rankings'::regclass AND contype = 'c'
            AND pg_get_constraintdef(oid) LIKE '%ranking_system%'
        """))
        for row in result:
            conn.execute(text(f'ALTER TABLE rankings DROP CONSTRAINT IF EXISTS "{row[0]}"'))
    except Exception:
        conn.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    op.execute(text("""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system IN (
            'WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA',
            'WPA_Heyball', 'WPA_Artistic'
        ))
    """))
