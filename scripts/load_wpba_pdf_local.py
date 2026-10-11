#!/usr/bin/env python3
"""
CLI equivalent of POST /rankings/refresh-wpba (no HTTP auth).

Fetches the current WPBA PDF from wpba.com, saves rankings, splits column systems,
fills per-event tournament history, and refreshes materialized views.

Usage (from repo root):
  python3 scripts/load_wpba_pdf_local.py

Requires DATABASE_URL (or .env in project root).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_wpba_pdf_local")


def main() -> int:
    from scrapers.wpba_scraper import WPBAScraper
    from database import get_database_manager

    db = get_database_manager()
    scraper = WPBAScraper()
    wpba_data = scraper.scrape_rankings()
    if not wpba_data:
        logger.error("WPBA scrape returned no data (check network and wpba.com).")
        return 1

    source_url = getattr(scraper, "pdf_url", None) or ""
    count = db.save_wpba_rankings(wpba_data, ranking_type="WPBA_Women")
    logger.info("Saved %s WPBA_Women rows from %s", count, source_url[:120])

    try:
        split_result = db.split_wpba_women_to_column_buttons()
        logger.info("WPBA Women tournament split: %s", split_result)
    except Exception as e:
        logger.warning("WPBA Women tournament split failed: %s", e)

    try:
        wpba_evt_th = db.fill_tournament_history_from_wpba_women_events()
        logger.info("WPBA per-event tournament history: %s", wpba_evt_th)
    except Exception as e:
        logger.warning("WPBA per-event tournament history failed: %s", e)

    try:
        db.refresh_materialized_views()
        logger.info("Materialized views refreshed")
    except Exception as e:
        logger.warning("Materialized view refresh failed: %s", e)

    try:
        from api.services.cache_store import invalidate_cache

        invalidate_cache("tournament-history")
    except Exception as e:
        logger.warning("Cache invalidate failed (OK if not running API process): %s", e)

    logger.info("Done. Parsed %s rows; PDF source: %s", len(wpba_data), source_url or "(unknown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
