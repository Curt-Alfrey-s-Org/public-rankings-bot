"""Add users.nickname column for display name customization.

Revision ID: 020
Revises: 019
Create Date: 2026-02-18

Adds users.nickname (VARCHAR 100, nullable) for profile display names.
Fixes: column users.nickname does not exist (login/auth failures).
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    existing = [col["name"] for col in inspector.get_columns("users")]
    if "nickname" not in existing:
        op.add_column("users", sa.Column("nickname", sa.String(100), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    existing = [col["name"] for col in inspector.get_columns("users")]
    if "nickname" in existing:
        op.drop_column("users", "nickname")
