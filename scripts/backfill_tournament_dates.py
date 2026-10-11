#!/usr/bin/env python3
"""
Backfill missing tournament_history.date values.

DEPRECATED for year-only: We need at least month/year in the date. This script
only has year, so it no longer sets placeholder dates (Dec 31, Jan 1).

Use backfill_tournament_dates_from_sources.py instead - it fetches real dates
(month+day) from WPBA, WPA, and web search.
"""

import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def backfill_dates(dry_run: bool = True) -> dict:
    """No-op: year-only placeholders are not used. Use backfill_tournament_dates_from_sources.py."""
    logger.info(
        "Skipping: dates require at least month/year. Use scripts/backfill_tournament_dates_from_sources.py"
    )
    return {
        "updated": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "view_status": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill tournament_history.date using year")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    result = backfill_dates(dry_run=args.dry_run)
    logger.info(
        "Done. Updated: %d, Skipped: %d, Dry run: %s",
        result["updated"],
        result["skipped"],
        result["dry_run"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
