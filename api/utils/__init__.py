# API utilities package
"""
API utilities - combines performance monitoring with bot integration helpers.
"""

from typing import Any, Dict, Optional

# Performance monitoring utilities
from .performance import (
    get_timestamp,
    PerformanceTimer,
    timing_decorator,
    RequestTimingMiddleware,
    log_process,
    log_checkpoint
)

# Bot integration helpers (return None/empty in API-only mode)
def is_bot_running() -> bool:
    """Rankings API runs without an embedded bot process."""
    return False


def get_bot_instance() -> Optional[Any]:
    """Return the running bot instance if available; otherwise None."""
    return None

def get_startup_timings() -> Dict[str, Any]:
    """Return startup timings for health/status. Empty when not tracked."""
    return {}

__all__ = [
    'get_timestamp',
    'PerformanceTimer',
    'timing_decorator',
    'RequestTimingMiddleware',
    'log_process',
    'log_checkpoint',
    'is_bot_running',
    'get_bot_instance',
    'get_startup_timings'
]
