"""Add WPA Men per-column ranking_system values (one button per column).

Revision ID: 031
Revises: 030
Create Date: 2026-03-01

Adds ranking_system values for each WPA Men event column so the UI can show
one button per column (e.g. Yalin 8-Ball, Predator 10-Ball, 9-Ball World Champs)
instead of combining columns.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

# One system per WPA Men event column (max 32 chars each)
WPA_MEN_COLUMN_SYSTEMS = [
    "WPA_Men_Yalin_8Ball",
    "WPA_Men_Predator_10B",
    "WPA_Men_9B_WorldChamp",
    "WPA_Men_9B_ChinaOpen",
    "WPA_Men_9B_IntlOpen",
    "WPA_Men_10B_Indonesia",
    "WPA_Men_10B_Polish",
    "WPA_Men_10B_Qatar",
    "WPA_Men_Kamui_LasVegas",
    "WPA_Men_Maldives",
    "WPA_Men_HCM",
]


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during upgrade 031: %s", e)
    existing = [
        "WPBA_Women", "WPA_Men", "WPA_Women", "WPBA", "WPA",
        "WPA_Heyball", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic",
        "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
        "Competitors_Pool_StraitPool", "Competitors_Pool_OnePocket", "Competitors_Pool_BankPool",
        "Competitors_Pool_Women_9Ball", "Competitors_Pool_Men_9Ball", "Competitors_Pool_Mixed_9Ball",
    ]
    all_systems = existing + WPA_MEN_COLUMN_SYSTEMS
    arr = ", ".join(repr(s) for s in all_systems)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during downgrade 031: %s", e)
    existing = [
        "WPBA_Women", "WPA_Men", "WPA_Women", "WPBA", "WPA",
        "WPA_Heyball", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic",
        "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
        "Competitors_Pool_StraitPool", "Competitors_Pool_OnePocket", "Competitors_Pool_BankPool",
        "Competitors_Pool_Women_9Ball", "Competitors_Pool_Men_9Ball", "Competitors_Pool_Mixed_9Ball",
    ]
    arr = ", ".join(repr(s) for s in existing)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))
