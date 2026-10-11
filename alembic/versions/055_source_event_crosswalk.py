"""Cross-source event crosswalk for multi-source de-dup (Digital Pool + Inside Spin).

Revision ID: 055
Revises: 054
Create Date: 2026-06-09

Maps each real tournament (one ``tournament_history.tournament_id``) to the
event ids it carries on external sources, so the same event scraped from
multiple sources (digitalpool.com, insidesp.in, ...) is never stored twice.

See docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md §3a. The repo does not auto-merge
two different ``tournament_id``s for the same event; this table is the explicit
crosswalk that the merge helper (``api/services/event_crosswalk.py``) maintains.

``(source, source_event_id)`` is UNIQUE so a given external event resolves to
exactly one local tournament. ``ON DELETE CASCADE`` keeps it tidy if the local
tournament row is removed.
"""

from alembic import op
from sqlalchemy import text

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS source_event_crosswalk (
            id              SERIAL PRIMARY KEY,
            tournament_id   VARCHAR(255) NOT NULL
                                REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
            source          VARCHAR(32)  NOT NULL,   -- 'digitalpool' | 'insidesp' | ...
            source_event_id VARCHAR(255) NOT NULL,   -- DP tournament/event id or slug; IS slug
            source_url      TEXT,
            match_method    VARCHAR(32),             -- 'date+name' | 'llm' | 'manual' | 'backfill'
            match_score     DOUBLE PRECISION,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_source_event UNIQUE (source, source_event_id)
        )
    """))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_source_event_crosswalk_tid "
        "ON source_event_crosswalk (tournament_id)"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_source_event_crosswalk_source "
        "ON source_event_crosswalk (source)"
    ))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS source_event_crosswalk"))
