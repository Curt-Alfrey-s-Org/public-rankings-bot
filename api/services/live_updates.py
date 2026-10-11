"""
Live Updates System - Server-Sent Events (SSE) for scraper completion notifications.
Broadcasts scraper events to all connected clients so frontends can refresh data.
"""

import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Global set of client event queues (asyncio.Queue) for broadcasting
_client_queues: Set[asyncio.Queue] = set()
_queue_lock = asyncio.Lock()

# Main event loop (set at startup) for scheduling broadcasts from scheduler threads
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store reference to main event loop so scheduler jobs can schedule broadcasts."""
    global _main_loop
    _main_loop = loop


@dataclass
class ScraperEvent:
    """Event fired when a scraper completes."""
    scraper_type: str  # 'fargo', 'rankings_wpba', 'rankings_wpa_women', 'rankings_wpa_men', 'tournament', 'upcoming'
    status: str  # 'success' or 'failed'
    timestamp: str  # ISO format
    message: str = ""
    rows_updated: int = 0
    duration_s: float = 0.0
    error: str = ""

    def to_json(self) -> str:
        """Convert to JSON for SSE transmission."""
        return json.dumps(asdict(self))


async def broadcast_scraper_event(event: ScraperEvent) -> None:
    """Broadcast scraper completion event to all connected SSE clients."""
    async with _queue_lock:
        if not _client_queues:
            logger.debug(f"[LIVE-UPDATES] No connected clients for event: {event.scraper_type}")
            return
        
        # Queue event for all clients
        dead_queues = []
        for q in _client_queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("[LIVE-UPDATES] Client queue full, marking for removal")
                dead_queues.append(q)
        
        # Clean up dead connections
        for q in dead_queues:
            _client_queues.discard(q)
        
        logger.info(
            f"[LIVE-UPDATES] Broadcasted {event.scraper_type} to {len(_client_queues)} clients. "
            f"Status: {event.status}, Updated: {event.rows_updated} rows, Duration: {event.duration_s:.1f}s"
        )


async def register_client_queue(queue: asyncio.Queue) -> None:
    """Register a client queue for receiving events."""
    async with _queue_lock:
        _client_queues.add(queue)
        logger.info(f"[LIVE-UPDATES] Client connected. Total clients: {len(_client_queues)}")


async def unregister_client_queue(queue: asyncio.Queue) -> None:
    """Unregister a client queue when connection closes."""
    async with _queue_lock:
        _client_queues.discard(queue)
        logger.info(f"[LIVE-UPDATES] Client disconnected. Total clients: {len(_client_queues)}")


def publish_scraper_event(
    scraper_type: str,
    status: str,
    rows_updated: int = 0,
    duration_s: float = 0.0,
    error: str = "",
    message: str = ""
) -> None:
    """Publish scraper event from sync context (scheduler jobs).
    
    Use this in scheduler job functions to notify clients.
    """
    event = ScraperEvent(
        scraper_type=scraper_type,
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        message=message,
        rows_updated=rows_updated,
        duration_s=duration_s,
        error=error,
    )
    
    # Resolve the event loop on which broadcast_scraper_event() should run.
    #
    # 1. Prefer the loop saved at API startup by set_main_event_loop() — this is the
    #    documented contract; scheduler / background-thread callers always need it.
    # 2. If we're already running on an event loop (async route handler), schedule
    #    the broadcast as a task on it directly. asyncio.run_coroutine_threadsafe
    #    is documented for cross-thread use only; using it from inside the same loop
    #    works today but is the wrong primitive (W-2 from the pre-merge review).
    # 3. We deliberately do NOT fall back to asyncio.get_event_loop() — Python 3.12+
    #    deprecates that call outside a running loop and 3.14+ raises. The historical
    #    fallback returned a brand-new unrunnable loop and silently dropped events
    #    (M-2 from the pre-merge debug pass). If neither (1) nor (2) is available,
    #    emit a loud WARNING so the contract violation is visible in the logs.
    target_loop = _main_loop
    running_loop: Optional[asyncio.AbstractEventLoop]
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    try:
        if running_loop is not None and (target_loop is None or running_loop is target_loop):
            running_loop.create_task(broadcast_scraper_event(event))
            logger.debug("[LIVE-UPDATES] Scheduled event on running loop: %s -> %s", scraper_type, status)
        elif target_loop is not None:
            asyncio.run_coroutine_threadsafe(broadcast_scraper_event(event), target_loop)
            logger.debug("[LIVE-UPDATES] Queued event on main loop: %s -> %s", scraper_type, status)
        else:
            logger.warning(
                "[LIVE-UPDATES] _main_loop not set and no running loop — event %s "
                "(status=%s) DROPPED. set_main_event_loop() must be called at startup.",
                scraper_type,
                status,
            )
    except Exception as e:
        logger.warning("[LIVE-UPDATES] Failed to queue broadcast: %s", e)


def get_connected_client_count() -> int:
    """Get number of currently connected SSE clients."""
    return len(_client_queues)


def notify_data_changed(
    topic: str,
    *,
    rows_updated: int = 0,
    duration_s: float = 0.0,
    message: str = "",
) -> None:
    """
    Single helper for "I just successfully changed data of kind <topic>".

    Does both halves of the freshness contract atomically from the route's perspective:

      1. ``invalidate_cache(topic)`` — bust any server HTTP cache entries under the
         topic prefix so the **next** GET returns fresh JSON (RFC 9111 §4.4).
      2. ``publish_scraper_event(topic, ...)`` — broadcast over SSE so connected
         browsers re-issue their TanStack Query GETs immediately
         (https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation).

    Call this **after** the DB commit (and after ``refresh_materialized_views()`` if
    the topic depends on a materialized view). Safe in sync routes; safe to call from
    background threads (matches the scheduler-job semantics).

    Args:
        topic: a value from ``api.services.live_topics.Topic`` (e.g.
            ``Topic.TOURNAMENT_HISTORY.value``). Free-form strings are accepted but
            logged as a warning so we catch typos.
        rows_updated: forwarded to ScraperEvent for UI display.
        duration_s: forwarded to ScraperEvent for UI display.
        message: forwarded to ScraperEvent for UI display.
    """
    # Local imports to avoid a circular import (cache_store imports nothing from here,
    # but we keep the dependency one-directional and explicit).
    from api.services.cache_store import invalidate_cache, make_cache_key
    from api.services.live_topics import is_known_topic

    if not is_known_topic(topic):
        logger.warning(
            "notify_data_changed: unknown topic %r — frontend may not invalidate. "
            "Add it to api/services/live_topics.py::Topic.",
            topic,
        )

    try:
        invalidate_cache(make_cache_key(topic))
    except Exception as exc:
        logger.warning("notify_data_changed: invalidate_cache(%s) failed: %s", topic, exc)

    publish_scraper_event(
        scraper_type=topic,
        status="success",
        rows_updated=rows_updated,
        duration_s=duration_s,
        message=message,
    )
