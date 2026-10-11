"""
Fargo global leaderboard — materialize `fargo_rankings` from `players.fargo_score`.
No external HTTP in this path (published Fargo sync uses api/services/fairmatch_scraper.py / cron).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from database import get_database_manager

logger = logging.getLogger(__name__)


def scrape_fargo_rankings_into_table(snapshot_date: Optional[date] = None) -> int:
    """Refresh dedicated fargo_rankings table from current player Fargo scores."""
    db = get_database_manager()
    n = db.refresh_fargo_rankings_table(snapshot_date)
    if n:
        logger.info("fargo_rankings snapshot rows: %s", n)
    return n
