"""
API access control middleware for /api/* (review 2026-09-25, finding 18).

Policy (documented in docs/API_ACCESS_POLICY.md; keep both in sync):

1. OPEN (any method, no key, no token): liveness and the login/registration flow
   - /api/health, /api/app-version, /api/v1/config, /api/v1/health*, /api/auth/*, /api/v1/auth/*
2. PUBLIC READ (GET/HEAD only, no key, no token): endpoints the web app loads before
   sign-in or from the browser where no custom header can be sent (<img>/<video> src,
   EventSource). All are read-only and carry no private data.
   - /api/splash-config, /api/login-features, /api/media/slideshow, /api/assets/serve/*,
     /api/live/updates, /api/live/status, /api/tournaments/{id}/stream,
     /api/docs/notifications-email, /api/docs/director-import
3. EVERYTHING ELSE under /api/ needs one of:
   a) a valid Bearer token (JWT from login, or a legacy auth_sessions token), or
   b) a valid X-API-Key (BOT_API_KEY) AND X-User-Role of "user" or "admin"
      (server-to-server callers such as the USPBF nginx proxy). A missing or empty
      X-User-Role is rejected (401) on every such path, with no per-path exemptions
      (follow-up 2026-09-25: the demo-ask and /api/test-tournaments exemptions were removed;
      the USPBF proxy always sends X-User-Role: user, and test-center writes need a JWT).
   The role header never grants privileges by itself: route dependencies still read
   the role from the JWT, so admin/director write routes keep requiring a Bearer token.
4. A token issued while must_change_password is set (api.auth.PASSWORD_CHANGE_CLAIM)
   is rejected with 403 everywhere except the password-change flow.

RequireApiKeyMiddleware enforces 3b's key part for anonymous requests; RequireUserOrAdminMiddleware
validates Bearer tokens, the role header, and rule 4. Register both (see api/main.py).
"""

from __future__ import annotations

import hmac
import logging
import re
from typing import Callable, Optional

import jwt
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api import auth as auth_lib

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
ROLE_HEADER = "X-User-Role"
JWT_ROLES = ("admin", "director", "user", "super_admin", "score_keeper")
ANONYMOUS_ROLE_HEADERS = ("user", "admin")

_OPEN_EXACT = frozenset({"/api/health", "/api/app-version", "/api/v1/config", "/api/auth", "/api/v1/auth"})
_OPEN_PREFIXES = ("/api/auth/", "/api/v1/auth/", "/api/v1/health")

_PUBLIC_READ_METHODS = frozenset({"GET", "HEAD"})
_PUBLIC_READ_EXACT = frozenset({
    "/api/splash-config",
    "/api/login-features",
    "/api/media/slideshow",
    "/api/live/updates",
    "/api/live/status",
    "/api/docs/notifications-email",  # static help text opened via <a href> in the web app
    "/api/docs/director-import",
})
_PUBLIC_READ_PREFIXES = ("/api/assets/serve/",)
_PUBLIC_READ_PATTERNS = (re.compile(r"^/api/tournaments/[^/]+/stream$"),)

# Paths a restricted (must_change_password) token may use besides /api/auth/* (which the
# auth routes guard themselves via get_current_user_allow_password_change).
PASSWORD_CHANGE_ALLOWED_PATHS = frozenset({"/api/users/change-password"})

def _normalize(path: str) -> str:
    return path.rstrip("/") or "/"


def is_open_path(path: str) -> bool:
    p = _normalize(path)
    return p in _OPEN_EXACT or p.startswith(_OPEN_PREFIXES)


def is_public_read(method: str, path: str) -> bool:
    if method.upper() not in _PUBLIC_READ_METHODS:
        return False
    p = _normalize(path)
    if p in _PUBLIC_READ_EXACT or p.startswith(_PUBLIC_READ_PREFIXES):
        return True
    return any(rx.match(p) for rx in _PUBLIC_READ_PATTERNS)


def is_public_request(method: str, path: str) -> bool:
    """True when the request needs neither an API key nor a token."""
    return (not path.startswith("/api/")) or is_open_path(path) or is_public_read(method, path)


def _bearer_token(request: Request) -> Optional[str]:
    header = (request.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        return token or None
    return None


def _json(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


class RequireApiKeyMiddleware(BaseHTTPMiddleware):
    """Anonymous (no Bearer) non-public /api/* requests must send X-API-Key == BOT_API_KEY.

    Requests with a Bearer token are passed on; RequireUserOrAdminMiddleware validates the token.
    api_key empty: 503 (production), or allowed with a warning when allow_missing_key=True (DEBUG dev only).
    """

    def __init__(self, app, api_key: str = "", allow_missing_key: bool = False):
        super().__init__(app)
        self.api_key = (api_key or "").strip()
        self.allow_missing_key = allow_missing_key
        self._warned_missing = False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if is_public_request(request.method, path):
            return await call_next(request)
        if _bearer_token(request):
            return await call_next(request)
        if not self.api_key:
            if self.allow_missing_key:
                if not self._warned_missing:
                    logger.warning("BOT_API_KEY not set: API key check disabled (DEBUG mode only).")
                    self._warned_missing = True
                return await call_next(request)
            return _json(503, "BOT_API_KEY not configured")
        provided = (request.headers.get(API_KEY_HEADER) or "").strip()
        if not provided or not hmac.compare_digest(provided.encode("utf-8"), self.api_key.encode("utf-8")):
            return _json(401, "Invalid or missing API key")
        return await call_next(request)


def _default_session_validator(token: str) -> tuple[bool, Optional[str]]:
    from api.routes.auth import validate_token

    return validate_token(token)


class RequireUserOrAdminMiddleware(BaseHTTPMiddleware):
    """Validate Bearer tokens server-side; without a token require X-User-Role user/admin
    (the key itself is checked by RequireApiKeyMiddleware). Enforces must_change_password."""

    def __init__(
        self,
        app,
        session_validator: Optional[Callable[[str], tuple[bool, Optional[str]]]] = None,
    ):
        super().__init__(app)
        self.session_validator = session_validator or _default_session_validator

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if is_public_request(request.method, path):
            return await call_next(request)
        token = _bearer_token(request)
        if token:
            try:
                payload = jwt.decode(token, auth_lib.SECRET_KEY, algorithms=[auth_lib.ALGORITHM])
                if payload.get("role") in JWT_ROLES:
                    if (
                        payload.get(auth_lib.PASSWORD_CHANGE_CLAIM)
                        and _normalize(path) not in PASSWORD_CHANGE_ALLOWED_PATHS
                        and await run_in_threadpool(auth_lib.password_change_pending, payload)
                    ):
                        return _json(403, auth_lib.PASSWORD_CHANGE_REQUIRED_DETAIL)
                    return await call_next(request)
            except jwt.InvalidTokenError as e:  # includes ExpiredSignatureError
                logger.debug("Bearer JWT validation failed in middleware: %s", e)
            # Fall back to session token (auth_sessions) for legacy tokens.
            valid, _role = await run_in_threadpool(self.session_validator, token)
            if not valid:
                return _json(401, "Invalid or expired token")
            return await call_next(request)

        role = (request.headers.get(ROLE_HEADER) or "").strip().lower()
        if not role:
            return _json(401, "Not authenticated. Sign in, or send X-API-Key with X-User-Role.")
        if role not in ANONYMOUS_ROLE_HEADERS:
            return _json(403, "Sign in as user or admin to access.")
        return await call_next(request)
