"""Add WPA Artistic Pool per-event ranking_system values (one button per tournament).

Revision ID: 035
Revises: 034
Create Date: 2026-03-02

Adds ranking_system values for each Artistic Pool event so the UI can show
one button per tournament (e.g. 2019 CAO, 2022 WC, 2023 MC) plus the
existing WPA_Artistic overall.
"""

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

WPA_ARTISTIC_EVENT_SYSTEMS = [
    "WPA_Artistic_2019_CAO",
    "WPA_Artistic_2019_WC",
    "WPA_Artistic_2021_NC",
    "WPA_Artistic_2022_NC",
    "WPA_Artistic_2022_WC",
    "WPA_Artistic_2023_MC",
    "WPA_Artistic_2023_SAO",
]

ARTISTIC_RANKING_TYPES = [
    ("WPA_Artistic_2019_CAO", "2019 Coughlin Auto Open", "WPA", "Artistic"),
    ("WPA_Artistic_2019_WC", "2019 World Championship", "WPA", "Artistic"),
    ("WPA_Artistic_2021_NC", "2021 National Championship", "WPA", "Artistic"),
    ("WPA_Artistic_2022_NC", "2022 National Championship", "WPA", "Artistic"),
    ("WPA_Artistic_2022_WC", "2022 World Championship", "WPA", "Artistic"),
    ("WPA_Artistic_2023_MC", "2023 Masters Championship", "WPA", "Artistic"),
    ("WPA_Artistic_2023_SAO", "2023 South African Open", "WPA", "Artistic"),
]

# All systems from migration 033 (current state) plus 034 (no new systems).
_EXISTING = [
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
    "WPA_Heyball_Men_WorldChamp", "WPA_Heyball_Men_10Ball",
    "WPA_Heyball_Men_Asian", "WPA_Heyball_Men_European",
    "WPA_Heyball_Men_NorthAmerican", "WPA_Heyball_Men_Oceania",
    "WPA_Heyball_Men_PanAmerican", "WPA_Heyball_Men_Champions",
    "WPA_Heyball_Women_WorldChamp", "WPA_Heyball_Women_Asian",
    "WPA_Heyball_Women_European", "WPA_Heyball_Women_NorthAmerican",
    "WPA_Heyball_Women_Oceania", "WPA_Heyball_Women_PanAmerican",
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
        logger.debug("Could not drop rankings_ranking_system_check during upgrade 035: %s", e)

    all_systems = _EXISTING + WPA_ARTISTIC_EVENT_SYSTEMS
    arr = ", ".join(repr(s) for s in all_systems)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))

    if "ranking_types" in inspector.get_table_names():
        for code, display, org, division in ARTISTIC_RANKING_TYPES:
            conn.execute(text("""
                INSERT INTO ranking_types (code, display_name, org_code, division, is_active)
                VALUES (:code, :display, :org, :div, true)
                ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, is_active = true
            """), {"code": code, "display": display, "org": org, "div": division})


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rankings" not in inspector.get_table_names():
        return

    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check during downgrade 035: %s", e)

    arr = ", ".join(repr(s) for s in _EXISTING)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))

    if "ranking_types" in inspector.get_table_names():
        for code, _, _, _ in ARTISTIC_RANKING_TYPES:
            op.execute(text("DELETE FROM ranking_types WHERE code = :code"), {"code": code})
