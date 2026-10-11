#!/usr/bin/env python3
"""
Inside Spin Tier-2 historical ingest (Phase 4).

Uses the Inside Spin list API + RSC participantRows (no headless browser).
De-dups via source_event_crosswalk; gap-fills results on matched events only
when local tournament_results is empty; inserts insidesp_{slug} for IS-only pro events.

Operator-triggered only.

Usage:
  python scripts/scrape_insidesp_tier2.py                           # report only
  python scripts/scrape_insidesp_tier2.py --ingest                    # default pro scope
  python scripts/scrape_insidesp_tier2.py --ingest --begin-year 2022 --end-year 2022
  python scripts/scrape_insidesp_tier2.py --ingest --max-events 5     # smoke test
  python scripts/scrape_insidesp_tier2.py --ingest --gap-fill-only     # matched events only
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError as e:
    logger.debug("python-dotenv not available: %s", e)

from api.services.insidesp_tier2_importer import InsideSpinTier2Importer


def main() -> int:
    ap = argparse.ArgumentParser(description="Inside Spin Tier-2 historical ingest")
    ap.add_argument("--ingest", action="store_true", help="Write tournament_history/results")
    ap.add_argument("--begin-year", type=int, default=2020)
    ap.add_argument("--end-year", type=int, default=None)
    ap.add_argument("--max-events", type=int, default=None, help="Cap events processed (testing)")
    ap.add_argument("--all-events", action="store_true", help="Disable pro-like filter")
    ap.add_argument("--gap-fill-only", action="store_true",
                    help="Only gap-fill matched events; do not insert IS-only rows")
    ap.add_argument("--no-detail", action="store_true",
                    help="Use list-API top_finishers only (faster, podium-only)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    importer = InsideSpinTier2Importer()

    if args.ingest:
        result = importer.ingest(
            begin_year=args.begin_year,
            end_year=args.end_year,
            only_pro=not args.all_events,
            max_events=args.max_events,
            fetch_detail=not args.no_detail,
            gap_fill_only=args.gap_fill_only,
        )
    else:
        result = importer.report(
            begin_year=args.begin_year,
            end_year=args.end_year,
            only_pro=not args.all_events,
        )

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
