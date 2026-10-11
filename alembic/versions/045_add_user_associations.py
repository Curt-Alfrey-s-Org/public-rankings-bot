"""Add user_associations table and requires_email_setup/force_password_reset fields.

Revision ID: 045
Revises: 044
Create Date: 2026-03-18

Adds user_associations table to track which associations (WPBA_Women, WPA_Women, WPA_Men)
each user belongs to. Also adds requires_email_setup and force_password_reset boolean
fields to users table for Fargo account creation workflow.
"""

from alembic import op
from sqlalchemy import text

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade():
    # One statement per column so partial failures are visible (avoids silent ORM/DB mismatch).
    op.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS requires_email_setup BOOLEAN DEFAULT FALSE"
        )
    )
    op.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_reset BOOLEAN DEFAULT FALSE"
        )
    )
    
    # Create user_associations table
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS user_associations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            association VARCHAR(32) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, association)
        )
    """))
    
    # Create indexes
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_user_associations_user_id 
        ON user_associations(user_id)
    """))
    
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_user_associations_association 
        ON user_associations(association)
    """))


def downgrade():
    # Drop user_associations table
    op.execute(text("DROP TABLE IF EXISTS user_associations"))

    op.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS requires_email_setup"))
    op.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS force_password_reset"))
