"""Add country_source and license_source to rankings so we remember how data was found.

Revision ID: 024
Revises: 023
Create Date: 2026-03-01

Values: cross_system, wpa_archive, obvious_same_person, backfill_wpba, csv_import, dashboard_import, etc.
Existing fargo_source / fargo_name_format already track Fargo; this adds the same for country and license.
"""

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rankings",
        sa.Column("country_source", sa.String(255), nullable=True),
    )
    op.add_column(
        "rankings",
        sa.Column("license_source", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("rankings", "license_source")
    op.drop_column("rankings", "country_source")
