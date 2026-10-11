#!/usr/bin/env python3
"""
Populate ranking buttons from imported WPA Women and WPA Men data.

Copies the latest WPA_Women snapshot to CP 9-Ball, CP 10-Ball, CP 8-Ball,
CP Mixed 9-Ball, WPA Artistic, and WPA Heyball Women. Copies the latest
WPA_Men snapshot to WPA Heyball Men. Run after importing WPA Women and
WPA Men so every Rankings page button shows data.

Usage:
  python scripts/populate_rankings_from_import.py
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError as e:
    logger.debug("python-dotenv not available; proceeding without .env autoload: %s", e)

from database import get_database_manager


def main():
    db = get_database_manager()

    from_women = [
        "Competitors_Pool_9Ball",
        "Competitors_Pool_10Ball",
        "Competitors_Pool_8Ball",
        "Competitors_Pool_Mixed_9Ball",
        "WPA_Artistic",
        "WPA_Heyball_Women",
    ]
    from_men = ["WPA_Heyball_Men"]

    print("Copying from WPA_Women to:", ", ".join(from_women))
    r1 = db.copy_rankings_from_source_to_targets("WPA_Women", from_women)
    total1 = sum(r1.values())
    print(f"  -> {total1} rows copied to {len(from_women)} system(s)")

    print("Copying from WPA_Men to:", ", ".join(from_men))
    r2 = db.copy_rankings_from_source_to_targets("WPA_Men", from_men)
    total2 = sum(r2.values())
    print(f"  -> {total2} rows copied to {len(from_men)} system(s)")

    print(f"Done. Total rows populated: {total1 + total2}")
    return 0 if (total1 > 0 or total2 > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
