"""Middleware for request correlation IDs."""

import re
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9\-_.]{1,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID to request state and response headers."""

    async def dispatch(self, request, call_next):
        incoming = (request.headers.get("X-Request-ID") or "").strip()
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else str(uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
