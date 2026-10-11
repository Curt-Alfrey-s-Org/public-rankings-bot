#!/usr/bin/env python3
"""
Import country and/or license_number into rankings from a CSV file.

Use when you obtain a list from WPA, web search, or another source.
Only updates rows where the field is currently NULL/empty (no overwrite).

CSV columns (any of): player_name or name, country, license_number or license
Example:
  player_name,country,license_number
  "Amit, Rubilen",PHI,ACBS - 102
  Kelly Fisher,USA,BCA - 509

Run from project root:
  python3 scripts/import_country_license_csv.py path/to/file.csv [--dry-run] [--systems WPBA_Women WPA_Women]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def _name_keys(name: str) -> list[str]:
    """Keys for lookup: normalized name and, if 'Last, First', also 'First Last'."""
    s = (name or "").strip()
    keys = [_normalize_name(s)]
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            keys.append(_normalize_name(f"{parts[1]} {parts[0]}"))
    return keys


def load_csv_lookup(csv_path: Path) -> dict[str, dict]:
    """Build normalized key -> { country, license_number } from CSV."""
    lookup: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("player_name") or row.get("name") or "").strip()
            if not name:
                continue
            country = (row.get("country") or "").strip() or None
            license_number = (row.get("license_number") or row.get("license") or "").strip() or None
            entry = {}
            if country:
                entry["country"] = country
            if license_number:
                entry["license_number"] = license_number
            if not entry:
                continue
            for key in _name_keys(name):
                if key not in lookup:
                    lookup[key] = {}
                lookup[key].update(entry)
    return lookup


def import_csv(csv_path: Path, dry_run: bool, systems: list[str]) -> int:
    """Update rankings (latest snapshot) from CSV lookup. Only fill where missing."""
    lookup = load_csv_lookup(csv_path)
    if not lookup:
        logger.warning("No rows with country or license in %s", csv_path)
        return 0

    db = get_database_manager()
    conn = db.get_connection()
    updated = 0
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'rankings' AND column_name = 'country_source'"
        )
        has_source_cols = cur.fetchone() is not None

        for ranking_system in systems:
            cur.execute(
                """
                SELECT player_name, country, license_number
                FROM rankings r
                WHERE r.ranking_system = %s
                AND r.snapshot_date = (
                    SELECT MAX(r2.snapshot_date) FROM rankings r2 WHERE r2.ranking_system = %s
                )
                AND (r.country IS NULL OR TRIM(COALESCE(r.country, '')) = ''
                     OR r.license_number IS NULL OR TRIM(COALESCE(r.license_number, '')) = '')
                """,
                (ranking_system, ranking_system),
            )
            rows = cur.fetchall()
            for row in rows:
                player_name = (row[0] or "").strip()
                current_country = row[1]
                current_license = row[2]
                match = None
                for key in _name_keys(player_name):
                    match = lookup.get(key)
                    if match:
                        break
                if not match:
                    continue
                need_country = not (current_country and current_country.strip())
                need_license = not (current_license and current_license.strip())
                country = (match.get("country") or "").strip() if need_country else (current_country or "")
                license_number = (match.get("license_number") or "").strip() if need_license else (current_license or "")
                if (need_country and not country) and (need_license and not license_number):
                    continue
                logger.info("[%s] %s -> country=%s license=%s", ranking_system, player_name, country or "-", license_number or "-")
                updated += 1
                if not dry_run:
                    set_parts = [
                        "country = COALESCE(NULLIF(%s, ''), country)",
                        "license_number = COALESCE(NULLIF(%s, ''), license_number)",
                    ]
                    params = [country or "", license_number or ""]
                    if has_source_cols:
                        set_parts.append("country_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'csv_import' ELSE country_source END")
                        set_parts.append("license_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'csv_import' ELSE license_source END")
                        params.extend([country or "", license_number or ""])
                    params.extend([ranking_system, ranking_system, player_name])
                    cur.execute(
                        """
                        UPDATE rankings
                        SET """ + ", ".join(set_parts) + """
                        WHERE ranking_system = %s
                        AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = %s)
                        AND player_name = %s
                        """,
                        params,
                    )
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Import country/license from CSV into rankings")
    parser.add_argument("csv_path", type=Path, help="Path to CSV (columns: player_name/name, country, license_number/license)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument(
        "--systems",
        nargs="+",
        default=["WPA_Women", "WPBA_Women", "WPA_Men", "WPBA"],
        help="Ranking systems to update (default: WPA_Women WPBA_Women WPA_Men WPBA)",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        logger.error("File not found: %s", args.csv_path)
        return 1

    n = import_csv(args.csv_path, args.dry_run, args.systems)
    logger.info("Updated %d rows (%s)", n, "dry run" if args.dry_run else "committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
