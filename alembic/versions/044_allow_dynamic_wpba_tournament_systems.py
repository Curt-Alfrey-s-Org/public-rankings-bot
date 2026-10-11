"""Allow dynamic WPBA_Women_* tournament systems for PDF-discovered columns.

Revision ID: 044
Revises: 043
Create Date: 2026-03-16

When a new WPBA PDF has new tournament columns, split_wpba_women_to_column_buttons
can create ranking_system entries like WPBA_Women_NewTournament. This migration
relaxes the CHECK constraint to allow any system matching WPBA_Women_[A-Za-z0-9_]+
in addition to the existing fixed list. Additive only; no data wipe.
"""

from alembic import op
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)

    # Allow existing systems OR any WPBA_Women_* (dynamic tournament buttons)
    op.execute(text("""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (
            ranking_system::text ~ '^WPBA_Women_[A-Za-z0-9_]+$'
            OR ranking_system IN (
                'WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA',
                'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic',
                'LOCAL',
                'WPBA_Women_IronCityVI', 'WPBA_Women_Jacoby2025', 'WPBA_Women_Colorado2025',
                'WPBA_Women_SoaringEagle2025', 'WPBA_Women_RaxxMezz2025', 'WPBA_Women_DRPool2025',
                'WPBA_Women_Jacoby2024', 'WPBA_Women_CapitalCity2024', 'WPBA_Women_NAPA2024',
                'WPBA_Women_Colorado2024', 'WPBA_Women_Palmetto', 'WPBA_Women_IronCityV',
                'Competitors_Pool_9Ball', 'Competitors_Pool_10Ball', 'Competitors_Pool_8Ball',
                'Competitors_Pool_StraitPool', 'Competitors_Pool_OnePocket', 'Competitors_Pool_BankPool',
                'Competitors_Pool_Women_9Ball', 'Competitors_Pool_Men_9Ball', 'Competitors_Pool_Mixed_9Ball',
                'WPA_Men_Yalin_8Ball', 'WPA_Men_Predator_10B', 'WPA_Men_9B_WorldChamp',
                'WPA_Men_9B_ChinaOpen', 'WPA_Men_9B_IntlOpen', 'WPA_Men_10B_Indonesia',
                'WPA_Men_10B_Polish', 'WPA_Men_10B_Qatar', 'WPA_Men_Kamui_LasVegas',
                'WPA_Men_Maldives', 'WPA_Men_HCM',
                'WPA_Women_8Ball', 'WPA_Women_10B_Indonesia', 'WPA_Women_10B_Predator',
                'WPA_Women_JapanOpen', 'WPA_Women_Kamui_LasVegas', 'WPA_Women_9Ball', 'WPA_Women_ChinaOpen',
                'WPA_Heyball_Men_WorldChamp', 'WPA_Heyball_Men_10Ball',
                'WPA_Heyball_Men_Asian', 'WPA_Heyball_Men_European',
                'WPA_Heyball_Men_NorthAmerican', 'WPA_Heyball_Men_Oceania',
                'WPA_Heyball_Men_PanAmerican', 'WPA_Heyball_Men_Champions',
                'WPA_Heyball_Women_WorldChamp', 'WPA_Heyball_Women_Asian',
                'WPA_Heyball_Women_European', 'WPA_Heyball_Women_NorthAmerican',
                'WPA_Heyball_Women_Oceania', 'WPA_Heyball_Women_PanAmerican',
                'WPA_Heyball_Women_Champions',
                'WPA_Artistic_2019_CAO', 'WPA_Artistic_2019_WC', 'WPA_Artistic_2021_NC',
                'WPA_Artistic_2022_NC', 'WPA_Artistic_2022_WC', 'WPA_Artistic_2023_MC',
                'WPA_Artistic_2023_SAO',
                'WPA_Men_JPBA_JapanOpen', 'WPA_Women_9B_WorldChamp', 'WPA_Women_LittleMonster',
                'WPA_Women_AllJapan57', 'WPA_Women_DRPoolTour', 'WPA_Women_WPBA_Colorado',
                'WPA_Women_WPBA_IronCity', 'WPA_Women_WPBA_RaxxMezz', 'WPA_Women_WPBA_SEMasters'
            )
        )
    """))


def downgrade():
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)
    # Re-add 041-style constraint (no dynamic WPBA_Women_*)
    systems = [
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
        "WPA_Women_JapanOpen", "WPA_Women_Kamui_LasVegas", "WPA_Women_9Ball", "WPA_Women_ChinaOpen",
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
        "WPA_Men_JPBA_JapanOpen", "WPA_Women_9B_WorldChamp", "WPA_Women_LittleMonster",
        "WPA_Women_AllJapan57", "WPA_Women_DRPoolTour", "WPA_Women_WPBA_Colorado",
        "WPA_Women_WPBA_IronCity", "WPA_Women_WPBA_RaxxMezz", "WPA_Women_WPBA_SEMasters",
        "LOCAL",
    ]
    arr = ", ".join(repr(s) for s in systems)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (ranking_system::text = ANY (ARRAY[{arr}]::text[]))
    """))
