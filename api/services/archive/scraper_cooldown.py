"""
Scraper cooldown: ensure scrapers do not run more than once per hour.
Used by background scheduler and API endpoints that trigger scrapers.
"""

import time
import threading
import logging

logger = logging.getLogger(__name__)

_last_run: dict[str, float] = {}
_lock = threading.Lock()
_MIN_INTERVAL_SECONDS = 3600  # 1 hour


def try_acquire_scraper_run(scraper_id: str, min_interval_seconds: int = _MIN_INTERVAL_SECONDS) -> bool:
    """
    Check if scraper can run and record the run if so.
    Call at the start of a scraper. Returns True if run is allowed, False if cooldown active.

    Args:
        scraper_id: Identifier (e.g. "rankings_wpba", "tournament_refresh", "fargo_sync")
        min_interval_seconds: Minimum seconds between runs (default 3600 = 1 hour)

    Returns:
        True if scraper may run (and run is recorded), False if must skip
    """
    with _lock:
        last = _last_run.get(scraper_id, 0)
        now = time.time()
        if now - last < min_interval_seconds:
            wait = min_interval_seconds - (now - last)
            logger.info(
                "[SCRAPER_COOLDOWN] Skipping %s: last run %.0f min ago, wait %.0f s",
                scraper_id,
                (now - last) / 60,
                wait,
            )
            return False
        _last_run[scraper_id] = now
        return True
