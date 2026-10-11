"""Idempotent repair: users columns + user_associations (ORM parity).

Revision ID: 046
Revises: 045
Create Date: 2026-03-19

Repairs deployments where revision 045 was recorded but ALTER TABLE on users
failed silently (older 045 used try/except) or where preferences_json was never
added via ad-hoc scripts. Without these columns, SQLAlchemy loads of User rows
return 500 for GET /api/users and /api/users/profile/me.
"""

from alembic import op
from sqlalchemy import text

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade():
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
    op.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences_json TEXT DEFAULT '{}'"
        )
    )

    op.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS user_associations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            association VARCHAR(32) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, association)
        )
    """
        )
    )
    op.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS idx_user_associations_user_id
        ON user_associations(user_id)
    """
        )
    )
    op.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS idx_user_associations_association
        ON user_associations(association)
    """
        )
    )


def downgrade():
    pass
