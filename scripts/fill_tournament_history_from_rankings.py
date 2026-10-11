#!/usr/bin/env python3
"""
Fill tournament history from already-scraped rankings data (no new scraping).
Reads the rankings table and creates/updates tournament_history and
tournament_results so each (ranking_system, snapshot_date) becomes one
"Rankings (date)" event with placements and points.

Usage:
  python scripts/fill_tournament_history_from_rankings.py
  python scripts/fill_tournament_history_from_rankings.py --limit 12   # last 12 snapshots per system
  python scripts/fill_tournament_history_from_rankings.py --systems WPBA_Women WPA_Women
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_database_manager


def main():
    ap = argparse.ArgumentParser(description="Fill tournament history from rankings snapshots")
    ap.add_argument(
        "--systems",
        nargs="*",
        help="Only these ranking systems (e.g. WPBA_Women WPA_Women). Default: all.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max snapshots per system (e.g. 12 = last 12 dates). Default: all.",
    )
    args = ap.parse_args()

    db = get_database_manager()
    stats = db.fill_tournament_history_from_rankings_snapshots(
        ranking_systems=args.systems or None,
        limit_snapshots_per_system=args.limit,
    )
    print(
        f"Done: {stats['tournaments_updated']} tournaments updated, "
        f"{stats['results_upserted']} results upserted, {stats['errors']} errors."
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
