"""
Background scheduler. Scrapers are not auto-started; rankings/tournament/Fargo
refresh run only when triggered manually (e.g. POST /api/rankings/refresh).
Scheduler is started with no jobs so shutdown and get_scheduler() still work.
"""

# Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/HOW_DATA_IS_UPDATED.md;
#   docs/ROADMAP.md (DOC-001 scheduler vs docs)

import logging
import os
logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    """Return the global scheduler instance, or None if disabled."""
    return _scheduler


def start_background_scheduler() -> None:
    """Start the background scheduler with no auto-scraper jobs. Call from API lifespan."""
    global _scheduler
    if os.environ.get("SKIP_BACKGROUND_SCHEDULER", "").lower() in ("1", "true", "yes"):
        logger.info("[SCHEDULER] Disabled via SKIP_BACKGROUND_SCHEDULER")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler()
        _scheduler.start()
        logger.info("[SCHEDULER] Started (no auto-scraper jobs; use manual refresh endpoints)")
    except ImportError as e:
        logger.warning("[SCHEDULER] APScheduler not installed: %s. Run: pip install apscheduler", e)
    except Exception as e:
        logger.error("[SCHEDULER] Failed to start: %s", e, exc_info=True)


def stop_background_scheduler() -> None:
    """Stop the scheduler. Call on API shutdown."""
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("[SCHEDULER] Stopped")
        except Exception as e:
            logger.warning("[SCHEDULER] Error stopping: %s", e)
        _scheduler = None
