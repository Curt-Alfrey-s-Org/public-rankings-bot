#!/usr/bin/env python3
"""
Backfill the source_event_crosswalk table for existing Digital Pool events.

Phase 1 of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md: seed crosswalk rows for
every tournament_history event already linked to digitalpool.com (via
source_url / bracket_url), so future multi-source ingestion (insidesp.in, full
Digital Pool harvest) resolves to the existing tournament instead of creating a
duplicate.

Operator-triggered only (no scheduler), per no-automatic-scraping policy. This
reads/writes the local DB only; it does NOT hit any external site.

Prereq: alembic migration 055 applied (creates source_event_crosswalk). The
resolver also creates the table defensively if missing.

Usage:
  python scripts/backfill_digitalpool_crosswalk.py
  python scripts/backfill_digitalpool_crosswalk.py --limit 50
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError as e:
    logger.debug("python-dotenv not available; proceeding without .env autoload: %s", e)

from api.services.event_crosswalk import backfill_digitalpool_crosswalk


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill Digital Pool event crosswalk rows")
    ap.add_argument("--limit", type=int, default=None, help="Max tournament_history rows to scan")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    stats = backfill_digitalpool_crosswalk(limit=args.limit)
    print(
        f"Done: scanned={stats['scanned']} recorded={stats['recorded']} "
        f"skipped_no_slug={stats['skipped_no_slug']} skipped_existing={stats['skipped_existing']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
