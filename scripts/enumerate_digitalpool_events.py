#!/usr/bin/env python3
"""
Enumerate the Digital Pool event catalog and report the local-vs-DP-only gap.

Phase 3 (discovery) of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Read-only on
Digital Pool; de-dups each DP event against tournament_history via the Phase-1
crosswalk (records crosswalk rows for matches only). Does NOT create any
tournament_history rows — it produces the report that drives the ingestion-scope
decision, and archives the DP-only events to scraped_data/externalpool_enum/.

Operator-triggered only (no scheduler).

Usage:
  python scripts/enumerate_digitalpool_events.py                     # public, since 2023
  python scripts/enumerate_digitalpool_events.py --date-floor 2024-01-01
  python scripts/enumerate_digitalpool_events.py --all               # include non-public
  python scripts/enumerate_digitalpool_events.py --max 200           # cap for a quick probe
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
    logger.debug("python-dotenv not available; proceeding without .env autoload: %s", e)

from scrapers.externalpool_event_enumerator import ExternalPoolEventEnumerator


def main() -> int:
    ap = argparse.ArgumentParser(description="Enumerate Digital Pool events; report DP-only gap")
    ap.add_argument("--date-floor", default=None, help="ISO date, only events on/after (default 2023-01-01)")
    ap.add_argument("--all", action="store_true", help="Include non-public events")
    ap.add_argument("--max", type=int, default=None, help="Max events to scan (quick probe)")
    ap.add_argument("--no-record", action="store_true", help="Do not write crosswalk rows for matches")
    ap.add_argument("--ingest", action="store_true",
                    help="Phase 3b: INSERT pro-like-with-placements DP-only events into "
                         "tournament_history (+ enrich). Idempotent.")
    ap.add_argument("--ingest-all-placements", action="store_true",
                    help="With --ingest: widen scope to all DP-only events with placements "
                         "(not just pro-like).")
    ap.add_argument("--max-ingest", type=int, default=None, help="Cap number of new inserts")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    enumerator = ExternalPoolEventEnumerator()
    if args.ingest:
        result = enumerator.ingest(
            date_floor=args.date_floor,
            public_only=not args.all,
            only_pro=not args.ingest_all_placements,
            require_placements=True,
            max_ingest=args.max_ingest,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0

    report = enumerator.enumerate(
        date_floor=args.date_floor,
        public_only=not args.all,
        max_events=args.max,
        record_crosswalk=not args.no_record,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
