"""
Cache store with Redis primary and in-memory secondary tier.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional
from api.utils.performance import get_timestamp

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles date and datetime objects."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

# Short defaults for live-update feel (app is not I/O/CPU heavy); override via env if needed
DEFAULT_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))
DEFAULT_STALE_TTL_SECONDS = int(os.getenv("CACHE_STALE_TTL_SECONDS", "60"))


@dataclass(frozen=True)
class CacheResult:
    """Cache lookup result."""

    hit: bool
    data: Optional[Any]
    is_stale: bool


_cache_lock = threading.RLock()
_in_memory_cache: Dict[str, Dict[str, Any]] = {}
_redis_client = None
_redis_checked = False


def _get_redis_client():
    """Return Redis client if configured and available; otherwise None."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_checked = True
        _redis_client = None
        return None

    try:
        import redis

        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_checked = True
        return _redis_client
    except ImportError:
        logger.warning("Redis package not installed; falling back to in-memory cache")
        _redis_checked = True
        _redis_client = None
        return None
    except Exception as exc:
        logger.warning("Redis client setup failed: %s", exc)
        _redis_checked = True
        _redis_client = None
        return None


def make_cache_key(*parts: Any) -> str:
    """Build a cache key from parts using ':' separators."""
    cleaned = [str(p).strip().replace(" ", "_") for p in parts if p is not None]
    return ":".join(cleaned)


def _current_epoch() -> float:
    return time.time()


def _cache_entry(data: Any, ttl_seconds: int, stale_ttl_seconds: int) -> Dict[str, Any]:
    return {
        "data": data,
        "fetched_at": _current_epoch(),
        "ttl": ttl_seconds,
        "stale_ttl": stale_ttl_seconds,
    }


def set_cached_json(
    key: str,
    data: Any,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    stale_ttl_seconds: int = DEFAULT_STALE_TTL_SECONDS,
) -> None:
    """Set JSON-serializable data in cache (Redis if available, else in-memory)."""
    start = time.perf_counter()
    entry = _cache_entry(data, ttl_seconds, stale_ttl_seconds)
    redis_client = _get_redis_client()

    if redis_client is not None:
        try:
            payload = json.dumps(entry, cls=DateTimeEncoder)
            redis_client.setex(key, ttl_seconds + stale_ttl_seconds, payload)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug(f"[CACHE] {get_timestamp()} [SET] Redis {key}: {duration_ms:.1f}ms")
            return
        except Exception as exc:
            logger.warning("Redis set failed (%s); falling back to in-memory", exc)

    duration_start = time.perf_counter()
    with _cache_lock:
        _in_memory_cache[key] = entry
    duration_ms = (time.perf_counter() - duration_start) * 1000
    logger.debug(f"[CACHE] {get_timestamp()} [SET] Memory {key}: {duration_ms:.1f}ms")


def _evaluate_entry(entry: Dict[str, Any], allow_stale: bool) -> CacheResult:
    now = _current_epoch()
    fetched_at = float(entry.get("fetched_at", 0))
    ttl = int(entry.get("ttl", DEFAULT_TTL_SECONDS))
    stale_ttl = int(entry.get("stale_ttl", DEFAULT_STALE_TTL_SECONDS))
    age = now - fetched_at

    if age <= ttl:
        return CacheResult(hit=True, data=entry.get("data"), is_stale=False)
    if allow_stale and age <= ttl + stale_ttl:
        return CacheResult(hit=True, data=entry.get("data"), is_stale=True)
    return CacheResult(hit=False, data=None, is_stale=False)


def get_cached_json(key: str, allow_stale: bool = True) -> CacheResult:
    """Get cached JSON data with stale-while-revalidate semantics."""
    start = time.perf_counter()
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            payload = redis_client.get(key)
            if payload:
                entry = json.loads(payload)
                result = _evaluate_entry(entry, allow_stale=allow_stale)
                if result.hit:
                    duration_ms = (time.perf_counter() - start) * 1000
                    status = "HIT" if not result.is_stale else "STALE"
                    logger.debug(f"[CACHE] {get_timestamp()} [GET {status}] Redis {key}: {duration_ms:.1f}ms")
                    return result
                if not allow_stale:
                    redis_client.delete(key)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug(f"[CACHE] {get_timestamp()} [GET MISS] Redis {key}: {duration_ms:.1f}ms")
            return CacheResult(hit=False, data=None, is_stale=False)
        except Exception as exc:
            logger.warning("Redis get failed (%s); falling back to in-memory", exc)

    start = time.perf_counter()
    with _cache_lock:
        entry = _in_memory_cache.get(key)
        if not entry:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug(f"[CACHE] {get_timestamp()} [GET MISS] Memory {key}: {duration_ms:.1f}ms")
            return CacheResult(hit=False, data=None, is_stale=False)
        result = _evaluate_entry(entry, allow_stale=allow_stale)
        if not result.hit:
            _in_memory_cache.pop(key, None)
        duration_ms = (time.perf_counter() - start) * 1000
        status = "HIT" if not result.is_stale else "STALE"
        logger.debug(f"[CACHE] {get_timestamp()} [GET {status}] Memory {key}: {duration_ms:.1f}ms")
        return result


def invalidate_cache(key_prefix: Optional[str] = None) -> None:
    """
    Invalidate cache entries by prefix. If no prefix, clears in-memory cache
    and attempts to flush Redis keys matching the prefix.
    """
    redis_client = _get_redis_client()

    if redis_client is not None:
        try:
            if key_prefix:
                for key in redis_client.scan_iter(match=f"{key_prefix}*"):
                    redis_client.delete(key)
            else:
                redis_client.flushdb()
        except Exception as exc:
            logger.warning("Redis invalidate failed: %s", exc)

    with _cache_lock:
        if key_prefix:
            for key in list(_in_memory_cache.keys()):
                if key.startswith(key_prefix):
                    _in_memory_cache.pop(key, None)
        else:
            _in_memory_cache.clear()


def get_cache_backend() -> str:
    """Return active cache backend name."""
    return "redis" if _get_redis_client() is not None else "memory"
