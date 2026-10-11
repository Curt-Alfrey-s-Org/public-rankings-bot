#!/usr/bin/env python3
"""
Delete news/events and rankings-snapshot rows from tournament_history
So Tournament History list and Leaderboard show only real tournaments.
"""

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database import get_database_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Delete news/events from tournament history."""
    logger.info("Starting delete news from tournament history...")

    try:
        db = get_database_manager()
        result = db.delete_news_from_tournament_history()
        logger.info(f"Deleted {result['deleted']} news/event rows from tournament_history")

    except Exception as e:
        logger.error(f"Failed to delete news from tournament history: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()