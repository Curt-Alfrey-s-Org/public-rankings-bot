"""
Global exception handler middleware for FastAPI
Provides consistent error handling for all unhandled exceptions
"""

import logging
import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from api.utils.error_handling import handle_api_error, log_api_call

logger = logging.getLogger(__name__)

class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch all unhandled exceptions and provide consistent error responses
    Also logs API calls for monitoring
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        try:
            # Process the request
            response = await call_next(request)

            # Log successful requests (only in debug mode or for important endpoints)
            if logger.isEnabledFor(logging.DEBUG) or request.url.path in [
                '/api/health', '/api/v1/health'
            ]:
                duration_ms = (time.time() - start_time) * 1000
                log_api_call(request, duration_ms=duration_ms)

            return response

        except Exception as exc:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log the failed request
            log_api_call(request, error=exc, duration_ms=duration_ms)

            # Handle the error with consistent formatting
            return handle_api_error(exc, request)