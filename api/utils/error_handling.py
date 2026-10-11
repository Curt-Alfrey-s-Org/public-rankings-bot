"""
Comprehensive error handling utilities for the Rankings Bot API
Provides consistent error handling, logging, and user-friendly responses
"""

import logging
import traceback
from uuid import uuid4
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import json

logger = logging.getLogger(__name__)


def _request_id_from(request: Optional[Request]) -> str:
    if request is None:
        return str(uuid4())
    request_id = getattr(getattr(request, "state", None), "request_id", None) or request.headers.get("X-Request-ID")
    return str(request_id or uuid4())


def _error_response(status_code: int, code: str, message: str, details: Optional[Dict[str, Any]], request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )

class APIError(Exception):
    """Base exception for API errors with consistent error responses"""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ValidationError(APIError):
    """Validation error with 400 status code"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 400, "VALIDATION_ERROR", details)

class AuthenticationError(APIError):
    """Authentication error with 401 status code"""
    def __init__(self, message: str = "Authentication required", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 401, "AUTHENTICATION_ERROR", details)

class AuthorizationError(APIError):
    """Authorization error with 403 status code"""
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 403, "AUTHORIZATION_ERROR", details)

class NotFoundError(APIError):
    """Resource not found error with 404 status code"""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 404, "NOT_FOUND", details)

class ConflictError(APIError):
    """Conflict error with 409 status code"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 409, "CONFLICT", details)

def handle_api_error(error: Exception, request: Optional[Request] = None) -> JSONResponse:
    """
    Convert exceptions to consistent JSON error responses

    Args:
        error: The exception that occurred
        request: Optional FastAPI request object for additional context

    Returns:
        JSONResponse with consistent error format
    """
    request_id = _request_id_from(request)

    # Handle custom API errors
    if isinstance(error, APIError):
        logger.warning(
            f"API Error [{error.error_code}]: {error.message}",
            extra={
                "status_code": error.status_code,
                "error_code": error.error_code,
                "details": error.details,
                "path": request.url.path if request else None,
                "method": request.method if request else None,
                "request_id": request_id,
            }
        )
        return _error_response(
            status_code=error.status_code,
            code=error.error_code,
            message=error.message,
            details=error.details,
            request_id=request_id,
        )

    # Handle HTTP exceptions
    elif isinstance(error, HTTPException):
        log_level = logging.ERROR if error.status_code >= 500 else logging.WARNING
        logger.log(
            log_level,
            "HTTP Exception: %s",
            error.detail,
            extra={
                "status_code": error.status_code,
                "path": request.url.path if request else None,
                "method": request.method if request else None,
                "request_id": request_id,
            },
            exc_info=(error.status_code >= 500),
        )
        return _error_response(
            status_code=error.status_code,
            code="HTTP_EXCEPTION",
            message=str(error.detail),
            details={},
            request_id=request_id,
        )

    # Handle SQLAlchemy errors
    elif isinstance(error, SQLAlchemyError):
        return handle_database_error(error, request, request_id=request_id)

    # Handle other exceptions
    else:
        return handle_unexpected_error(error, request, request_id=request_id)

def handle_database_error(
    error: SQLAlchemyError,
    request: Optional[Request] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Handle database-related errors with appropriate responses"""
    request_id = request_id or _request_id_from(request)

    # Integrity errors (constraint violations)
    if isinstance(error, IntegrityError):
        logger.error(
            f"Database integrity error: {str(error)}",
            extra={
                "error_type": "INTEGRITY_ERROR",
                "path": request.url.path if request else None,
                "traceback": traceback.format_exc(),
                "request_id": request_id,
            }
        )
        return _error_response(
            status_code=409,
            code="DATABASE_INTEGRITY_ERROR",
            message="Data integrity constraint violated",
            details={"original_error": str(error)},
            request_id=request_id,
        )

    # Operational errors (connection, timeout, etc.)
    elif isinstance(error, OperationalError):
        logger.error(
            f"Database operational error: {str(error)}",
            extra={
                "error_type": "OPERATIONAL_ERROR",
                "path": request.url.path if request else None,
                "traceback": traceback.format_exc(),
                "request_id": request_id,
            }
        )
        return _error_response(
            status_code=503,
            code="DATABASE_CONNECTION_ERROR",
            message="Database temporarily unavailable",
            details={"original_error": str(error)},
            request_id=request_id,
        )

    # Generic SQLAlchemy errors
    else:
        logger.error(
            f"Database error: {str(error)}",
            extra={
                "error_type": type(error).__name__,
                "path": request.url.path if request else None,
                "traceback": traceback.format_exc(),
                "request_id": request_id,
            }
        )
        return _error_response(
            status_code=500,
            code="DATABASE_ERROR",
            message="Database operation failed",
            details={"original_error": str(error)},
            request_id=request_id,
        )

def handle_unexpected_error(
    error: Exception,
    request: Optional[Request] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Handle unexpected errors with full logging"""
    request_id = request_id or _request_id_from(request)

    logger.error(
        f"Unexpected error: {str(error)}",
        extra={
            "error_type": type(error).__name__,
            "path": request.url.path if request else None,
            "method": request.method if request else None,
            "traceback": traceback.format_exc(),
            "request_id": request_id,
        },
        exc_info=True
    )

    return _error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        details={},
        request_id=request_id,
    )

def with_error_handling(func):
    """
    Decorator to wrap API route functions with comprehensive error handling

    Usage:
        @with_error_handling
        async def my_route(request: Request):
            # Your route logic here
            pass
    """
    async def wrapper(*args, **kwargs):
        request = None
        # Try to find the request object in arguments
        for arg in args:
            if hasattr(arg, 'url') and hasattr(arg, 'method'):
                request = arg
                break
        for key, arg in kwargs.items():
            if hasattr(arg, 'url') and hasattr(arg, 'method'):
                request = arg
                break

        try:
            return await func(*args, **kwargs)
        except Exception as e:
            return handle_api_error(e, request)

    return wrapper

def safe_db_operation(func):
    """
    Decorator for database operations with automatic transaction handling and error logging

    Usage:
        @safe_db_operation
        def my_db_operation(db: Session):
            # Your database logic here
            pass
    """
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(
                f"Database operation failed in {func.__name__}: {str(e)}",
                extra={
                    "function": func.__name__,
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                },
                exc_info=True
            )
            raise

    return wrapper

def log_api_call(request: Request, response: Any = None, error: Exception = None, duration_ms: float = None):
    """
    Log API calls with consistent format for monitoring and debugging

    Args:
        request: FastAPI request object
        response: Response data (if successful)
        error: Exception (if failed)
        duration_ms: Request duration in milliseconds
    """
    log_data = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query),
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
        "request_id": getattr(getattr(request, "state", None), "request_id", None) or request.headers.get("X-Request-ID"),
    }

    if duration_ms is not None:
        log_data["duration_ms"] = duration_ms

    if error:
        logger.warning(
            f"API call failed: {request.method} {request.url.path}",
            extra={
                **log_data,
                "error": str(error),
                "error_type": type(error).__name__,
                "status_code": getattr(error, 'status_code', None)
            }
        )
    else:
        logger.info(
            f"API call successful: {request.method} {request.url.path}",
            extra=log_data
        )

def create_error_response(error_code: str, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """
    Create a consistent error response

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        JSONResponse with consistent error format
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {}
            }
        }
    )