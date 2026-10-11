"""Physical association rankings tables (WPBA, Fargo, WPA men/women, Heyball, Artistic).

Revision ID: 049
Revises: 048
Create Date: 2026-03-25

Mirrored from legacy `rankings` rows on each save for the matching ranking_system /
ranking_variant. See database/postgres_manager.py `_mirror_rankings_to_association_table`.
"""

from alembic import op
from sqlalchemy import text

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None

TABLES = (
    "wpba_rankings",
    "fargo_rankings",
    "wpa_men_rankings",
    "wpa_women_rankings",
    "heyball_men_rankings",
    "heyball_women_rankings",
    "artistic_rankings",
)


def upgrade():
    for tbl in TABLES:
        op.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                id SERIAL PRIMARY KEY,
                player_name VARCHAR(512) NOT NULL,
                ranking_variant VARCHAR(256) NOT NULL,
                rank INTEGER NOT NULL,
                points DOUBLE PRECISION NOT NULL DEFAULT 0,
                country VARCHAR(255),
                license_number VARCHAR(255),
                stops_played INTEGER,
                snapshot_date DATE NOT NULL,
                source_data JSONB,
                position INTEGER,
                fargo_rating DOUBLE PRECISION,
                alfa_rating DOUBLE PRECISION,
                fargo_robustness INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (ranking_variant, snapshot_date, position)
            );
            CREATE INDEX IF NOT EXISTS ix_{tbl}_variant_snap ON {tbl} (ranking_variant, snapshot_date DESC);
            CREATE INDEX IF NOT EXISTS ix_{tbl}_player ON {tbl} (player_name);
            """
            )
        )


def downgrade():
    for tbl in reversed(TABLES):
        op.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
