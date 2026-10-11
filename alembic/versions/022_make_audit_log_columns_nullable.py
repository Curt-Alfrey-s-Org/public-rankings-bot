"""Make audit_log actor_role, actor_subject, action nullable for login event logging.

Revision ID: 022
Revises: 021
Create Date: 2026-02-23 17:34:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    """Make actor_role, actor_subject, action nullable for login event logging."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Check if audit_log exists and inspect existing columns
    if "audit_log" in inspector.get_table_names():
        existing = [c["name"] for c in inspector.get_columns("audit_log")]
        
        # Add columns if they don't exist
        if "actor_role" not in existing:
            op.add_column('audit_log', sa.Column('actor_role', sa.String(64), nullable=True))
        else:
            # Modify actor_role to be nullable (if it already exists)
            op.alter_column(
                'audit_log',
                'actor_role',
                existing_type=sa.String(64),
                nullable=True
            )
        
        # Add actor_subject if it doesn't exist
        if "actor_subject" not in existing:
            op.add_column('audit_log', sa.Column('actor_subject', sa.String(255), nullable=True))
        else:
            # Modify actor_subject to be nullable (if it already exists)
            op.alter_column(
                'audit_log',
                'actor_subject',
                existing_type=sa.String(255),
                nullable=True
            )
        
        # Add action if it doesn't exist
        if "action" not in existing:
            op.add_column('audit_log', sa.Column('action', sa.String(128), nullable=True))
        else:
            # Modify action to be nullable (if it already exists)
            op.alter_column(
                'audit_log',
                'action',
                existing_type=sa.String(128),
                nullable=True
            )


def downgrade():
    """Revert audit_log columns to NOT NULL."""
    op.alter_column(
        'audit_log',
        'actor_role',
        existing_type=sa.String(64),
        nullable=False
    )
    
    op.alter_column(
        'audit_log',
        'actor_subject',
        existing_type=sa.String(255),
        nullable=False
    )
    
    op.alter_column(
        'audit_log',
        'action',
        existing_type=sa.String(128),
        nullable=False
    )
