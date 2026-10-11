#!/usr/bin/env python3
"""Generate a report of players missing Fargo ratings (latest snapshot only)."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_database_manager
from api.services import fargo_client


logger = logging.getLogger(__name__)


def _write_csv(path: str, rows: list[dict]) -> None:
    """Write rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["player_name", "ranking_system", "rank"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    """CLI entrypoint for missing Fargo report generation."""
    parser = argparse.ArgumentParser(description="Report players missing Fargo ratings.")
    parser.add_argument("--system", default=None, help="Filter by system (e.g., WPBA, WPA, WPA_Men)")
    parser.add_argument("--limit", type=int, default=500, help="Max rows to include")
    parser.add_argument("--output", default=None, help="Write CSV to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db_manager = get_database_manager()
    conn = db_manager.get_connection()
    try:
        total_count = fargo_client.count_missing_fargo(conn, args.system)
        rows = fargo_client.get_missing_fargo_report(conn, args.system, args.limit)
    finally:
        conn.close()

    logger.info("Missing Fargo ratings: %d", total_count)

    if args.output:
        _write_csv(args.output, rows)
        logger.info("Wrote report: %s", args.output)

    if args.json or not args.output:
        print(json.dumps({"total_count": total_count, "rows": rows[: args.limit]}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
