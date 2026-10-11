"""
Client IP for rate limiting, login lockout/honeypot IP blocks and audit logs.

Review 2026-09-25 (MEDIUM): the API used to take the FIRST X-Forwarded-For value, which any
client can set (nginx's $proxy_add_x_forwarded_for appends to whatever the client sent), so
per-IP limits and IP blocks could be bypassed or pointed at someone else.

The app no longer parses X-Forwarded-For itself. Uvicorn's ProxyHeadersMiddleware
(``--proxy-headers`` + ``--forwarded-allow-ips``, see scripts/docker-api-cmd.sh) resolves the
client address: it only honours X-Forwarded-For when the TCP peer is a trusted proxy and
then walks the list right-to-left, skipping trusted proxies, so client-supplied values on
the left are ignored. ``request.client.host`` is therefore already the proxy-resolved IP.

Operator setting: FORWARDED_ALLOW_IPS (docs/ENV_VARS.md, "Trusted proxies").
"""

from __future__ import annotations

from typing import Any, Optional


def get_client_ip(request: Any) -> Optional[str]:
    """Proxy-resolved client IP (request.client.host), or None when unavailable."""
    if request is None:
        return None
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host or None
