"""Add Digital Pool field columns on tournament_results.

Revision ID: 061
Revises: 060
Create Date: 2026-07-12
"""

from alembic import op
from sqlalchemy import text

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS seed INTEGER"))
    op.execute(text("ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS race_to INTEGER"))
    op.execute(
        text("ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS current_round VARCHAR(128)")
    )
    op.execute(
        text("ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS player_status VARCHAR(64)")
    )
    op.execute(
        text("ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS is_eliminated BOOLEAN")
    )


def downgrade() -> None:
    op.execute(text("ALTER TABLE tournament_results DROP COLUMN IF EXISTS is_eliminated"))
    op.execute(text("ALTER TABLE tournament_results DROP COLUMN IF EXISTS player_status"))
    op.execute(text("ALTER TABLE tournament_results DROP COLUMN IF EXISTS current_round"))
    op.execute(text("ALTER TABLE tournament_results DROP COLUMN IF EXISTS race_to"))
    op.execute(text("ALTER TABLE tournament_results DROP COLUMN IF EXISTS seed"))
