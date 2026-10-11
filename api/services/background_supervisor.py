"""Background task supervision with crash tracking and backoff restart."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

_TASK_STATE: dict[str, dict] = {}


def get_background_task_health() -> dict:
    """Expose supervisor status for health endpoints."""
    return {name: dict(state) for name, state in _TASK_STATE.items()}


def start_supervised_task(
    name: str,
    coroutine_factory: Callable[[], Awaitable[None]],
    *,
    crash_threshold: int = 3,
    crash_window_sec: int = 300,
    base_backoff_sec: float = 1.0,
    max_backoff_sec: float = 30.0,
) -> asyncio.Task:
    """Start a supervised background task that auto-restarts on crash."""

    state = {
        "status": "starting",
        "crash_count_total": 0,
        "recent_crashes": 0,
        "degraded": False,
        "last_error": None,
        "last_started_at": time.time(),
        "last_completed_at": None,
    }
    _TASK_STATE[name] = state
    recent_crash_times: deque[float] = deque(maxlen=100)

    async def _runner():
        backoff = base_backoff_sec
        while True:
            try:
                state["status"] = "running"
                state["last_started_at"] = time.time()
                await coroutine_factory()
                state["status"] = "completed"
                state["last_completed_at"] = time.time()
                return
            except asyncio.CancelledError:
                state["status"] = "stopped"
                raise
            except Exception as exc:
                now = time.time()
                state["status"] = "crashed"
                state["crash_count_total"] += 1
                state["last_error"] = str(exc)
                recent_crash_times.append(now)
                while recent_crash_times and now - recent_crash_times[0] > crash_window_sec:
                    recent_crash_times.popleft()
                state["recent_crashes"] = len(recent_crash_times)
                state["degraded"] = len(recent_crash_times) >= crash_threshold
                logger.exception(
                    "Background task '%s' crashed (recent=%s, total=%s), restarting in %.1fs",
                    name,
                    state["recent_crashes"],
                    state["crash_count_total"],
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff_sec)

    return asyncio.create_task(_runner(), name=f"supervised:{name}")
