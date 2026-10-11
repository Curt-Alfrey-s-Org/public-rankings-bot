"""Simple in-process circuit breaker for external service calls."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class CircuitBreakerState:
    failures: int = 0
    opened_at: float | None = None
    half_open_probe_in_flight: bool = False


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the breaker is open and calls are blocked."""


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout_sec: int = 30):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout_sec = max(1, recovery_timeout_sec)
        self._state = CircuitBreakerState()
        self._lock = threading.Lock()

    def _is_open(self, now: float) -> bool:
        if self._state.opened_at is None:
            return False
        return (now - self._state.opened_at) < self.recovery_timeout_sec

    def call(self, fn, *args, **kwargs):
        now = time.monotonic()
        with self._lock:
            if self._is_open(now):
                raise CircuitBreakerOpenError(f"{self.name} circuit breaker is open")

            # Allow exactly one trial call after cooldown.
            if self._state.opened_at is not None and not self._is_open(now):
                if self._state.half_open_probe_in_flight:
                    raise CircuitBreakerOpenError(f"{self.name} half-open probe already running")
                self._state.half_open_probe_in_flight = True

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._state.failures += 1
                if self._state.failures >= self.failure_threshold:
                    self._state.opened_at = time.monotonic()
                self._state.half_open_probe_in_flight = False
            raise

        with self._lock:
            self._state.failures = 0
            self._state.opened_at = None
            self._state.half_open_probe_in_flight = False
        return result
