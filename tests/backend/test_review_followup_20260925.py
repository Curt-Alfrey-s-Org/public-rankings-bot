"""Follow-up fixes for the 2026-09-25 review (Medium/Low items + leftovers of PR #21).

- Client IP: the app no longer trusts the first X-Forwarded-For value; Uvicorn's
  ProxyHeadersMiddleware (scripts/docker-api-cmd.sh) resolves it from trusted proxies only.
- In-memory rate limiter store is bounded.
- force_password_reset is enforced server-side like must_change_password.
- POST /api/media/scrape requires admin.
- Maintenance scripts need DATABASE_URL from the environment (no hardcoded credentials).
"""
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-production")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from api import auth  # noqa: E402
from api import rate_limiter  # noqa: E402
from api.client_ip import get_client_ip  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.0.2.0/24"


def _request(client_host, xff=None):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {"type": "http", "method": "POST", "path": "/api/auth/login", "headers": headers,
             "client": (client_host, 12345) if client_host else None}
    return Request(scope)


class TestClientIp(unittest.TestCase):
    def test_raw_x_forwarded_for_is_ignored(self):
        req = _request("198.51.100.7", xff="1.2.3.4")
        self.assertEqual(get_client_ip(req), "198.51.100.7")
        self.assertEqual(rate_limiter._client_ip(req), "198.51.100.7")

    def test_missing_client(self):
        self.assertIsNone(get_client_ip(None))
        self.assertIsNone(get_client_ip(_request(None)))
        self.assertEqual(rate_limiter._client_ip(_request(None)), "unknown")

    def test_launcher_enables_proxy_headers_with_private_default(self):
        script = (REPO_ROOT / "scripts" / "docker-api-cmd.sh").read_text()
        self.assertIn("--proxy-headers", script)
        self.assertIn('--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"', script)
        self.assertIn(DEFAULT_FORWARDED_ALLOW_IPS, script)

    def _resolved_client(self, peer, xff):
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

        seen = {}

        async def app(scope, receive, send):
            seen["client"] = scope.get("client")

        mw = ProxyHeadersMiddleware(app, trusted_hosts=DEFAULT_FORWARDED_ALLOW_IPS.split(","))
        scope = {"type": "http", "client": (peer, 5555), "headers": [(b"x-forwarded-for", xff.encode())]}
        import asyncio

        asyncio.run(mw(scope, None, None))
        return seen["client"][0]

    def test_uvicorn_uses_rightmost_untrusted_hop(self):
        # client spoofs "1.2.3.4"; Cloudflare appends the real IP; nginx hops are private.
        self.assertEqual(
            self._resolved_client("172.18.0.5", "1.2.3.4, 198.51.100.7, 172.18.0.3"), "198.51.100.7"
        )

    def test_uvicorn_ignores_header_from_untrusted_peer(self):
        self.assertEqual(self._resolved_client("203.0.113.9", "1.2.3.4"), "203.0.113.9")


class TestRateLimiterBounded(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"RATE_LIMIT_MAX_KEYS": "100"})
        self._env.start()
        rate_limiter._store.clear()
        rate_limiter._windows.clear()
        rate_limiter._last_sweep = 0.0

    def tearDown(self):
        rate_limiter._store.clear()
        rate_limiter._windows.clear()
        self._env.stop()

    def test_store_is_capped(self):
        for i in range(1000):
            rate_limiter._check(f"10.0.{i // 256}.{i % 256}", "login", 10, 60.0)
        self.assertLessEqual(len(rate_limiter._store), 100)

    def test_stale_keys_are_swept(self):
        with mock.patch.object(rate_limiter.time, "time", return_value=1_000_000.0):
            for i in range(50):
                rate_limiter._check(f"192.0.2.{i}", "login", 10, 60.0)
        self.assertEqual(len(rate_limiter._store), 50)
        with mock.patch.object(rate_limiter.time, "time", return_value=1_000_000.0 + 3600):
            rate_limiter._check("198.51.100.1", "login", 10, 60.0)
        self.assertEqual(list(rate_limiter._store.keys()), [("198.51.100.1", "login")])

    def test_limit_still_enforced(self):
        results = [rate_limiter._check("203.0.113.5", "login", 3, 60.0)[0] for _ in range(4)]
        self.assertEqual(results, [True, True, True, False])


class _FakeUser:
    def __init__(self, must_change_password=False, force_password_reset=False):
        self.must_change_password = must_change_password
        self.force_password_reset = force_password_reset


class TestForcePasswordResetEnforced(unittest.TestCase):
    def _pending(self, user):
        fake_db = types.ModuleType("database")
        session = mock.MagicMock()
        fake_db.get_session_local = lambda: (lambda: session)
        with mock.patch.dict(sys.modules, {"database": fake_db}), \
                mock.patch.object(auth, "get_user_by_username", return_value=user):
            return auth._user_still_must_change_password("pro_player")

    def test_force_password_reset_keeps_token_restricted(self):
        self.assertTrue(self._pending(_FakeUser(force_password_reset=True)))

    def test_must_change_password_still_restricted(self):
        self.assertTrue(self._pending(_FakeUser(must_change_password=True)))

    def test_cleared_flags_unrestricted(self):
        self.assertFalse(self._pending(_FakeUser()))

    def test_login_issues_restricted_token_for_force_password_reset(self):
        src = (REPO_ROOT / "api" / "routes" / "auth.py").read_text()
        self.assertIn("if must_change or force_password_reset:", src)


class TestMediaScrapeRequiresAdmin(unittest.TestCase):
    def setUp(self):
        from api.routes import media

        self.media = media
        app = FastAPI()
        app.include_router(media.router)
        self.client = TestClient(app)

    def test_anonymous_rejected(self):
        self.assertEqual(self.client.post("/api/media/scrape").status_code, 401)

    def test_non_admin_rejected(self):
        for role in ("user", "director", "score_keeper"):
            token = auth.create_access_token(role, subject=f"{role}1")
            r = self.client.post("/api/media/scrape", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(r.status_code, 403, role)

    def test_admin_allowed(self):
        token = auth.create_access_token("admin", subject="admin1")
        with mock.patch.object(self.media, "run_scrape", return_value={"total": 0}), \
                mock.patch.object(self.media, "notify_data_changed"):
            r = self.client.post("/api/media/scrape", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"total": 0})


class TestMaintenanceScriptsNeedDatabaseUrl(unittest.TestCase):
    def test_scripts_fail_fast_without_database_url(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        for name in ("fix_super_admin.py", "reset_super_admin_password.py"):
            script = REPO_ROOT / "scripts" / name
            self.assertNotRegex(script.read_text(), r"postgresql://[^<\s'\"]+:[^<\s'\"]+@")
            proc = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(proc.returncode, 0, name)
            self.assertIn("DATABASE_URL", proc.stderr, name)


if __name__ == "__main__":
    unittest.main()
