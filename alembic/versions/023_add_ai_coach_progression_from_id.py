"""Add progression_from_id to ai_coach_analyses for progression review.

Revision ID: 023
Revises: 022
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'ai_coach_analyses',
        sa.Column('progression_from_id', sa.String(36), nullable=True)
    )
    op.create_index(
        'idx_ai_coach_analyses_progression_from',
        'ai_coach_analyses',
        ['progression_from_id'],
        unique=False
    )


def downgrade():
    op.drop_index('idx_ai_coach_analyses_progression_from', table_name='ai_coach_analyses')
    op.drop_column('ai_coach_analyses', 'progression_from_id')
