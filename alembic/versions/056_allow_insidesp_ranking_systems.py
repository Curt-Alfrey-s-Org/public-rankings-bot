"""Allow InsideSpin_<discipline> ranking systems (multi-source: insidesp.in).

Revision ID: 056
Revises: 055
Create Date: 2026-06-09

Phase 2 of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. The Inside Spin Tier-1
scraper saves per-discipline ratings into the `rankings` table under
`InsideSpin_9Ball` / `InsideSpin_10Ball` / `InsideSpin_8Ball` /
`InsideSpin_OnePocket` (Inside Spin's own Display Rating + Matches Rated land in
`rankings.source_data`). These are a *separate* rating source, never merged with
WPA/WPBA/Digital Pool rank lists.

Adds `OR ranking_system ~ '^InsideSpin_[A-Za-z0-9_]+$'` to the existing
`rankings_ranking_system_check`. Extends 054; downgrade restores the 054 body.
"""

from alembic import op
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None

# 054's IN(...) whitelist, reused verbatim by both upgrade and downgrade so the
# only delta between revisions is the InsideSpin regex alternative.
_IN_LIST = """
            ranking_system IN (
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
"""


def upgrade() -> None:
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)

    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (
            ranking_system::text ~ '^WPBA_Women_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^WPA_Women_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^WPA_Men_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^InsideSpin_[A-Za-z0-9_]+$'
            OR {_IN_LIST}
        )
    """))


def downgrade() -> None:
    try:
        op.execute(text("ALTER TABLE rankings DROP CONSTRAINT IF EXISTS rankings_ranking_system_check"))
    except Exception as e:
        logger.debug("Could not drop rankings_ranking_system_check: %s", e)
    op.execute(text(f"""
        ALTER TABLE rankings ADD CONSTRAINT rankings_ranking_system_check
        CHECK (
            ranking_system::text ~ '^WPBA_Women_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^WPA_Women_[A-Za-z0-9_]+$'
            OR ranking_system::text ~ '^WPA_Men_[A-Za-z0-9_]+$'
            OR {_IN_LIST}
        )
    """))
