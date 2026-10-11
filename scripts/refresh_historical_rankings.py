#!/usr/bin/env python3
"""
Scrape and store WPA historical rankings from https://wpapool.com/previous-ranking/.
Run periodically (e.g. weekly) to backfill historical snapshots.
Exit: 0 on success, 1 if scrape failed.
"""
import sys
import os
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load .env when run from cron or shell (so DATABASE_URL is set)
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k and v and k not in os.environ:
                    os.environ.setdefault(k, v)

# When run from cron on host, DATABASE_URL may use host "postgres" (Docker); rewrite to 127.0.0.1
import re
_url = os.environ.get("DATABASE_URL", "")
if _url and "postgres" in _url:
    os.environ["DATABASE_URL"] = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", _url)

from database import get_database_manager, ensure_rankings_tables_postgres
from scrapers.wpa_scraper import WPAScraper

LOG_LEVEL = os.environ.get("REFRESH_VERBOSE", "").strip().lower() in ("1", "true", "yes")
logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    ensure_rankings_tables_postgres()
    db = get_database_manager()
    scraper = WPAScraper(timeout=30)

    results = scraper.scrape_historical_rankings()
    if not results:
        logger.warning("No historical rankings scraped")
        return 1

    total_saved = 0
    for ranking_type, snapshot_date, rankings in results:
        try:
            result = db.save_wpa_rankings(
                rankings,
                snapshot_date=snapshot_date,
                ranking_type=ranking_type,
            )
            count = result.get("saved_count", 0) if isinstance(result, dict) else result
            total_saved += count
            logger.info(
                "%s %s: saved %d rankings",
                ranking_type,
                snapshot_date,
                count,
            )
        except Exception as e:
            logger.exception("Save failed for %s %s: %s", ranking_type, snapshot_date, e)
            return 1

    logger.info("Historical rankings complete: %d total saved", total_saved)

    # Populate tournament history and player records from rankings snapshots (WPA/Heyball)
    try:
        stats = db.fill_tournament_history_from_rankings_snapshots(limit_snapshots_per_system=50)
        logger.info(
            "Tournament history from rankings: created=%s updated=%s results=%s",
            stats.get("tournaments_created", 0),
            stats.get("tournaments_updated", 0),
            stats.get("results_upserted", 0),
        )
    except Exception as e:
        logger.warning("Fill tournament history from rankings failed: %s", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
