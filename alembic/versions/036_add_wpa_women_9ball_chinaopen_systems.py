"""Add WPA Women per-event systems for 9-Ball and China Open.

Revision ID: 036
Revises: 035
Create Date: 2026-03-03
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None

NEW_SYSTEMS = [
    "WPA_Women_9Ball",
    "WPA_Women_ChinaOpen",
]

NEW_RANKING_TYPES = [
    ("WPA_Women_9Ball", "WPA Women 9-Ball", "WPA", "Women"),
    ("WPA_Women_ChinaOpen", "WPA Women China Open", "WPA", "Women"),
]

_EXISTING = [
    "WPBA_Women", "WPA_Men", "WPA_Women", "WPBA", "WPA",
    "WPBA_Women_IronCityVI", "WPBA_Women_Jacoby2025", "WPBA_Women_Colorado2025",
    "WPBA_Women_SoaringEagle2025", "WPBA_Women_RaxxMezz2025", "WPBA_Women_DRPool2025",
    "WPBA_Women_Jacoby2024", "WPBA_Women_CapitalCity2024", "WPBA_Women_NAPA2024",
    "WPBA_Women_Colorado2024", "WPBA_Women_Palmetto",
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
    "WPA_Heyball_Men_WorldChamp", "WPA_Heyball_Men_10Ball",
    "WPA_Heyball_Men_Asian", "WPA_Heyball_Men_European",
    "WPA_Heyball_Men_NorthAmerican", "WPA_Heyball_Men_Oceania",
    "WPA_Heyball_Men_PanAmerican", "WPA_Heyball_Men_Champions",
    "WPA_Heyball_Women_WorldChamp", "WPA_Heyball_Women_Asian",
    "WPA_Heyball_Women_European", "WPA_Heyball_Women_NorthAmerican",
    "WPA_Heyball_Women_Oceania", "WPA_Heyball_Women_PanAmerican",
    "WPA_Heyball_Women_Champions",
    "WPA_Artistic_2019_CAO", "WPA_Artistic_2019_WC", "WPA_Artistic_2021_NC",
    "WPA_Artistic_2022_NC", "WPA_Artistic_2022_WC", "WPA_Artistic_2023_MC",
    "WPA_Artistic_2023_SAO",
]


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return

    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during upgrade 036: %s", e)

    arr = ", ".join(repr(s) for s in (_EXISTING + NEW_SYSTEMS))
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))

    if "ranking_types" in inspector.get_table_names():
        for code, display, org, division in NEW_RANKING_TYPES:
            conn.execute(text("""
                INSERT INTO ranking_types (code, display_name, org_code, division, is_active)
                VALUES (:code, :display, :org, :division, true)
                ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, is_active = true
            """), {"code": code, "display": display, "org": org, "division": division})


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return

    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during downgrade 036: %s", e)

    arr = ", ".join(repr(s) for s in _EXISTING)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))

    if "ranking_types" in inspector.get_table_names():
        for code, _, _, _ in NEW_RANKING_TYPES:
            op.execute(text("DELETE FROM ranking_types WHERE code = :code"), {"code": code})
