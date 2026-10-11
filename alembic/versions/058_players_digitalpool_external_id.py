"""Add players.digitalpool_player_id external key (Fargo enrichment from Digital Pool).

Revision ID: 058
Revises: 057
Create Date: 2026-06-09

Stores Digital Pool's authoritative player id on our `players` SSOT so Fargo
enrichment (scripts/enrich_players_fargo_from_digitalpool.py) can match by a
stable external key instead of re-deriving identity by name each run. The
initial linkage is seeded by exact canonical full-name equality against
DP-sourced `rankings` rows (whose names originate from Digital Pool), then
profiles are fetched by this id and `players.fargo_score` / `fargo_robustness`
/ `nationality` are filled (COALESCE only — never overriding existing values,
so the country-lock policy is respected).

Nullable + indexed (not UNIQUE: a DP id should map to one player, but we avoid a
hard constraint that could block a legitimate re-link during data cleanup).
"""

from alembic import op
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS digitalpool_player_id BIGINT"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_players_digitalpool_player_id "
        "ON players (digitalpool_player_id)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_players_digitalpool_player_id"))
    op.execute(text("ALTER TABLE players DROP COLUMN IF EXISTS digitalpool_player_id"))
