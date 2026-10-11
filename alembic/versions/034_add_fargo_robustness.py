"""Add fargo_robustness column to rankings table.

Revision ID: 034
Revises: 033
Create Date: 2026-03-02

Stores the FargoRate robustness value (total games played) alongside the
fargo_rating.  The value comes from the same TopListsForWeb API response
that already provides FargoRating.
"""

from alembic import op
import sqlalchemy as sa

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rankings", sa.Column("fargo_robustness", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("rankings", "fargo_robustness")
