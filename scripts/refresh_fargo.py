#!/usr/bin/env python3
"""
Fargo ratings are not downloaded by this script.

sync_fargo_ratings_rate_limited (dashboard.fargorate.com TopListsForWeb) was
removed on 2026-03-09. Ratings are updated only from an official FargoRate
CSV or Excel export:

  python3 scripts/import_fargo_csv.py PATH_TO_CSV

See docs/FARGO_LOOKUP.md and docs/HOW_DATA_IS_UPDATED.md.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "Fargo ratings are not downloaded by this script. "
        "Import an official FargoRate CSV with: "
        "python3 scripts/import_fargo_csv.py PATH_TO_CSV. "
        "See docs/FARGO_LOOKUP.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
