"""Trust-zone boundaries for ALFa AI narrative endpoints."""

from __future__ import annotations

import os

# api.auth requires JWT_SECRET at import time
os.environ.setdefault(
    "JWT_SECRET",
    "unit-test-jwt-secret-do-not-use-in-production-0123456789ab",
)

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.routes import ai_narrative
from api.services.ollama_client import OllamaResponse


class TestDemoAskDoesNotTouchPrivateBundle(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(ai_narrative.router)
        self.client = TestClient(app)

    @patch("api.routes.ai_narrative._apply_demo_rate_limit")
    @patch("api.routes.ai_narrative.apply_ai_narrative_demo_rate_limit")
    @patch("api.routes.ai_narrative.build_server_ask_ai_bundle")
    @patch("api.routes.ai_narrative.is_ollama_enabled", return_value=True)
    @patch("api.routes.ai_narrative.is_litellm_enabled", return_value=False)
    @patch("api.routes.ai_narrative.get_ollama_client")
    @patch("api.routes.ai_narrative.complete_narrative_chat", new_callable=AsyncMock)
    @patch("api.routes.ai_narrative.build_demo_alfa_knowledge_bundle", return_value={})
    def test_demo_never_loads_server_player_bundle(
        self,
        _demo_knowledge,
        mock_complete,
        mock_get_ollama,
        _litellm,
        _ollama,
        mock_server_bundle,
        _rl2,
        _rl1,
    ) -> None:
        mock_server_bundle.side_effect = AssertionError(
            "build_server_ask_ai_bundle must not run for public demo-ask"
        )
        mock_get_ollama.return_value = MagicMock()
        mock_complete.return_value = OllamaResponse(content="ok", model="m")

        r = self.client.post(
            "/api/ai-narrative/demo-ask",
            json={"question": "What is USPBF?"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        mock_server_bundle.assert_not_called()
        mock_complete.assert_called_once()
        self.assertEqual(
            mock_complete.call_args.kwargs.get("trust_zone"),
            "public_web",
        )


class TestAskUsesAppTrustZone(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(ai_narrative.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "user",
            "sub": "u1",
        }
        self.client = TestClient(app)

    @patch("api.routes.ai_narrative._can_access_player", return_value=True)
    @patch("api.routes.ai_narrative.is_ollama_enabled", return_value=True)
    @patch("api.routes.ai_narrative.is_litellm_enabled", return_value=False)
    @patch("api.routes.ai_narrative.get_ollama_client")
    @patch("api.routes.ai_narrative.complete_narrative_chat", new_callable=AsyncMock)
    @patch("api.routes.ai_narrative.build_alfa_knowledge_bundle", return_value={})
    @patch("api.routes.ai_narrative.build_server_ask_ai_bundle", return_value={"player": "x"})
    def test_ask_uses_app_trust_zone(
        self,
        _server,
        _alfa,
        mock_complete,
        mock_get_ollama,
        _litellm,
        _ollama,
        _can,
    ) -> None:
        mock_get_ollama.return_value = MagicMock()
        mock_complete.return_value = OllamaResponse(content="hi", model="m")

        r = self.client.post(
            "/api/ai-narrative/ask",
            json={
                "page": "general",
                "player_name": "Test Player",
                "question": "Summary?",
                "context": {},
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        mock_complete.assert_called_once()
        self.assertEqual(
            mock_complete.call_args.kwargs.get("trust_zone"),
            "app_authenticated",
        )


class TestDemoRateLimitRedisFree(unittest.TestCase):
    @patch.dict("os.environ", {"REDIS_URL": ""}, clear=False)
    @patch("api.rate_limiter.check_demo_ask_sliding", return_value=(False, 30.0))
    def test_apply_raises_429_when_sliding_denies(self, _sliding) -> None:
        from fastapi import HTTPException

        from api.services.ai_demo_rate_limit import apply_ai_narrative_demo_rate_limit

        with self.assertRaises(HTTPException) as ctx:
            apply_ai_narrative_demo_rate_limit("192.0.2.1")
        self.assertEqual(ctx.exception.status_code, 429)
