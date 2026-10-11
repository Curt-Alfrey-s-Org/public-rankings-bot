"""
Request/Response Logging Middleware
Logs all API requests and responses for debugging
"""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Log request
        start_time = time.time()
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else ""
        
        logger.debug(f"→ {method} {path}{'?' + query_params if query_params else ''}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            status_code = response.status_code
            if status_code >= 500:
                logger.error(f"← {method} {path} - {status_code} ({duration:.3f}s)")
            elif status_code >= 400:
                logger.warning(f"← {method} {path} - {status_code} ({duration:.3f}s)")
            else:
                logger.debug(f"← {method} {path} - {status_code} ({duration:.3f}s)")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"✗ {method} {path} - Exception after {duration:.3f}s: {e}", exc_info=True)
            raise
