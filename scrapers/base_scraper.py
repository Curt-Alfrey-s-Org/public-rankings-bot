#!/usr/bin/env python3
"""
Base Scraper Module
Provides common scraping utilities including retry logic with exponential backoff
"""

import functools
import logging
import time
from typing import Callable, Any, List, Tuple

logger = logging.getLogger(__name__)


class NonRetryableError(Exception):
    """Exception type for errors that should not be retried."""


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    retry_on_exceptions: Tuple[type, ...] = (Exception,),
    non_retryable_exceptions: Tuple[type, ...] = (),
    retry_on_empty: bool = True,
) -> Callable:
    """
    Decorator that implements retry logic with exponential backoff.
    
    This decorator will retry a function if it fails or returns an empty list.
    The delay between retries increases exponentially with each attempt.
    If all attempts fail, the function returns an empty list for graceful degradation.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 2.0)
        backoff_factor: Multiplier for delay after each attempt (default: 2.0)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=2.0)
        def scrape_rankings(self):
            # scraping logic
            return rankings
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> List:
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Check if result is empty or None
                    if retry_on_empty and not result:
                        if attempt < max_attempts:
                            logger.warning(
                                f"⚠️ {func.__name__} returned empty result "
                                f"(attempt {attempt}/{max_attempts}). "
                                f"Retrying in {delay:.1f}s..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                        else:
                            logger.error(
                                f"❌ {func.__name__} failed after {max_attempts} attempts. "
                                f"Returning empty list."
                            )
                            return []
                    
                    # Success case
                    if attempt > 1:
                        logger.info(
                            f"✅ {func.__name__} succeeded on attempt {attempt}/{max_attempts}"
                        )
                    
                    return result
                    
                except Exception as e:
                    if non_retryable_exceptions and isinstance(e, non_retryable_exceptions):
                        logger.error(
                            f"❌ {func.__name__} encountered non-retryable error: {type(e).__name__}: {e}. "
                            f"Returning empty list."
                        )
                        return []
                    if not isinstance(e, retry_on_exceptions):
                        logger.error(
                            f"❌ {func.__name__} failed with non-retryable error: {type(e).__name__}: {e}. "
                            f"Returning empty list."
                        )
                        return []
                    if attempt < max_attempts:
                        logger.warning(
                            f"⚠️ {func.__name__} failed with {type(e).__name__}: {e} "
                            f"(attempt {attempt}/{max_attempts}). "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts. "
                            f"Last error: {type(e).__name__}: {e}. "
                            f"Returning empty list."
                        )
                        return []
            
            # Unreachable (guard return)
            return []
        
        return wrapper
    return decorator
