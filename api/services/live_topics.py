"""
Live topics — single source of truth for "data domain" names used by:

  - api.services.cache_store.invalidate_cache(<topic>)
  - api.services.live_updates.publish_scraper_event(scraper_type=<topic>)
  - frontend useLiveUpdates SSE handler -> queryClient.invalidateQueries

A "topic" is the **prefix** under which related cache keys / React Query keys live.
One topic == one cache prefix == one SSE event type. No translation tables.

Doc refs:
  - RFC 9111 §4.4 (HTTP caching, invalidation tied to writes):
      https://www.rfc-editor.org/rfc/rfc9111#name-invalidating-stored-responses
  - TanStack Query — Query Invalidation (matches by array prefix):
      https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation
  - Project plan: docs/LIVE_UI_FRESHNESS_PLAN.md
"""

from __future__ import annotations

from enum import Enum


class Topic(str, Enum):
    """Stable topic identifiers. The string value is what crosses the wire."""

    TOURNAMENT_HISTORY = "tournament-history"
    UPCOMING_EVENTS = "upcoming-events"
    RANKINGS = "rankings"
    LEADERBOARD = "leaderboard"
    PLAYERS = "players"
    SETTINGS = "settings"
    BACKUPS = "backups"
    CALIBRATION = "calibration"
    FARGO = "fargo"
    SCORES = "scores"
    UPLOADS = "uploads"


KNOWN_TOPICS: frozenset[str] = frozenset(t.value for t in Topic)


def is_known_topic(value: str) -> bool:
    """Return True if `value` is a registered topic string (used for log warnings only)."""
    return value in KNOWN_TOPICS
