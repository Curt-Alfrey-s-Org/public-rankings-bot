#!/usr/bin/env python3
"""
Fill tournament history from CP / External Pool scrape archives.

Reads JSON files in data/externalpool_archive, data/cp_archive, or
custom paths (e.g. scrape archives on the server). Each file may contain a
"tournaments" array with tournament_name, players, and/or standings; these
are upserted into tournament_history and tournament_results.

Usage:
  python scripts/fill_tournament_history_from_cp_archives.py
  python scripts/fill_tournament_history_from_cp_archives.py --dir /path/to/archives
  python scripts/fill_tournament_history_from_cp_archives.py --dir data/externalpool_archive --dir /srv/scrape_archives
"""

import argparse
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
    ap = argparse.ArgumentParser(
        description="Fill tournament history from CP / External Pool JSON archives"
    )
    ap.add_argument(
        "--dir",
        dest="dirs",
        action="append",
        default=None,
        help="Archive directory (repeat for multiple). Default: data/externalpool_archive, data/cp_archive",
    )
    args = ap.parse_args()

    if args.dirs:
        archive_dirs = [Path(d) for d in args.dirs]
    else:
        project_root = Path(__file__).resolve().parent.parent
        archive_dirs = [
            project_root / "data" / "externalpool_archive",
            project_root / "data" / "cp_archive",
            project_root / "data" / "tournament_history_archive",
            project_root / "data" / "tournament_current_archive",
        ]
        # Include server scrape archives if present
        for extra in ("/srv/scrape_archives", "/srv/rankings-bot/scrape_archives"):
            p = Path(extra)
            if p.is_dir():
                archive_dirs.append(p)

    db = get_database_manager()
    stats = db.fill_tournament_history_from_cp_archives(archive_dirs)
    print(
        f"Done: {stats['files_read']} files read, {stats['tournaments_updated']} tournaments updated, "
        f"{stats['results_upserted']} results upserted, {stats['errors']} errors."
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
