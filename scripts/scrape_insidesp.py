#!/usr/bin/env python3
"""
Manual Inside Spin (insidesp.in) Tier-1 scrape.

Phase 2 of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Scrapes the server-rendered
listing pages (events + per-discipline ratings) and archives raw JSON under
data/insidesp_archive/. Optionally persists ratings into the `rankings` table as
InsideSpin_<discipline> and de-dups the events against tournament_history via the
source_event_crosswalk.

Operator-triggered only (no scheduler), per no-automatic-scraping policy.

Prereq for --save: alembic migrations 055 (crosswalk) and 056 (InsideSpin_*
ranking systems) applied, and DB env configured.

Usage:
  python scripts/scrape_insidesp.py                 # scrape + archive only (no DB)
  python scripts/scrape_insidesp.py --save          # + save ratings + crosswalk events
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

from scrapers.insidesp_scraper import InsideSpinScraper


def main() -> int:
    ap = argparse.ArgumentParser(description="Scrape Inside Spin (Tier 1) ratings + events")
    ap.add_argument("--save", action="store_true",
                    help="Persist ratings to rankings (InsideSpin_*) and crosswalk events")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    scraper = InsideSpinScraper()
    ratings = scraper.scrape_all_ratings()
    events = scraper.scrape_events()

    total_ratings = sum(len(v) for v in ratings.values())
    print(f"Scraped ratings: {total_ratings} across {len(ratings)} disciplines "
          f"({', '.join(f'{k}={len(v)}' for k, v in ratings.items())})")
    print(f"Scraped events: {len(events)}")

    if not args.save:
        print("Archive-only run (no DB writes). Re-run with --save to persist.")
        return 0

    from database import get_database_manager
    from api.services.event_crosswalk import EventCrosswalkResolver, SOURCE_INSIDESP

    db = get_database_manager()

    saved = 0
    for suffix, rows in ratings.items():
        if not rows:
            continue
        system = f"InsideSpin_{suffix}"
        try:
            n = db.save_rankings(rows, system)
            saved += n
            print(f"  saved {n} -> {system}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR saving {system}: {exc}")

    resolver = EventCrosswalkResolver(db=db)
    resolver.ensure_table()
    matched = unmatched = no_date = 0
    for ev in events:
        if not ev.get("start_date"):
            no_date += 1
            continue
        res = resolver.resolve(
            source=SOURCE_INSIDESP,
            source_event_id=ev.get("slug") or ev.get("url") or ev.get("name"),
            name=ev.get("name") or "",
            event_date=ev.get("start_date"),
            location=ev.get("location"),
            source_url=ev.get("url"),
        )
        if res.matched:
            matched += 1
        else:
            unmatched += 1

    print(f"Ratings saved: {saved}")
    print(f"Events crosswalk: matched={matched} unmatched(IS-only)={unmatched} no_date={no_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
