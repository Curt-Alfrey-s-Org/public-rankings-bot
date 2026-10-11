"""Add created_at to audit_log if missing.

Revision ID: 043
Revises: 042
Create Date: 2026-03-16

Some deployments (e.g. after fix_audit_log_schema.sql or different init)
may have audit_log without created_at. This ensures the column exists
so GET /rankings/audit works.
"""

from alembic import op
from sqlalchemy import text

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Add created_at if missing; backfill from timestamp if that column exists
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'created_at'
            ) THEN
                ALTER TABLE audit_log ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'timestamp'
                ) THEN
                    UPDATE audit_log SET created_at = timestamp WHERE created_at IS NULL;
                END IF;
            END IF;
        END $$;
    """))


def downgrade():
    # No downgrade - removing created_at could break existing code
    pass
