#!/usr/bin/env python3
"""
Backfill WPBA country/license from WPA data by name match.

Uses latest snapshot per system. Only updates WPBA_Women rows where
country or license_number is missing.
"""

import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _fetch_wpa_lookup(cursor) -> dict:
    cursor.execute(
        """
        SELECT player_name, country, license_number
        FROM rankings
        WHERE ranking_system IN ('WPA_Men', 'WPA_Women')
        AND snapshot_date = (
            SELECT MAX(snapshot_date) FROM rankings
            WHERE ranking_system IN ('WPA_Men', 'WPA_Women')
        )
        """
    )
    lookup = {}
    for row in cursor.fetchall():
        name = (row[0] or "").strip().lower()
        if not name:
            continue
        lookup[name] = {
            "country": row[1],
            "license_number": row[2],
        }
    return lookup


def backfill(dry_run: bool) -> dict:
    db = get_database_manager()
    conn = db.get_connection()
    cursor = conn.cursor()

    wpa_lookup = _fetch_wpa_lookup(cursor)

    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'rankings' AND column_name = 'country_source'"
    )
    has_source_cols = cursor.fetchone() is not None

    cursor.execute(
        """
        SELECT player_name, country, license_number
        FROM rankings
        WHERE ranking_system = 'WPBA_Women'
        AND snapshot_date = (
            SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'
        )
        AND (country IS NULL OR country = '' OR license_number IS NULL OR license_number = '')
        """
    )
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        name = (row[0] or "").strip()
        key = name.lower()
        match = wpa_lookup.get(key)
        if not match:
            continue

        country = match.get("country")
        license_number = match.get("license_number")
        if not country and not license_number:
            continue

        logger.info("Backfill %s -> country=%s license=%s", name, country or "-", license_number or "-")
        updated += 1
        if not dry_run:
            if has_source_cols:
                cursor.execute(
                    """
                    UPDATE rankings
                    SET country = COALESCE(NULLIF(%s, ''), country),
                        license_number = COALESCE(NULLIF(%s, ''), license_number),
                        country_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'backfill_wpba' ELSE country_source END,
                        license_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'backfill_wpba' ELSE license_source END
                    WHERE ranking_system = 'WPBA_Women'
                    AND snapshot_date = (
                        SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'
                    )
                    AND player_name = %s
                    """,
                    (country, license_number, country or "", license_number or "", name),
                )
            else:
                cursor.execute(
                    """
                    UPDATE rankings
                    SET country = COALESCE(NULLIF(%s, ''), country),
                        license_number = COALESCE(NULLIF(%s, ''), license_number)
                    WHERE ranking_system = 'WPBA_Women'
                    AND snapshot_date = (
                        SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'
                    )
                    AND player_name = %s
                    """,
                    (country, license_number, name),
                )

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    conn.close()
    return {"updated": updated, "dry_run": dry_run}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill WPBA country/license from WPA data")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    result = backfill(dry_run=args.dry_run)
    logger.info("Done. Updated: %d, Dry run: %s", result["updated"], result["dry_run"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
