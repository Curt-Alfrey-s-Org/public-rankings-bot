#!/usr/bin/env python3
"""Scrape past tournament results from WPBA/WPA. Run after init_tournament_history.py."""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from database import engine
from scrapers.tournament_history_scraper import TournamentHistoryScraper
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fargo", action="store_true", help="Attach current Fargo to results")
    parser.add_argument("--limit", type=int, default=None, help="Max events to process")
    parser.add_argument("--wpba-only", action="store_true")
    parser.add_argument("--wpa-only", action="store_true")
    args = parser.parse_args()
    wpba = not args.wpa_only
    wpa = not args.wpba_only
    scraper = TournamentHistoryScraper(engine=engine)
    scraper.init_tournament_tables()
    result = scraper.scrape_past_tournaments(
        wpba=wpba, wpa=wpa, attach_fargo=args.fargo, limit=args.limit
    )
    logger.info("Done: %s", result)
    return 0 if result.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
