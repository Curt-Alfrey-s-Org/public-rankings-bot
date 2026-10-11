"""
Public billiards news aggregated from RSS/Atom feeds (WPBA, WPA, AZBilliards).

Cached in memory to avoid hammering upstream feeds.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Query

from api.services.news_feeds import fetch_one_feed_sync, parse_feeds_env

logger = logging.getLogger(__name__)

router = APIRouter(tags=["news"])

_CACHE_TTL_SEC = 15 * 60
_cache_lock = asyncio.Lock()
_cache_at: float = 0.0
_cached_articles: list[dict[str, Any]] = []


async def _refresh_cache() -> list[dict[str, Any]]:
    feeds = parse_feeds_env()
    timeout = httpx.Timeout(12.0, connect=5.0)

    def _sync_fetch() -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        with httpx.Client(timeout=timeout, headers={"User-Agent": "RankingsBot-NewsFeeds/1.0"}) as client:
            for name, url in feeds:
                merged.extend(fetch_one_feed_sync(client, name, url))
        return merged

    return await asyncio.to_thread(_sync_fetch)


@router.get("/news")
async def get_billiards_news(
    limit: int = Query(10, ge=1, le=50, description="Max articles to return"),
) -> dict[str, Any]:
    """
    Combined billiards headlines from configured RSS feeds.
    Returns empty articles if all feeds fail (never 500 for upstream issues).
    """
    global _cache_at, _cached_articles
    now = time.monotonic()
    async with _cache_lock:
        if _cached_articles and (now - _cache_at) < _CACHE_TTL_SEC:
            return {"articles": _cached_articles[:limit]}

        try:
            merged = await _refresh_cache()
        except Exception:
            logger.exception("News aggregate refresh failed unexpectedly")
            if _cached_articles:
                return {"articles": _cached_articles[:limit]}
            _cached_articles = []
            _cache_at = now
            return {"articles": []}

        _cached_articles = merged
        _cache_at = now
        return {"articles": merged[:limit]}
