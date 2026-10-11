"""
Prometheus metrics middleware for FastAPI.
Tracks HTTP request metrics for Prometheus scraping.
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

try:
    from api.routes.metrics import (
        http_requests_total,
        http_request_duration_seconds,
        http_request_size_bytes,
        http_response_size_bytes,
        PROMETHEUS_AVAILABLE
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    http_requests_total = None
    http_request_duration_seconds = None
    http_request_size_bytes = None
    http_response_size_bytes = None


def _normalize_path(path: str) -> str:
    """
    Normalize API paths for metrics aggregation.
    Replaces dynamic segments (IDs, UUIDs) with placeholders.
    """
    # Remove query strings
    if '?' in path:
        path = path.split('?')[0]
    
    # Normalize common patterns
    import re
    
    # Replace UUIDs
    path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path, flags=re.IGNORECASE)
    
    # Replace numeric IDs
    path = re.sub(r'/\d+', '/{id}', path)
    
    # Limit path length for cardinality
    if len(path) > 100:
        path = path[:100]
    
    return path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP metrics for Prometheus."""
    
    async def dispatch(self, request: Request, call_next):
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)
        
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        method = request.method
        path = _normalize_path(request.url.path)
        
        # Track request size from header to avoid consuming request streams.
        request_size = 0
        try:
            content_length = request.headers.get("content-length")
            if content_length:
                request_size = int(content_length)
        except (TypeError, ValueError):
            request_size = 0
        
        # Start timer
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Get response size
            response_size = 0
            if hasattr(response, 'body'):
                try:
                    response_size = len(response.body)
                except Exception as e:
                    logger.debug("Metrics recording failed: %s", e)
            
            # Record metrics
            status_code = getattr(response, 'status_code', 200)
            status_class = f"{status_code // 100}xx"
            
            try:
                http_requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=status_class
                ).inc()
                
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=path
                ).observe(duration)
                
                if request_size > 0:
                    http_request_size_bytes.labels(
                        method=method,
                        endpoint=path
                    ).observe(request_size)
                
                if response_size > 0:
                    http_response_size_bytes.labels(
                        method=method,
                        endpoint=path
                    ).observe(response_size)
            except Exception as e:
                logger.warning("Error recording Prometheus metrics: %s", e)
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            status_class = "5xx"
            
            try:
                http_requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=status_class
                ).inc()
                
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=path
                ).observe(duration)
            except Exception as e:
                logger.debug("Metrics recording failed: %s", e)
            
            raise
