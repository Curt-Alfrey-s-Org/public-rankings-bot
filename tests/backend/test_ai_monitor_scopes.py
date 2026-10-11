"""AI Monitor website vs internal SQL scopes."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "JWT_SECRET",
    "unit-test-jwt-secret-do-not-use-in-production-0123456789ab",
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.routes import admin as admin_routes


class TestAiMonitorWebsiteFilter(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(admin_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {"role": "admin", "sub": "admin1"}
        self.client = TestClient(app)

    @patch.dict(os.environ, {"AI_MONITOR_WEBSITE_ONLY": "true"}, clear=False)
    @patch("database.get_engine")
    def test_website_query_includes_trust_zone_predicate(self, mock_get_engine) -> None:
        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_engine.return_value.connect.return_value = mock_ctx

        mock_conn.execute.return_value.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value.scalar.return_value = 0

        r = self.client.get("/api/admin/ai-monitor", params={"limit": 10})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body.get("website_only_filter"))

        sql_parts = []
        for c in mock_conn.execute.call_args_list:
            clause = c[0][0] if c[0] else None
            sql_parts.append(getattr(clause, "text", str(clause)))
        joined = " ".join(sql_parts)
        self.assertIn("trust_zone", joined)
        self.assertIn("public_web", joined)
        self.assertIn("app_authenticated", joined)


class TestAiMonitorInternalRequiresSuper(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(admin_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {"role": "super_admin", "sub": "super1"}
        self.client = TestClient(app)

    @patch("database.get_engine")
    def test_internal_uses_complement_predicate(self, mock_get_engine) -> None:
        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_engine.return_value.connect.return_value = mock_ctx
        mock_conn.execute.return_value.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value.scalar.return_value = 0

        r = self.client.get("/api/admin/ai-monitor/internal", params={"limit": 5})
        self.assertEqual(r.status_code, 200, r.text)

        sql_parts = []
        for c in mock_conn.execute.call_args_list:
            clause = c[0][0] if c[0] else None
            sql_parts.append(getattr(clause, "text", str(clause)))
        joined = " ".join(sql_parts)
        self.assertIn("NOT IN", joined)
        self.assertIn("IS NULL", joined)
