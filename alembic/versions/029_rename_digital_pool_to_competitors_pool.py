"""Rename Digital Pool to CP in ranking_types and rankings.

Revision ID: 029
Revises: 028
Create Date: 2026-03-01

Replaces all references to Digital_Pool_* with Competitors_Pool_* in code,
display_name, and ranking_system. User-facing label is 'CP' (see 030 for display_name update).
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "ranking_types" in inspector.get_table_names():
        op.execute(text("""
            UPDATE ranking_types
            SET code = REPLACE(code, 'Digital_Pool_', 'Competitors_Pool_'),
                display_name = REPLACE(display_name, 'Digital Pool', 'Competitors Pool')
            WHERE code LIKE 'Digital_Pool_%'
        """))

    if "rankings" in inspector.get_table_names():
        op.execute(text("""
            UPDATE rankings
            SET ranking_system = REPLACE(ranking_system, 'Digital_Pool_', 'Competitors_Pool_')
            WHERE ranking_system LIKE 'Digital_Pool_%'
        """))
        # Re-add check constraint with Competitors_Pool_* values
        try:
            result = conn.execute(text("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'rankings'::regclass AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%ranking_system%'
            """))
            for row in result:
                op.execute(text(f'ALTER TABLE rankings DROP CONSTRAINT IF EXISTS "{row[0]}"'))
        except Exception:
            op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
        op.execute(text("""
            ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
            CHECK (ranking_system::text = ANY (ARRAY[
                'WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA',
                'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic',
                'Competitors_Pool_9Ball', 'Competitors_Pool_10Ball', 'Competitors_Pool_8Ball',
                'Competitors_Pool_StraitPool', 'Competitors_Pool_OnePocket', 'Competitors_Pool_BankPool',
                'Competitors_Pool_Women_9Ball', 'Competitors_Pool_Men_9Ball', 'Competitors_Pool_Mixed_9Ball'
            ]::text[]))
        """))

    if "digital_pool_metadata" in inspector.get_table_names():
        op.execute(text("""
            UPDATE digital_pool_metadata
            SET ranking_system = REPLACE(ranking_system, 'Digital_Pool_', 'Competitors_Pool_')
            WHERE ranking_system LIKE 'Digital_Pool_%'
        """))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "ranking_types" in inspector.get_table_names():
        op.execute(text("""
            UPDATE ranking_types
            SET code = REPLACE(code, 'Competitors_Pool_', 'Digital_Pool_'),
                display_name = REPLACE(display_name, 'Competitors Pool', 'Digital Pool')
            WHERE code LIKE 'Competitors_Pool_%'
        """))

    if "rankings" in inspector.get_table_names():
        op.execute(text("""
            UPDATE rankings
            SET ranking_system = REPLACE(ranking_system, 'Competitors_Pool_', 'Digital_Pool_')
            WHERE ranking_system LIKE 'Competitors_Pool_%'
        """))
        try:
            result = conn.execute(text("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'rankings'::regclass AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%ranking_system%'
            """))
            for row in result:
                op.execute(text(f'ALTER TABLE rankings DROP CONSTRAINT IF EXISTS "{row[0]}"'))
        except Exception:
            op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
        op.execute(text("""
            ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
            CHECK (ranking_system::text = ANY (ARRAY[
                'WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA',
                'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic',
                'Digital_Pool_9Ball', 'Digital_Pool_10Ball', 'Digital_Pool_8Ball',
                'Digital_Pool_StraitPool', 'Digital_Pool_OnePocket', 'Digital_Pool_BankPool',
                'Digital_Pool_Women_9Ball', 'Digital_Pool_Men_9Ball', 'Digital_Pool_Mixed_9Ball'
            ]::text[]))
        """))

    if "digital_pool_metadata" in inspector.get_table_names():
        op.execute(text("""
            UPDATE digital_pool_metadata
            SET ranking_system = REPLACE(ranking_system, 'Competitors_Pool_', 'Digital_Pool_')
            WHERE ranking_system LIKE 'Competitors_Pool_%'
        """))
