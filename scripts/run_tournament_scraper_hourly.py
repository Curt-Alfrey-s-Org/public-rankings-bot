#!/usr/bin/env python3
"""
Tournament Scraper Scheduler
Manages hourly execution of the tournament scraper with proper logging and error handling.
Can be run via cron or as a standalone service.
"""

import os
import re
import sys
import logging
from pathlib import Path
from datetime import datetime
import json

# Setup paths
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env when run from cron (cron has minimal env)
env_path = project_root / ".env"
if env_path.is_file():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)

# When run on host, Docker hostname "postgres" does not resolve
url = os.environ.get("DATABASE_URL", "")
if url and "postgres" in url:
    url = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", url)
    os.environ["DATABASE_URL"] = url

# Setup logging
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "tournament_scraper.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_scraper():
    """Execute the tournament scraper and log results."""
    logger.info("=" * 80)
    logger.info("🕐 HOURLY TOURNAMENT SCRAPER RUN STARTING")
    logger.info("=" * 80)
    
    try:
        from database import engine
        from scrapers.tournament_scraper_improved import EnhancedTournamentScraper
        
        scraper = EnhancedTournamentScraper(engine=engine, rate_limit_delay=2.0)
        
        result = scraper.scrape_tournaments(
            wpba=True,
            wpa=True,
            include_future=True,
            attach_fargo=True,
            force_rescrape=False,  # Incremental by default
            limit=None  # No limit for production
        )
        
        # Log detailed results
        logger.info("📊 Run completed successfully")
        logger.info(f"   Duration: {result['duration_seconds']:.2f}s")
        logger.info(f"   Events discovered: {result['events_discovered']}")
        logger.info(f"   Events processed: {result['events_processed']}")
        logger.info(f"   New tournaments: {result['events_new']}")
        logger.info(f"   Updated tournaments: {result['events_updated']}")
        logger.info(f"   Future tournaments: {result['events_future']}")
        logger.info(f"   Errors: {result['error_count']}")
        logger.info(f"   Warnings: {result['warning_count']}")
        
        # Save summary to JSON for monitoring
        summary_file = log_dir / "tournament_scraper_last_run.json"
        with open(summary_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        if result['error_count'] > 0:
            logger.warning(f"⚠️  Run completed with {result['error_count']} errors")
            logger.warning(f"   Errors: {result['errors']}")
            return 1
        
        logger.info("✅ Scraper run completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR during scraper run: {e}", exc_info=True)
        
        # Save error summary
        error_summary = {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "success": False
        }
        summary_file = log_dir / "tournament_scraper_last_run.json"
        with open(summary_file, 'w') as f:
            json.dump(error_summary, f, indent=2)
        
        return 1
    
    finally:
        logger.info("=" * 80)
        logger.info("🏁 HOURLY SCRAPER RUN FINISHED")
        logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = run_scraper()
    sys.exit(exit_code)
