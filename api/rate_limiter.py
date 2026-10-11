"""
Per-IP rate limiter for auth login and rankings endpoints.
Used by middleware in main.py to return 429 when limits are exceeded.

Client IP: proxy-resolved by Uvicorn (see api/client_ip.py); client-supplied
X-Forwarded-For values are never trusted here (review 2026-09-25).

Memory: the store is bounded. Stale keys are swept periodically and the number of tracked
keys is capped (RATE_LIMIT_MAX_KEYS, default 50000); when the cap is hit the least recently
used keys are evicted.

Limits are per Uvicorn worker process (in-memory); with UVICORN_WORKERS=N the effective
login limit is up to N x LOGIN_LIMIT. The public AI demo uses Redis when REDIS_URL is set.
"""

import os
import time
import threading
import logging
from collections import deque, defaultdict
from typing import Tuple

from api.client_ip import get_client_ip

logger = logging.getLogger(__name__)

# Per-IP sliding window: key = (ip, bucket), value = deque of timestamps
_store: dict[tuple[str, str], deque] = defaultdict(deque)
_windows: dict[tuple[str, str], float] = {}  # window (seconds) last used for each key
_lock = threading.Lock()
_last_sweep = 0.0
_SWEEP_INTERVAL_SEC = 60.0


def _max_keys() -> int:
    try:
        return max(100, int(os.getenv("RATE_LIMIT_MAX_KEYS", "50000")))
    except ValueError:
        return 50000

# Limits: (max_calls, time_window_seconds)
LOGIN_LIMIT = (10, 60)   # 10 login attempts per minute per IP
RANKINGS_LIMIT = (120, 60)  # 120 requests per minute per IP (rankings read)
REFRESH_LIMIT = (1, 300)  # 1 refresh per 5 minutes (global)
AI_COACH_LIMIT = (10, 3600)  # 10 analyses per hour per user (admin+ exempt in route)
RANKINGS_ASSISTANT_LIMIT = (30, 3600)  # per login per hour (player, director, scorekeeper tablet, etc.)
RANKINGS_ASSISTANT_ADMIN_LIMIT = (120, 3600)  # admin / super_admin


def _client_ip(request) -> str:
    """Proxy-resolved client IP (never the raw, client-controlled X-Forwarded-For)."""
    return get_client_ip(request) or "unknown"


def _sweep_locked(now: float) -> None:
    """Drop expired keys; if still over the cap, evict least recently used keys. Caller holds _lock."""
    global _last_sweep
    _last_sweep = now
    for key in list(_store.keys()):
        q = _store[key]
        window = _windows.get(key, 3600.0)
        if not q or q[-1] < now - window:
            _store.pop(key, None)
            _windows.pop(key, None)
    cap = _max_keys()
    if len(_store) > cap:
        target = int(cap * 0.9)
        by_last_use = sorted(_store.items(), key=lambda kv: kv[1][-1] if kv[1] else 0.0)
        for key, _q in by_last_use[: len(_store) - target]:
            _store.pop(key, None)
            _windows.pop(key, None)
        logger.warning("Rate limiter store exceeded %d keys; evicted least recently used entries", cap)


def _check(ip: str, bucket: str, max_calls: int, window_sec: float) -> Tuple[bool, float]:
    """
    Check if (ip, bucket) is under limit. If allowed, record the call.
    Returns (allowed, retry_after_seconds). retry_after_seconds is 0 if allowed.
    """
    now = time.time()
    key = (ip, bucket)
    with _lock:
        if abs(now - _last_sweep) >= _SWEEP_INTERVAL_SEC or len(_store) >= _max_keys():
            _sweep_locked(now)
        _windows[key] = window_sec
        q = _store[key]
        cutoff = now - window_sec
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) < max_calls:
            q.append(now)
            return True, 0.0
        oldest = q[0] if q else now
        retry_after = (oldest + window_sec) - now
        return False, max(0.0, retry_after)


def check_login(request) -> Tuple[bool, float]:
    """Per-IP rate limit for login. Returns (allowed, retry_after_seconds)."""
    ip = _client_ip(request)
    max_calls, window = LOGIN_LIMIT
    return _check(ip, "login", max_calls, float(window))


def check_rankings(request) -> Tuple[bool, float]:
    """Per-IP rate limit for rankings. Returns (allowed, retry_after_seconds)."""
    ip = _client_ip(request)
    max_calls, window = RANKINGS_LIMIT
    return _check(ip, "rankings", max_calls, float(window))


def check_rate_limit(endpoint: str) -> Tuple[bool, float]:
    """
    Global rate limit for specific endpoints (not per-IP).
    Used for refresh and alfa-recompute endpoints.
    Returns (allowed, retry_after_seconds).
    """
    # Use a fixed "global" IP for these endpoint-wide limits
    global_ip = "global"
    max_calls, window = REFRESH_LIMIT  # Default to refresh limit
    return _check(global_ip, endpoint, max_calls, float(window))


def check_ai_coach_limit(user_id: str) -> Tuple[bool, float]:
    """
    Per-user rate limit for AI Coach analyze endpoint.
    Returns (allowed, retry_after_seconds). Caller must exempt admin/super_admin.
    """
    uid = str(user_id) if user_id else "anonymous"
    max_calls, window = AI_COACH_LIMIT
    return _check(uid, "ai_coach", max_calls, float(window))


def check_rankings_assistant_limit(user_id: str, role: str) -> Tuple[bool, float]:
    """
    Per-user rate limit for Rankings Assistant (Ollama) Q&A.
    Higher cap for admin and super_admin.
    """
    uid = str(user_id) if user_id else "anonymous"
    if (role or "").strip().lower() in ("admin", "super_admin"):
        max_calls, window = RANKINGS_ASSISTANT_ADMIN_LIMIT
    else:
        max_calls, window = RANKINGS_ASSISTANT_LIMIT
    return _check(uid, "rankings_assistant", max_calls, float(window))


def _demo_sliding_limit() -> Tuple[int, float]:
    """Max calls and window (seconds) for public AI demo when Redis is not used."""
    try:
        max_calls = int(os.getenv("AI_NARRATIVE_DEMO_SLIDING_MAX", "15"))
    except ValueError:
        max_calls = 15
    try:
        window = float(os.getenv("AI_NARRATIVE_DEMO_SLIDING_WINDOW_SEC", "60"))
    except ValueError:
        window = 60.0
    return max(1, max_calls), max(10.0, window)


def check_demo_ask_sliding(ip: str) -> Tuple[bool, float]:
    """
    Per-IP sliding window for POST /api/ai-narrative/demo-ask when REDIS_URL is unset.
    """
    max_calls, window = _demo_sliding_limit()
    return _check(ip, "ai_narrative_demo", max_calls, window)

