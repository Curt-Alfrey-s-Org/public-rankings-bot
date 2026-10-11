#!/usr/bin/env python3
"""
Fix WPA_Women_9Ball rankings by importing Poison Saigon tournament results.
Updates the rankings table with the correct tournament results.
"""

import logging
import os
import sys
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load .env so DATABASE_URL is available when run standalone (e.g. from cron)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # dotenv optional; rely on env vars if not installed

# When run on host, Docker hostname "postgres" does not resolve; use 127.0.0.1
import re
url = os.environ.get("DATABASE_URL", "")
if url and "postgres" in url:
    url = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", url)
    os.environ["DATABASE_URL"] = url

from database import get_database_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Fix WPA_Women_9Ball rankings with Poison Saigon tournament results."""
    logger.info("Starting fix for Poison Saigon rankings...")

    try:
        db = get_database_manager()

        # Get Poison Saigon tournament results for WPA Women
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tr.player_name, tr.placement, tr.points, tr.fargo_rating_at_scrape
            FROM tournament_results tr
            JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE th.name LIKE '%Poison Saigon%' AND th.tournament_id LIKE '%WPA_Women%'
            ORDER BY tr.placement ASC
        """)

        results = cursor.fetchall()
        conn.close()

        if not results:
            logger.error("No Poison Saigon tournament results found")
            return

        logger.info(f"Found {len(results)} players in Poison Saigon tournament")

        # Convert to rankings format
        rankings = []
        for row in results:
            player_name, placement, points, fargo_rating = row
            rankings.append({
                'rank': placement,
                'name': player_name,
                'points': float(points) if points else 0.0,
                'country': '',  # Could be extracted from player name if needed
                'fargo_rating': fargo_rating
            })

        # Save as WPA_Women_9Ball rankings
        count = db.save_wpa_rankings(rankings, ranking_type='WPA_Women_9Ball')
        logger.info(f"Updated WPA_Women_9Ball rankings with {count} players")

    except Exception as e:
        logger.error(f"Failed to fix Poison Saigon rankings: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()