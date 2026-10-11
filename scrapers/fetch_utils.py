"""
Shared fetch helpers for scrapers: retries, rate-limit and error handling.
"""
import logging
import os
import time
from typing import Dict, Optional

import requests
try:
    from api.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
except Exception:  # pragma: no cover - scraper still works without breaker module
    CircuitBreaker = None  # type: ignore
    CircuitBreakerOpenError = RuntimeError  # type: ignore

logger = logging.getLogger(__name__)

# Status codes we retry (rate limit + transient server errors)
RETRY_STATUSES = (429, 502, 503, 504)

# Default backoff seconds when Retry-After is not present
DEFAULT_BACKOFF = (2, 4, 8)
MIN_REQUEST_INTERVAL_SEC = max(0.0, float(os.getenv("SCRAPER_MIN_REQUEST_INTERVAL_SEC", "0.3")))
SCRAPER_HTTP_BREAKER = (
    CircuitBreaker(name="scraper-http", failure_threshold=5, recovery_timeout_sec=45)
    if CircuitBreaker
    else None
)
_LAST_REQUEST_AT = 0.0
_SCRAPER_METRICS = {
    "requests_total": 0,
    "requests_failed": 0,
    "retries_total": 0,
    "breaker_rejections": 0,
    "last_error": None,
    "last_error_at": None,
}


def get_with_retry(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = 30,
    max_retries: int = 3,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    """
    GET url with retries on rate limit (429) and transient errors (502, 503, 504).
    Uses Retry-After when present, otherwise exponential backoff.
    On final failure, raises (no stale cached response).

    Raises:
        requests.RequestException: On final failure after all retries.
    """
    session = session or requests.Session()
    last_exc = None
    global _LAST_REQUEST_AT

    _SCRAPER_METRICS["requests_total"] += 1

    # Optional global request pacing to reduce remote throttling.
    if MIN_REQUEST_INTERVAL_SEC > 0:
        now = time.monotonic()
        elapsed = now - _LAST_REQUEST_AT
        if elapsed < MIN_REQUEST_INTERVAL_SEC:
            time.sleep(MIN_REQUEST_INTERVAL_SEC - elapsed)
        _LAST_REQUEST_AT = time.monotonic()

    for attempt in range(max_retries):
        try:
            if SCRAPER_HTTP_BREAKER is not None:
                resp = SCRAPER_HTTP_BREAKER.call(
                    session.get, url, headers=headers or {}, timeout=timeout
                )
            else:
                resp = session.get(url, headers=headers or {}, timeout=timeout)

            if resp.status_code in RETRY_STATUSES and attempt < max_retries - 1:
                _SCRAPER_METRICS["retries_total"] += 1
                wait = _wait_seconds(resp, attempt)
                logger.warning(
                    "Scraper got %s from %s; retry %s/%s in %s s",
                    resp.status_code,
                    url[:60],
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        except requests.Timeout as e:
            last_exc = e
            if attempt < max_retries - 1:
                _SCRAPER_METRICS["retries_total"] += 1
                wait = DEFAULT_BACKOFF[min(attempt, len(DEFAULT_BACKOFF) - 1)]
                logger.warning(
                    "Scraper timeout for %s; retry %s/%s in %s s",
                    url[:60],
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
            else:
                break
        except CircuitBreakerOpenError:
            _SCRAPER_METRICS["breaker_rejections"] += 1
            last_exc = requests.RequestException("Scraper circuit breaker open; retry later")
            break
        except requests.RequestException as e:
            last_exc = e
            if attempt < max_retries - 1:
                _SCRAPER_METRICS["retries_total"] += 1
                wait = DEFAULT_BACKOFF[min(attempt, len(DEFAULT_BACKOFF) - 1)]
                logger.warning(
                    "Scraper error %s for %s; retry %s/%s in %s s",
                    type(e).__name__,
                    url[:60],
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
            else:
                break

    _SCRAPER_METRICS["requests_failed"] += 1
    _SCRAPER_METRICS["last_error"] = str(last_exc) if last_exc else "unknown scraper error"
    _SCRAPER_METRICS["last_error_at"] = time.time()
    if last_exc:
        raise last_exc
    raise requests.RequestException(f"Failed after {max_retries} attempts")


def _wait_seconds(response: requests.Response, attempt: int) -> float:
    """Prefer Retry-After header; else use exponential backoff."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError as e:
            logger.debug("Invalid Retry-After header '%s': %s", retry_after, e)
    return float(DEFAULT_BACKOFF[min(attempt, len(DEFAULT_BACKOFF) - 1)])


def get_scraper_health_metrics() -> dict:
    """Return scraper fetch reliability metrics for health endpoint."""
    return dict(_SCRAPER_METRICS)
