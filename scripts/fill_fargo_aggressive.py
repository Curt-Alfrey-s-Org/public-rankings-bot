#!/usr/bin/env python3
"""
Aggressive Fargo fill: name variations + FairMatch per-player lookup.

For every ranked player missing a Fargo rating, generate name variations
and try each on fairmatch.fargorate.com via Selenium.  Rate-limited to
avoid hammering the site.

Usage:
    python3 scripts/fill_fargo_aggressive.py [--dry-run] [--limit N] [--system SYS]

Options:
    --dry-run    Show what would be looked up without writing to DB
    --limit N    Only try the first N missing players (default: all)
    --system SYS Only fill for a specific ranking_system (e.g. WPA_Artistic)
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

ALL_SYSTEMS = [
    "WPBA_Women", "WPA_Men", "WPA_Women",
    "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic",
]

DELAY_BETWEEN_LOOKUPS = 1.5


def get_missing_players(engine, systems):
    """Return list of (player_name, ranking_system) for players missing Fargo."""
    from sqlalchemy import text
    rows = []
    with engine.connect() as conn:
        for sys_name in systems:
            result = conn.execute(text("""
                SELECT DISTINCT player_name, ranking_system
                FROM rankings
                WHERE ranking_system = :sys
                AND snapshot_date = (
                    SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = :sys
                )
                AND (fargo_rating IS NULL)
                AND player_name IS NOT NULL
                ORDER BY player_name
            """), {"sys": sys_name})
            rows.extend(result.fetchall())
    seen = set()
    unique = []
    for name, system in rows:
        if name not in seen:
            seen.add(name)
            unique.append((name, system))
    return unique


def try_fairmatch_lookup(player_name):
    """Try FairMatch lookup with name variations. Returns (rating, source_name) or (None, None).

    Only tries variations with 2+ words to avoid false-positive matches
    on single-word names like 'Diaz' or 'Andrew'.
    Tries the original full name first, then generated variations.
    """
    from api.services.fargo_name_variations import generate_name_variations
    from api.services.fairmatch_scraper import lookup_rating

    variations = generate_name_variations(player_name)
    full_name_variants = [v for v in variations if len(v.split()) >= 2]
    if not full_name_variants:
        full_name_variants = [player_name]

    for variant in full_name_variants:
        try:
            rating, err = lookup_rating(variant)
            if rating is not None:
                return rating, variant
            time.sleep(0.5)
        except Exception as e:
            logger.debug("FairMatch error for '%s' (variant '%s'): %s", player_name, variant, e)
    return None, None


def update_fargo_in_db(engine, player_name, rating, source_name):
    """Write Fargo rating to all ranking rows for this player."""
    from sqlalchemy import text
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE rankings
            SET fargo_rating = :rating,
                fargo_last_updated = :updated,
                fargo_robustness = NULL
            WHERE player_name = :name
            AND fargo_rating IS NULL
        """), {"rating": rating, "updated": now_iso, "name": player_name})
        conn.commit()
        return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Aggressive Fargo fill via FairMatch")
    parser.add_argument("--dry-run", action="store_true", help="Show lookups without writing")
    parser.add_argument("--limit", type=int, default=0, help="Max players to try (0=all)")
    parser.add_argument("--system", type=str, default="", help="Only fill for this system")
    args = parser.parse_args()

    os.environ.setdefault("DATABASE_URL", "postgresql://rankingsbot_user:change-me@rankings-bot-postgres:5432/rankingsbot")
    from database import get_database_manager
    db = get_database_manager()

    systems = [args.system] if args.system else ALL_SYSTEMS
    missing = get_missing_players(db.engine, systems)
    if args.limit > 0:
        missing = missing[:args.limit]

    logger.info("Players missing Fargo: %d (systems: %s)", len(missing), ", ".join(systems))
    if not missing:
        logger.info("All players have Fargo ratings!")
        return

    matched = 0
    unmatched = 0
    unmatched_names = []

    for i, (name, system) in enumerate(missing, 1):
        logger.info("[%d/%d] Looking up: %s (%s)", i, len(missing), name, system)
        if args.dry_run:
            from api.services.fargo_name_variations import generate_name_variations
            variations = generate_name_variations(name)
            logger.info("  Would try %d variations: %s", len(variations), variations[:5])
            continue

        rating, source_name = try_fairmatch_lookup(name)
        if rating is not None:
            rows_updated = update_fargo_in_db(db.engine, name, rating, source_name)
            matched += 1
            logger.info("  MATCHED: %s -> Fargo %s (via '%s', %d rows updated)",
                        name, rating, source_name, rows_updated)
        else:
            unmatched += 1
            unmatched_names.append(name)
            logger.info("  NOT FOUND: %s", name)

        time.sleep(DELAY_BETWEEN_LOOKUPS)

    logger.info("=" * 60)
    logger.info("RESULTS: %d matched, %d unmatched out of %d tried", matched, unmatched, len(missing))
    if unmatched_names:
        logger.info("Unmatched players:")
        for n in unmatched_names:
            logger.info("  - %s", n)


if __name__ == "__main__":
    main()
