#!/usr/bin/env python3
"""
Load Digital Pool historical pro_world_rankings into the rankings table.

Phase 3c of docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md. Digital Pool keeps a
sparse historical time-series of per-system rank-position snapshots in
``pro_world_rankings`` (rank_date 2021-09-30 .. 2023-09-05, 8 systems:
Fargo World/Men's/Women's/US, Matchroom World 9-Ball, WPA World Men's/Women's,
US Pro Series).

Each (system, rank_date) snapshot is saved into the ``rankings`` table under
``DigitalPool_<suffix>`` with ``snapshot_date = rank_date``. These are rank-only
systems (``points=0.0``; Digital Pool player_id preserved in
``rankings.source_data``). The save is an atomic per-(system, date) replace
(``DELETE ... WHERE ranking_system AND snapshot_date`` then INSERT), so re-runs
are idempotent and never clobber other dates or the live rank lists.

Operator-triggered only (no scheduler), per no-automatic-scraping policy.

Prereq for --save: alembic migration 057 applied (DigitalPool_* allowed) and DB
env configured.

Usage:
  python scripts/load_digitalpool_ranking_history.py            # fetch + report only (no DB)
  python scripts/load_digitalpool_ranking_history.py --save     # + persist all snapshots
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError as e:
    logger.debug("python-dotenv not available; proceeding without .env autoload: %s", e)

from scrapers.externalpool_scraper import CpScraper


def _parse_date(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Load Digital Pool historical pro_world_rankings (DigitalPool_*)"
    )
    ap.add_argument("--save", action="store_true",
                    help="Persist every (system, rank_date) snapshot into rankings")
    ap.add_argument("--page-size", type=int, default=1000,
                    help="GraphQL keyset page size (default 1000)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    scraper = CpScraper()
    history = scraper.scrape_pro_world_rankings_history(page_size=args.page_size)

    total_snaps = sum(len(v["snapshots"]) for v in history.values())
    total_rows = sum(sum(len(rows) for rows in v["snapshots"].values()) for v in history.values())
    print(f"Fetched {len(history)} systems, {total_snaps} snapshots, {total_rows} rows:")
    for suffix, info in history.items():
        snaps = info["snapshots"]
        dates = sorted(snaps.keys())
        rows = sum(len(r) for r in snaps.values())
        span = f"{dates[0]}..{dates[-1]}" if dates else "-"
        print(f"  DigitalPool_{suffix:18} {info['code']:26} snapshots={len(snaps):>2} rows={rows:>5} {span}")

    if not args.save:
        print("Report-only run (no DB writes). Re-run with --save to persist.")
        return 0

    from database import get_database_manager
    db = get_database_manager()

    saved = 0
    systems_done = 0
    for suffix, info in history.items():
        system = f"DigitalPool_{suffix}"
        for rank_date, rows in sorted(info["snapshots"].items()):
            if not rows:
                continue
            try:
                n = db.save_rankings(rows, system, snapshot_date=_parse_date(rank_date))
                saved += n
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR saving {system} @ {rank_date}: {exc}")
        systems_done += 1
        print(f"  done {system}")

    print(f"Saved {saved} ranking rows across {systems_done} DigitalPool_* systems.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
