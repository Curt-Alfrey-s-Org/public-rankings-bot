#!/usr/bin/env python3
"""
Import Fargo ratings from a CSV file.
Usage:
  python3 scripts/import_fargo_csv.py <path_to_csv> [--system WPA_Men]
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Fargo ratings from CSV")
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument("--system", default="WPA", help="Ranking system (e.g. WPA, WPBA, WPA_Men)")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.is_file():
        logger.error("File not found: %s", csv_path)
        return 1

    try:
        from database import get_database_manager
        from api.services.fargo_client import import_fargo_ratings_manual
    except ImportError as e:
        logger.error("Failed to import database modules: %s", e)
        return 1

    ratings = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            logger.error("CSV file has no headers")
            return 1
            
        # Try to find the appropriate columns
        headers = [h.strip().lower() for h in reader.fieldnames]
        
        name_col = None
        fargo_col = None
        robustness_col = None
        
        for h in reader.fieldnames:
            hl = h.strip().lower()
            if "name" in hl or "player" in hl:
                name_col = h
            if "fargo" in hl or "rating" in hl:
                fargo_col = h
            if "robust" in hl:
                robustness_col = h
                
        if not name_col or not fargo_col:
            logger.error(f"Could not identify name or rating columns. Found headers: {reader.fieldnames}")
            return 1
            
        logger.info(f"Using columns - Name: '{name_col}', Rating: '{fargo_col}', Robustness: '{robustness_col}'")
        
        for row in reader:
            name = row.get(name_col, "").strip()
            rating_str = row.get(fargo_col, "").strip()
            if not name or not rating_str:
                continue
                
            try:
                rating = float(rating_str.replace(",", ""))
                robustness = None
                if robustness_col and row.get(robustness_col):
                    try:
                        robustness = int(row[robustness_col].replace(",", "").strip())
                    except ValueError:
                        pass
                        
                ratings.append({
                    "player_name": name,
                    "fargo_rating": rating,
                    "fargo_robustness": robustness
                })
            except ValueError:
                pass

    if not ratings:
        logger.warning("No valid ratings found in CSV")
        return 1

    logger.info(f"Found {len(ratings)} valid ratings in CSV")

    db = get_database_manager()
    conn = db.get_connection()
    try:
        updated, err = import_fargo_ratings_manual(conn, args.system, ratings)
        if err:
            logger.error("Import failed: %s", err)
            return 1
            
        logger.info("Successfully imported/updated %d ratings for system %s", updated, args.system)
        
        try:
            from api.routes.rankings import _write_cache_version
            _write_cache_version()
            logger.info("Rankings API cache invalidated")
        except Exception as exc:
            logger.warning("Cache invalidation failed: %s", exc)
            
    finally:
        conn.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
