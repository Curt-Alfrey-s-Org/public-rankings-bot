"""
Strip technical error payloads from JSON error responses for non-admin clients.

Admin and super_admin JWTs (Authorization: Bearer) receive full responses unchanged.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from api.auth import decode_token

logger = logging.getLogger(__name__)

# Status code -> generic client-safe message (no stack traces, SQL, paths).
_GENERIC_MESSAGE: dict[int, str] = {
    400: "Something was wrong with your request.",
    401: "Authentication required.",
    403: "You don't have permission to do this.",
    404: "The requested resource was not found.",
    405: "This action is not allowed for this resource.",
    408: "The request took too long.",
    409: "A conflict occurred. Please try again.",
    422: "Invalid input. Please check your data.",
    429: "Too many requests. Try again later.",
    500: "Something went wrong.",
    502: "Service temporarily unavailable.",
    503: "Service temporarily unavailable.",
    504: "The service did not respond in time.",
}


def _generic_message_for_status(status_code: int) -> str:
    return _GENERIC_MESSAGE.get(status_code, "An error occurred.")


def _is_admin_or_super_admin_jwt(request: Request) -> bool:
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return False
    token = auth[7:].strip()
    if not token:
        return False
    try:
        payload = decode_token(token)
    except HTTPException:
        return False
    except Exception:
        logger.debug("Error sanitizer: unexpected error decoding JWT", exc_info=True)
        return False
    role = payload.get("role")
    return role in ("admin", "super_admin")


def _sanitize_json_body(data: Any, status_code: int) -> Any:
    """Return a copy-safe structure for JSON error responses."""
    generic = _generic_message_for_status(status_code)

    if isinstance(data, dict):
        # FastAPI / Starlette style
        if "detail" in data:
            out = dict(data)
            detail = data["detail"]
            if isinstance(detail, str):
                out["detail"] = generic
            elif isinstance(detail, list):
                # Validation errors — replace with single generic message
                out["detail"] = generic
            else:
                out["detail"] = generic
            return out

        # Structured API errors from error_handling._error_response
        err = data.get("error")
        if isinstance(err, dict):
            out = dict(data)
            err_out = dict(err)
            code = err_out.get("code")
            request_id = err_out.get("request_id")
            err_out["message"] = generic
            err_out["details"] = {}
            if code is not None:
                err_out["code"] = code
            if request_id is not None:
                err_out["request_id"] = request_id
            out["error"] = err_out
            return out

    return data


def _content_type_is_json(ct: str | None) -> bool:
    if not ct:
        return False
    return "application/json" in ct.split(";")[0].strip().lower()


async def _read_response_body(response: Response) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


class ErrorSanitizerMiddleware(BaseHTTPMiddleware):
    """Rewrite JSON error bodies for clients without admin/super_admin Bearer JWT."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        status = getattr(response, "status_code", 200)
        if status < 400:
            return response

        if _is_admin_or_super_admin_jwt(request):
            return response

        ct = response.headers.get("content-type")
        if not _content_type_is_json(ct):
            return response

        try:
            body = await _read_response_body(response)
        except Exception:
            logger.exception("Error sanitizer: failed to read response body")
            return response

        if not body:
            return Response(
                content=body,
                status_code=status,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                content=body,
                status_code=status,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        sanitized = _sanitize_json_body(data, status)

        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-type")
        }

        return JSONResponse(
            content=sanitized,
            status_code=status,
            headers=headers,
        )
