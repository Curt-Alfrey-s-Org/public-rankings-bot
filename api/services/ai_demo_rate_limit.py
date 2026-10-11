"""
Public demo (USPBF) rate limiting for POST /api/ai-narrative/demo-ask.

Uses Redis fixed-window counters when REDIS_URL is set (works across API replicas).
Falls back to in-memory sliding window via api.rate_limiter.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def apply_ai_narrative_demo_rate_limit(ip: str) -> None:
    """
    Enforce per-IP limits for the public demo. Raises HTTPException(429) when exceeded.

    Redis (preferred when REDIS_URL set):
      Key: rankings-bot:ai_narrative:demo:{ip}
      Window: AI_NARRATIVE_DEMO_REDIS_WINDOW_SEC (default 300)
      Max: AI_NARRATIVE_DEMO_REDIS_MAX_PER_WINDOW (default 30)

    Fallback: sliding window via api.rate_limiter.check_demo_ask_sliding(ip).
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    window_sec = max(30, _env_int("AI_NARRATIVE_DEMO_REDIS_WINDOW_SEC", 300))
    max_per_window = max(1, _env_int("AI_NARRATIVE_DEMO_REDIS_MAX_PER_WINDOW", 30))

    if redis_url:
        try:
            import redis as redis_lib

            r = redis_lib.from_url(redis_url, decode_responses=True)
            key = f"rankings-bot:ai_narrative:demo:{ip}"
            n = int(r.incr(key))
            if n == 1:
                r.expire(key, window_sec)
            if n > max_per_window:
                ttl = r.ttl(key)
                retry_after = max(1, int(ttl)) if ttl and ttl > 0 else window_sec
                raise HTTPException(
                    status_code=429,
                    detail="Too many demo requests for this network. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "Redis demo rate limit unavailable (%s); using in-memory sliding window",
                exc,
            )

    from api.rate_limiter import check_demo_ask_sliding

    allowed, retry_after = check_demo_ask_sliding(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many demo requests. Please wait and try again.",
            headers={"Retry-After": str(int(max(1.0, retry_after)))},
        )
