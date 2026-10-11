#!/usr/bin/env python3
"""
Backfill rankings from existing on-server data only (no new scrapers, no new scraping).

Sources used:
- data/wpa_archive/wpa_women_rankings_*.json (player_name, country, license_number)
- data/wpa_archive/wpa_women_with_licenses_legacy.json (name, country, license)
- Cross-system enrichment (enrich_cross_system_data.py)
- WPBA from WPA by name (backfill_wpba_country_license.py)

Updates only rows where the field is currently NULL/empty. Does not overwrite existing data.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
WPA_ARCHIVE = DATA_ROOT / "wpa_archive"


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def _name_keys(name: str) -> list[str]:
    """Return keys to use for lookup: normalized name and, if 'Last, First', also 'First Last'."""
    s = (name or "").strip()
    keys = [_normalize_name(s)]
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            keys.append(_normalize_name(f"{parts[1]} {parts[0]}"))
    return keys


def _build_wpa_lookup_from_archives() -> dict[str, dict]:
    """Build normalized_name -> { country, license_number } from WPA archive JSON files."""
    lookup: dict[str, dict] = {}

    # wpa_women_rankings_*.json: data[].player_name, country, license_number
    for p in sorted(WPA_ARCHIVE.glob("wpa_women_rankings_*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            data = raw.get("data") if isinstance(raw, dict) else raw
            if not isinstance(data, list):
                continue
            for row in data:
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
                for key in _name_keys(name):
                    if key not in lookup:
                        lookup[key] = {}
                    lookup[key].update(entry)
            logger.info("Loaded %d entries from %s", len(data), p.name)
        except Exception as e:
            logger.warning("Skip %s: %s", p, e)

    # wpa_women_with_licenses_legacy.json: name, country, license
    legacy = WPA_ARCHIVE / "wpa_women_with_licenses_legacy.json"
    if legacy.exists():
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for row in data:
                    name = (row.get("name") or row.get("player_name") or "").strip()
                    if not name:
                        continue
                    country = (row.get("country") or "").strip() or None
                    license_number = (row.get("license") or row.get("license_number") or "").strip() or None
                    entry = {}
                    if country:
                        entry["country"] = country
                    if license_number:
                        entry["license_number"] = license_number
                    for key in _name_keys(name):
                        if key not in lookup:
                            lookup[key] = {}
                        lookup[key].update(entry)
                logger.info("Loaded %d entries from %s", len(data), legacy.name)
        except Exception as e:
            logger.warning("Skip %s: %s", legacy, e)

    return lookup


def backfill_country_license_from_archives(dry_run: bool, systems: list[str]) -> int:
    """Update rankings (latest snapshot per system) from WPA archive lookup. Only fill where missing."""
    lookup = _build_wpa_lookup_from_archives()
    if not lookup:
        logger.warning("No WPA archive data found under %s", WPA_ARCHIVE)
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
                player_name, current_country, current_license = (row[0] or "").strip(), row[1], row[2]
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
                        set_parts.append("country_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'wpa_archive' ELSE country_source END")
                        set_parts.append("license_source = CASE WHEN NULLIF(%s, '') IS NOT NULL THEN 'wpa_archive' ELSE license_source END")
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


def run_enrich_cross_system(execute: bool) -> bool:
    """Run enrich_cross_system_data.py. Returns True if success."""
    root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(root / "enrich_cross_system_data.py")]
    if execute:
        cmd.append("--execute")
    try:
        subprocess.run(cmd, cwd=str(root), check=True, timeout=300)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("enrich_cross_system_data failed: %s", e)
        return False
    except Exception as e:
        logger.warning("enrich_cross_system_data error: %s", e)
        return False


def run_backfill_wpba(execute: bool) -> bool:
    """Run backfill_wpba_country_license.py. Returns True if success."""
    root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(root / "scripts" / "backfill_wpba_country_license.py")]
    if not execute:
        cmd.append("--dry-run")
    try:
        subprocess.run(cmd, cwd=str(root), check=True, timeout=120)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("backfill_wpba_country_license failed: %s", e)
        return False
    except Exception as e:
        logger.warning("backfill_wpba_country_license error: %s", e)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill rankings from on-server archives only")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip enrich_cross_system_data.py")
    parser.add_argument("--skip-wpba", action="store_true", help="Skip backfill_wpba_country_license.py")
    parser.add_argument("--skip-archives", action="store_true", help="Skip WPA archive JSON backfill")
    parser.add_argument("--systems", nargs="+", default=["WPA_Women", "WPBA_Women"],
                        help="Systems to backfill from archives (default: WPA_Women WPBA_Women)")
    args = parser.parse_args()

    execute = not args.dry_run
    if args.dry_run:
        logger.info("DRY RUN - no changes will be written")

    if not args.skip_enrich:
        logger.info("Running cross-system enrichment...")
        run_enrich_cross_system(execute)
    if not args.skip_wpba:
        logger.info("Running WPBA from WPA backfill...")
        run_backfill_wpba(execute)
    if not args.skip_archives:
        logger.info("Backfilling from WPA archive JSON files...")
        n = backfill_country_license_from_archives(args.dry_run, args.systems)
        logger.info("Archive backfill: %d rows updated", n)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
