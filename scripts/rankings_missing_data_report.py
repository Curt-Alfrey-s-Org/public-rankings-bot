#!/usr/bin/env python3
"""
Report: who is missing what (Fargo, country, license) in rankings.

Uses latest snapshot per (player_name, ranking_system). Output is CSV and/or JSON
for working the list and measuring progress. No scraping or new data.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_report(system: str | None, limit: int | None, include_all: bool) -> tuple[list[dict], dict]:
    """Query latest snapshot per system; return rows with any missing field and summary."""
    db = get_database_manager()
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        # Latest snapshot per (player_name, ranking_system)
        sys_filter = "AND r.ranking_system = %(org)s" if system else ""
        params: dict = {"limit": limit or 10000}
        if system:
            params["org"] = system
        cursor.execute(
            f"""
            SELECT
                r.player_name,
                r.ranking_system,
                r.rank,
                r.points,
                r.country,
                r.license_number,
                r.fargo_rating,
                r.snapshot_date,
                r.country_source,
                r.license_source,
                r.fargo_source,
                r.fargo_name_format,
                CASE WHEN r.fargo_rating IS NULL THEN 1 ELSE 0 END AS missing_fargo,
                CASE WHEN r.country IS NULL OR TRIM(COALESCE(r.country, '')) = '' THEN 1 ELSE 0 END AS missing_country,
                CASE WHEN r.license_number IS NULL OR TRIM(COALESCE(r.license_number, '')) = '' THEN 1 ELSE 0 END AS missing_license
            FROM rankings r
            WHERE r.snapshot_date = (
                SELECT MAX(r2.snapshot_date)
                FROM rankings r2
                WHERE r2.player_name = r.player_name AND r2.ranking_system = r.ranking_system
            )
            {sys_filter}
            ORDER BY r.ranking_system, r.rank
            LIMIT %(limit)s
            """,
            params,
        )
        columns = [d[0] for d in cursor.description]
        all_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if include_all:
            rows = all_rows
        else:
            rows = [
                r
                for r in all_rows
                if (r.get("missing_fargo") or r.get("missing_country") or r.get("missing_license"))
            ]

        summary = {
            "total_rows": len(all_rows),
            "rows_with_any_missing": len(rows),
            "missing_fargo_count": sum(1 for r in all_rows if r.get("missing_fargo")),
            "missing_country_count": sum(1 for r in all_rows if r.get("missing_country")),
            "missing_license_count": sum(1 for r in all_rows if r.get("missing_license")),
            "system_filter": system,
        }
        return rows, summary
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rankings missing data report (Fargo, country, license)")
    parser.add_argument("--system", default=None, help="Filter by ranking_system (e.g. WPBA_Women, WPA_Men)")
    parser.add_argument("--limit", type=int, default=5000, help="Max rows to consider (default 5000)")
    parser.add_argument("--all", action="store_true", help="Include rows with no missing data (default: only missing)")
    parser.add_argument("--output", "-o", default=None, help="Write CSV to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    rows, summary = run_report(args.system, args.limit, args.all)

    logger.info(
        "Total rows: %d | With any missing: %d | Missing Fargo: %d | Missing country: %d | Missing license: %d",
        summary["total_rows"],
        summary["rows_with_any_missing"],
        summary["missing_fargo_count"],
        summary["missing_country_count"],
        summary["missing_license_count"],
    )

    if args.output:
        fieldnames = [
            "player_name", "ranking_system", "rank", "missing_fargo", "missing_country", "missing_license",
            "country", "license_number", "fargo_rating", "country_source", "license_source", "fargo_source", "fargo_name_format",
            "snapshot_date",
        ]
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        logger.info("Wrote %s", args.output)

    if args.json or not args.output:
        def _json_serial(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        out = {"summary": summary, "rows": rows}
        print(json.dumps(out, indent=2, default=_json_serial))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
