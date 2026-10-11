#!/usr/bin/env python3
"""
Base scraper module with retry logic and common utilities.
Provides retry_with_backoff decorator for resilient scraping.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Retry decorator with exponential backoff.
    
    Applies exponential backoff retry logic to functions that may fail transiently.
    Useful for network operations like web scraping and API calls.
    
    Args:
        max_attempts: Maximum number of attempts (default 3).
        initial_delay: Initial delay in seconds (default 2.0).
        backoff_factor: Multiplier for delay between attempts (default 2.0).
        exceptions: Tuple of exception types to catch and retry on (default (Exception,)).
        
    Returns:
        Callable: Decorator function that wraps the target function.
        
    Raises:
        The last caught exception if all attempts are exhausted.
        RuntimeError if all attempts fail without an exception being raised.
        
    Example:
        @retry_with_backoff(max_attempts=3, exceptions=(RequestException,))
        def scrape_data():
            # API call
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            func_name = func.__name__
            
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(f"{func_name}: attempt {attempt}/{max_attempts}")
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func_name} attempt {attempt}/{max_attempts} failed: {type(e).__name__}: {str(e)[:100]}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func_name} failed after {max_attempts} attempts. "
                            f"Last error: {type(e).__name__}: {str(e)[:100]}"
                        )
            
            # All attempts exhausted, raise the last exception
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"{func_name} failed without exception")
                
        return wrapper
    return decorator
