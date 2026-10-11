"""Fixes from the 2026-09-26 review (round 2). No database server needed."""
import ast
import asyncio
import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-production")

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from api.models.user import User  # noqa: E402
from api.routes import head_to_head, users  # noqa: E402
from api.services.alfa_engine import get_alfa_player  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestRankingHistoryPreference(unittest.TestCase):
    """GET/POST /api/users/preferences/ranking_history_days called PostgresManager methods
    that no longer exist: GET always returned null, POST always returned 500."""

    def setUp(self):
        engine = create_engine("sqlite://")
        User.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(User(username="alice", email="a@example.com", password_hash="x", role="admin",
                         preferences_json=json.dumps({"display_name": "Alice"})))
        self.db.commit()
        self.alice = {"sub": "alice", "role": "admin"}

    def tearDown(self):
        self.db.close()

    def test_default_is_null(self):
        self.assertEqual(users.get_ranking_history_preference(self.alice, self.db)["value"], None)

    def test_set_then_get_keeps_other_preferences(self):
        body = users.UserPreferencesRequest(key="ranking_history_days", value=60)
        self.assertEqual(users.set_ranking_history_preference(body, self.alice, self.db)["value"], 60)
        self.assertEqual(users.get_ranking_history_preference(self.alice, self.db)["value"], 60)
        prefs = json.loads(self.db.query(User).filter_by(username="alice").one().preferences_json)
        self.assertEqual(prefs, {"display_name": "Alice", "ranking_history_days": 60})
        body = users.UserPreferencesRequest(key="ranking_history_days", value=None)
        users.set_ranking_history_preference(body, self.alice, self.db)
        self.assertIsNone(users.get_ranking_history_preference(self.alice, self.db)["value"])

    def test_invalid_value_and_unknown_user(self):
        with self.assertRaises(HTTPException) as ctx:
            users.set_ranking_history_preference(
                users.UserPreferencesRequest(key="ranking_history_days", value=0), self.alice, self.db)
        self.assertEqual(ctx.exception.status_code, 400)
        with self.assertRaises(HTTPException) as ctx:
            users.set_ranking_history_preference(
                users.UserPreferencesRequest(key="ranking_history_days", value=30),
                {"sub": "nobody", "role": "admin"}, self.db)
        self.assertEqual(ctx.exception.status_code, 404)  # was turned into a 500 before

    def test_corrupt_preferences_json_reads_as_empty(self):
        user = self.db.query(User).filter_by(username="alice").one()
        user.preferences_json = "not json"
        self.db.commit()
        self.assertIsNone(users.get_ranking_history_preference(self.alice, self.db)["value"])


class TestHeadToHeadAlfaRating(unittest.TestCase):
    """get_alfa_player() has no include_sandbagger kwarg; the TypeError was swallowed so admins
    never saw ALFa ratings in head-to-head."""

    def test_alfa_rating_is_filled_for_admin(self):
        fake_alfa = mock.create_autospec(get_alfa_player, return_value={"alfa_rating": 1612.5})
        player = {"name": "Jane Doe", "fargo_rating": None}
        conn = mock.MagicMock()
        conn.cursor.return_value.fetchall.return_value = []
        dbm = mock.MagicMock()
        dbm.get_connection.return_value = conn
        with mock.patch.object(head_to_head, "get_alfa_player", fake_alfa), \
                mock.patch.object(head_to_head, "get_database_manager", return_value=dbm), \
                mock.patch.object(head_to_head, "_find_player", side_effect=lambda c, pid: dict(player)):
            result = asyncio.run(head_to_head.get_head_to_head("a", "b", user={"role": "admin"}))
        self.assertEqual(result["operator"]["alfa_rating"], 1612.5)
        self.assertEqual(result["player2"]["alfa_rating"], 1612.5)


class TestRankingsRefreshNoUnboundLocal(unittest.TestCase):
    """A later 'from database import get_database_manager' inside _run_refresh made the name
    local, so its first use raised UnboundLocalError."""

    def test_run_refresh_does_not_rebind_get_database_manager(self):
        tree = ast.parse((REPO_ROOT / "api" / "routes" / "rankings.py").read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_refresh")
        rebinds = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.ImportFrom)
                   and any((a.asname or a.name) == "get_database_manager" for a in n.names)]
        self.assertEqual(rebinds, [])


class TestSqlalchemyPin(unittest.TestCase):
    """SQLAlchemy 2.1 defaults postgresql:// to psycopg (v3), which is not installed."""

    def test_requirements_cap_sqlalchemy_below_2_1(self):
        for name in ("requirements-api.txt", "requirements.txt"):
            text = (REPO_ROOT / name).read_text()
            line = next(l for l in text.splitlines() if re.match(r"(?i)^sqlalchemy\b", l))
            self.assertIn("<2.1", line, name)


if __name__ == "__main__":
    unittest.main()
