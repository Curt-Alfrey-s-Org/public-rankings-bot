"""Allow dynamic WPA_Women_* tournament systems for HTML-discovered columns.

Revision ID: 051
Revises: 050
Create Date: 2026-04-07

Mirrors 044 (WPBA_Women_*): when WPA adds a new event column on wpapool.com,
split_wpa_women_to_column_buttons may create ranking_system values not listed
in the fixed IN (...). Adds OR ranking_system ~ '^WPA_Women_[A-Za-z0-9_]+$'.
Base WPA_Women row does not match (requires a suffix after WPA_Women_).
"""

from alembic import op
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)

    op.execute(text("""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (
            ranking_system::text ~ '^WPBA_Women_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^WPA_Women_[A-Za-z0-9_]+$'
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


def downgrade() -> None:
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)
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
