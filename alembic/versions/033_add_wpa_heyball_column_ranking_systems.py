"""Add WPA Heyball per-column ranking_system values (one button per column).

Revision ID: 033
Revises: 032
Create Date: 2026-03-02

Adds ranking_system values for each WPA Heyball event column so the UI can show
one button per column (e.g. World Championship, Asian Open, European Open)
instead of combining columns.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None

# One system per WPA Heyball event column
WPA_HEYBALL_COLUMN_SYSTEMS = [
    "WPA_Heyball_Men_WorldChamp",
    "WPA_Heyball_Men_10Ball",
    "WPA_Heyball_Men_Asian",
    "WPA_Heyball_Men_European",
    "WPA_Heyball_Men_NorthAmerican",
    "WPA_Heyball_Men_Oceania",
    "WPA_Heyball_Men_PanAmerican",
    "WPA_Heyball_Men_Champions",
    "WPA_Heyball_Women_WorldChamp",
    "WPA_Heyball_Women_Asian",
    "WPA_Heyball_Women_European",
    "WPA_Heyball_Women_NorthAmerican",
    "WPA_Heyball_Women_Oceania",
    "WPA_Heyball_Women_PanAmerican",
    "WPA_Heyball_Women_Champions",
]


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during upgrade 033: %s", e)
    existing = [
        "WPBA_Women", "WPA_Men", "WPA_Women", "WPBA", "WPA",
        "WPA_Heyball", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic",
        "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
        "Competitors_Pool_StraitPool", "Competitors_Pool_OnePocket", "Competitors_Pool_BankPool",
        "Competitors_Pool_Women_9Ball", "Competitors_Pool_Men_9Ball", "Competitors_Pool_Mixed_9Ball",
        "WPA_Men_Yalin_8Ball", "WPA_Men_Predator_10B", "WPA_Men_9B_WorldChamp",
        "WPA_Men_9B_ChinaOpen", "WPA_Men_9B_IntlOpen", "WPA_Men_10B_Indonesia",
        "WPA_Men_10B_Polish", "WPA_Men_10B_Qatar", "WPA_Men_Kamui_LasVegas",
        "WPA_Men_Maldives", "WPA_Men_HCM",
        "WPA_Women_8Ball", "WPA_Women_10B_Indonesia", "WPA_Women_10B_Predator",
        "WPA_Women_JapanOpen", "WPA_Women_Kamui_LasVegas",
    ]
    all_systems = existing + WPA_HEYBALL_COLUMN_SYSTEMS
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
        logger.debug("Could not drop rankings_ranking_system_check during downgrade 033: %s", e)
    existing = [
        "WPBA_Women", "WPA_Men", "WPA_Women", "WPBA", "WPA",
        "WPA_Heyball", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic",
        "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
        "Competitors_Pool_StraitPool", "Competitors_Pool_OnePocket", "Competitors_Pool_BankPool",
        "Competitors_Pool_Women_9Ball", "Competitors_Pool_Men_9Ball", "Competitors_Pool_Mixed_9Ball",
        "WPA_Men_Yalin_8Ball", "WPA_Men_Predator_10B", "WPA_Men_9B_WorldChamp",
        "WPA_Men_9B_ChinaOpen", "WPA_Men_9B_IntlOpen", "WPA_Men_10B_Indonesia",
        "WPA_Men_10B_Polish", "WPA_Men_10B_Qatar", "WPA_Men_Kamui_LasVegas",
        "WPA_Men_Maldives", "WPA_Men_HCM",
        "WPA_Women_8Ball", "WPA_Women_10B_Indonesia", "WPA_Women_10B_Predator",
        "WPA_Women_JapanOpen", "WPA_Women_Kamui_LasVegas",
    ]
    arr = ", ".join(repr(s) for s in existing)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))