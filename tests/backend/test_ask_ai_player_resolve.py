"""Ask AI: extract player names from questions and resolve on /ask."""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault(
    "JWT_SECRET",
    "unit-test-jwt-secret-do-not-use-in-production-0123456789ab",
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.routes import ai_narrative
from api.services.ask_ai_context import extract_player_name_candidates
from api.services.ollama_client import OllamaResponse


class TestExtractPlayerNameCandidates(unittest.TestCase):
    def test_show_stats_for(self) -> None:
        got = extract_player_name_candidates("show stats for Debbie Teichert")
        self.assertIn("Debbie Teichert", got)

    def test_stats_about(self) -> None:
        got = extract_player_name_candidates("stats about Kelly Fisher")
        self.assertIn("Kelly Fisher", got)

    def test_possessive(self) -> None:
        got = extract_player_name_candidates("What is Allison Fisher's rating?")
        self.assertTrue(any("Allison Fisher" in n for n in got))

    def test_tier_question_no_player(self) -> None:
        got = extract_player_name_candidates("What does PRO include?")
        self.assertEqual(got, [])


class TestAskResolvesPlayerFromQuestion(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(ai_narrative.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "admin",
            "sub": "Bama",
        }
        self.client = TestClient(app)

    @patch("api.routes.ai_narrative.is_ollama_enabled", return_value=True)
    @patch("api.routes.ai_narrative.is_litellm_enabled", return_value=False)
    @patch("api.routes.ai_narrative.get_ollama_client")
    @patch("api.routes.ai_narrative.complete_narrative_chat", new_callable=AsyncMock)
    @patch("api.routes.ai_narrative.build_alfa_knowledge_bundle", return_value={"user_tier": "PRO"})
    @patch(
        "api.routes.ai_narrative.build_server_ask_ai_bundle",
        return_value={"resolved_name": "Debbie Teichert", "performance": {"player_name": "Debbie Teichert"}},
    )
    @patch(
        "api.routes.ai_narrative.resolve_player_name_from_question",
        return_value="Debbie Teichert",
    )
    @patch("api.routes.ai_narrative._can_access_player", return_value=True)
    def test_empty_player_name_loads_bundle_from_question(
        self,
        _can,
        mock_resolve,
        mock_bundle,
        _knowledge,
        mock_complete,
        mock_get_ollama,
        _litellm,
        _ollama,
    ) -> None:
        mock_get_ollama.return_value = MagicMock()
        mock_complete.return_value = OllamaResponse(content="Debbie is ranked...", model="m")

        r = self.client.post(
            "/api/ai-narrative/ask",
            json={
                "page": "general",
                "player_name": "",
                "question": "show stats for Debbie Teichert",
                "context": {},
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        mock_resolve.assert_called_once()
        mock_bundle.assert_called_once()
        self.assertEqual(mock_bundle.call_args.args[0], "Debbie Teichert")
        # Ensure LLM saw resolved_from_question in serialized context
        user_msg = mock_complete.call_args.args[0][-1]["content"]
        self.assertIn("resolved_from_question", user_msg)


if __name__ == "__main__":
    unittest.main()
