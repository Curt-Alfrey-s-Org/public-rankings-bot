"""
Performance Timing Utility - Add timestamps to all processes for bottleneck identification

Provides:
- Request/response timing middleware
- Function timing decorators
- Database query timing
- Cache operation timing
- Logging with millisecond precision
"""

import time
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Optional, Callable, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_timestamp() -> str:
    """Get current timestamp in ISO format with milliseconds (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class PerformanceTimer:
    """Context manager for measuring execution time of code blocks."""

    def __init__(self, name: str, threshold_ms: float = 0):
        """
        Args:
            name: Operation name for logging
            threshold_ms: Only log if duration exceeds threshold (0 = always log)
        """
        self.name = name
        self.threshold_ms = threshold_ms
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_sec = time.perf_counter() - self.start_time
        self.duration_ms = duration_sec * 1000

        if self.duration_ms >= self.threshold_ms:
            timestamp = get_timestamp()
            status = "ERROR" if exc_type else "OK"
            logger.info(
                f"[PERF] {timestamp} [{status}] {self.name}: {self.duration_ms:.2f}ms"
            )

        return False  # Don't suppress exceptions


@contextmanager
def timed(name: str, threshold_ms: float = 0):
    """Context manager for timing code blocks."""
    timer = PerformanceTimer(name, threshold_ms)
    with timer:
        yield timer


def timing_decorator(name: Optional[str] = None, threshold_ms: float = 0):
    """
    Decorator to measure function execution time.

    Args:
        name: Operation name (defaults to function name)
        threshold_ms: Only log if duration exceeds threshold
    """

    def decorator(func: Callable) -> Callable:
        operation_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_sec = time.perf_counter() - start_time
                duration_ms = duration_sec * 1000

                if duration_ms >= threshold_ms:
                    timestamp = get_timestamp()
                    logger.info(
                        f"[PERF] {timestamp} [OK] {operation_name}: {duration_ms:.2f}ms"
                    )

        return wrapper

    return decorator


class RequestTimingMiddleware:
    """ASGI middleware to log HTTP request/response times."""

    def __init__(self, app, threshold_ms: float = 0):
        """
        Args:
            app: ASGI application
            threshold_ms: Only log requests exceeding this duration
        """
        self.app = app
        self.threshold_ms = threshold_ms

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_time = time.perf_counter()
        method = scope.get("method", "?")
        path = scope.get("path", "?")

        async def send_with_timing(message):
            if message["type"] == "http.response.start":
                response_time = time.perf_counter()
                duration_sec = response_time - request_time
                duration_ms = duration_sec * 1000
                status_code = message.get("status", "?")

                if duration_ms >= self.threshold_ms:
                    timestamp = get_timestamp()
                    logger.info(
                        f"[PERF] {timestamp} {method} {path} → {status_code} | {duration_ms:.2f}ms"
                    )

            await send(message)

        await self.app(scope, receive, send_with_timing)


def log_process(process_name: str, details: str = ""):
    """Log a process start/completion with timestamp."""
    timestamp = get_timestamp()
    msg = f"[PERF] {timestamp} [PROCESS] {process_name}"
    if details:
        msg += f" — {details}"
    logger.info(msg)


def log_checkpoint(checkpoint_name: str, elapsed_ms: Optional[float] = None):
    """Log a checkpoint in a process with optional elapsed time."""
    timestamp = get_timestamp()
    msg = f"[PERF] {timestamp} [CHECKPOINT] {checkpoint_name}"
    if elapsed_ms is not None:
        msg += f" (+{elapsed_ms:.2f}ms)"
    logger.info(msg)
