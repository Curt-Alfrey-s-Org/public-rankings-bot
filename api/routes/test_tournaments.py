"""
Test Tournament API Routes
==========================

Isolated test tournament endpoints that don't interfere with live tournament data.
Used for testing tournament functionality with real player data.

Endpoints:
- GET /api/test-tournaments/current - Get current test tournament
- GET /api/test-tournaments/matches - Get test tournament matches
- GET /api/test-tournaments/leaderboard - Get test tournament leaderboard
- POST /api/test-tournaments/simulate-match - Simulate a test match
- POST /api/test-tournaments/clone-production-to-test-center - Mirror prod stats into Test Center DB (read-only prod)
"""

import json
import logging
import math
import os
import random
import re
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database import get_engine, get_test_center_engine
from database.postgres_manager import PostgresManager
from api.services import bracket_engine
from api.auth import require_admin_or_super_admin, require_director_or_admin
from api.models.tournament_models import MatchScoreUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

class TestTournamentManager:
    """Manages test tournament data in persistent database tables"""

    def __init__(self):
        # Dedicated Test Center DB when TEST_CENTER_DATABASE_URL is set (see docs/ENV_VARS.md).
        self.db = PostgresManager(engine=get_test_center_engine())
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure test tournament tables exist in database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            # Check if tables exist, create if not
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'test_tournaments'
                )
            """)
            if not cursor.fetchone()[0]:
                # Tables don't exist, create them
                _app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                _schema_path = os.path.join(_app_root, "database", "schema_postgres.sql")
                with open(_schema_path, "r") as f:
                    schema = f.read()

                # Extract test tournament table creation SQL
                test_tables_sql = ""
                in_test_section = False
                for line in schema.split('\n'):
                    if "-- TEST TOURNAMENT TABLES" in line:
                        in_test_section = True
                    elif in_test_section and line.strip().startswith("-- ") and "TEST TOURNAMENT" not in line:
                        break
                    elif in_test_section:
                        test_tables_sql += line + "\n"

                if test_tables_sql:
                    cursor.execute(test_tables_sql)
                    conn.commit()
            else:
                # Table exists; ensure columns exist
                extra_cols = [
                    ("ranking_system", "VARCHAR(32)"),
                    ("game_type", "VARCHAR(64)"),
                    ("association", "VARCHAR(64)"),
                    ("bracket_template_id", "INTEGER"),
                    ("bracket_draw_size", "INTEGER"),
                    ("bye_strategy", "VARCHAR(32)"),
                    ("end_date", "TIMESTAMP"),
                    ("points_structure", "TEXT"),
                    ("race_to_final", "INTEGER DEFAULT 10"),
                    ("seeding_history", "TEXT"),
                ]
                for col, typ in extra_cols:
                    try:
                        cursor.execute(
                            f"ALTER TABLE test_tournaments ADD COLUMN IF NOT EXISTS {col} {typ}"
                        )
                        conn.commit()
                    except Exception as e:
                        logger.debug("Column %s may already exist: %s", col, e)
                        conn.rollback()
        finally:
            conn.close()

    def _row_to_dict(self, cursor: Any, row: Any) -> Optional[Dict[str, Any]]:
        """Convert a DB-API row into a dict (handles tuple or mapping rows)."""
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {k: row[k] for k in row.keys()}
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    def _rows_to_dicts(self, cursor: Any, rows: List[Any]) -> List[Dict[str, Any]]:
        """Convert a list of DB-API rows into dicts."""
        return [self._row_to_dict(cursor, row) for row in rows if row is not None]

    # Default player data is now handled in setup_test_tournament endpoint

    def get_current_tournament(self) -> Optional[Dict[str, Any]]:
        """Get current test tournament data from database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT tournament_id, name, format, max_players, entry_fee, prize_pool,
                       tables, race_to, race_to_final, status, location, start_date, end_date, notes,
                       ranking_system, game_type, association, bracket_template_id,
                       bracket_draw_size, bye_strategy, points_structure, seeding_history,
                       created_at, updated_at
                FROM test_tournaments
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                d = self._row_to_dict(cursor, row)
                ps = d.get("points_structure")
                if isinstance(ps, str) and ps.strip():
                    try:
                        d["points_structure"] = json.loads(ps)
                    except json.JSONDecodeError:
                        pass
                return d
            return None
        finally:
            conn.close()

    def get_registered_players(self, tournament_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get registered players for test tournament from database"""
        if not tournament_id:
            # Get from latest tournament
            current = self.get_current_tournament()
            if not current:
                return []
            tournament_id = current['tournament_id']

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT player_id, first_name, last_name, nickname, fargo_rating,
                       current_rating, country, status, seed, registered_at
                FROM test_tournament_players
                WHERE tournament_id = %s
                ORDER BY registered_at ASC
            """, (tournament_id,))
            players = self._rows_to_dicts(cursor, cursor.fetchall())

            # Construct full name from first_name and last_name
            for player in players:
                first_name = player.get('first_name', '').strip()
                last_name = player.get('last_name', '').strip()
                if first_name and last_name:
                    # Treat old "Player 17" placeholders as blank
                    if first_name == 'Player' and last_name.isdigit():
                        player['name'] = ''
                    else:
                        player['name'] = f"{first_name} {last_name}"
                elif first_name:
                    player['name'] = first_name
                elif last_name:
                    player['name'] = last_name
                else:
                    player['name'] = ''

            # Enrich with license, total_points, rank from latest rankings when available
            try:
                names = [p['name'] for p in players if (p.get('name') or '').strip()]
                if names:
                    placeholders = ','.join(['%s'] * len(names))
                    cursor.execute(
                        """
                        SELECT DISTINCT ON (name) name, rank, points, license_number
                        FROM mv_latest_rankings
                        WHERE name IN (""" + placeholders + """)
                        ORDER BY name, ranking_system
                        """,
                        names,
                    )
                    rows = cursor.fetchall()
                    colnames = [c[0] for c in cursor.description]
                    by_name = {}
                    for row in rows:
                        d = dict(zip(colnames, row))
                        by_name[d['name']] = {
                            'license_number': d.get('license_number'),
                            'total_points': float(d['points']) if d.get('points') is not None else None,
                            'rank': d.get('rank'),
                        }
                    for player in players:
                        extra = by_name.get(player['name'], {})
                        player['license_number'] = extra.get('license_number')
                        player['total_points'] = extra.get('total_points')
                        player['rank'] = extra.get('rank')
            except Exception as e:
                logger.debug("Could not enrich test players with rankings data: %s", e)
            for player in players:
                player.setdefault('license_number', None)
                player.setdefault('total_points', None)
                player.setdefault('rank', None)

            return players
        finally:
            conn.close()

    def update_player_name(self, player_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Update a registered player's display name in the current test tournament."""
        current = self.get_current_tournament()
        if not current:
            return None
        tournament_id = current['tournament_id']
        name = (name or '').strip()
        parts = name.split(None, 1) if name else []
        first_name = parts[0] if parts else ''
        last_name = parts[1] if len(parts) > 1 else ''
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE test_tournament_players
                SET first_name = %s, last_name = %s
                WHERE tournament_id = %s AND player_id = %s
            """, (first_name, last_name, tournament_id, player_id))
            conn.commit()
            if cursor.rowcount == 0:
                return None
            cursor.execute("""
                SELECT player_id, first_name, last_name, nickname, fargo_rating,
                       current_rating, country, status, seed, registered_at
                FROM test_tournament_players
                WHERE tournament_id = %s AND player_id = %s
            """, (tournament_id, player_id))
            row = cursor.fetchone()
            if not row:
                return None
            player = self._rows_to_dicts(cursor, [row])[0]
            first_name = player.get('first_name', '').strip()
            last_name = player.get('last_name', '').strip()
            player['name'] = f"{first_name} {last_name}".strip() or name
            return player
        finally:
            conn.close()

    def _get_top_players_from_rankings(self, ranking_system: str, limit: int) -> List[Dict[str, Any]]:
        """Get top players from mv_latest_rankings for the given ranking system."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT name, rank, points, license_number, fargo_rating, country
                FROM mv_latest_rankings
                WHERE ranking_system = %s
                ORDER BY rank ASC
                LIMIT %s
            """, (ranking_system, limit))
            rows = cursor.fetchall()
            colnames = [c[0] for c in cursor.description]
            return [dict(zip(colnames, row)) for row in rows]
        except Exception as e:
            logger.debug("Could not load rankings for %s: %s", ranking_system, e)
            return []
        finally:
            conn.close()

    def auto_fill_players(self) -> int:
        """Add top players until tournament is full. Uses tournament's ranking_system if set, else default list."""
        current = self.get_current_tournament()
        if not current:
            return 0
        tournament_id = current['tournament_id']
        max_players = int(current.get('max_players') or 64)
        existing = self.get_registered_players(tournament_id)
        existing_ids = {p['player_id'] for p in existing}
        needed = max(0, max_players - len(existing_ids))
        if needed == 0:
            return 0

        ranking_system = (current.get('ranking_system') or '').strip()
        # WPBA tournaments: always pull real names from production (read-only) and
        # prefix with 'test ' so no hard-coded / un-prefixed rows ever appear.
        if ranking_system.upper().startswith("WPBA"):
            result = self.import_wpba_players_from_production(limit=needed)
            return int(result.get("copied") or 0)

        if ranking_system:
            # Pull top players from this ranking system
            rows = self._get_top_players_from_rankings(ranking_system, limit=max(needed, 128))
            pool = []
            for r in rows:
                name = (r.get('name') or '').strip()
                if not name:
                    continue
                pool.append({
                    'player_id': name,
                    'name': name,
                    'fargo_rating': r.get('fargo_rating'),
                    'current_rating': 1500.0,
                    'country': r.get('country'),
                })
        else:
            pool = []

        if not pool:
            pool = self._get_default_players()

        added = 0
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            for player in pool:
                if added >= needed:
                    break
                pid = player.get('player_id') or player.get('name') or ''
                if pid in existing_ids:
                    continue
                first_name = (player.get('name') or '').split()[0] if player.get('name') else ''
                last_name = ' '.join((player.get('name') or '').split()[1:]) if player.get('name') and len((player.get('name') or '').split()) > 1 else ''
                cursor.execute("""
                    INSERT INTO test_tournament_players
                    (tournament_id, player_id, first_name, last_name, fargo_rating, current_rating, country)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tournament_id, player_id) DO NOTHING
                """, (
                    tournament_id,
                    pid,
                    first_name,
                    last_name,
                    player.get('fargo_rating'),
                    player.get('current_rating', 1500.0),
                    player.get('country'),
                ))
                if cursor.rowcount:
                    added += 1
                    existing_ids.add(pid)
            conn.commit()
        finally:
            conn.close()
        return added

    def clear_registration(self) -> int:
        """Remove all players from the current test tournament. Returns number removed."""
        current = self.get_current_tournament()
        if not current:
            return 0
        tournament_id = current['tournament_id']
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM test_tournament_players WHERE tournament_id = %s",
                (tournament_id,),
            )
            removed = cursor.rowcount
            conn.commit()
            return removed
        finally:
            conn.close()

    def _assert_prod_is_not_test(self) -> None:
        """Refuse to 'copy from production' when prod and test engines point at the same database."""
        prod_url = str(get_engine().url)
        test_url = str(get_test_center_engine().url)
        if prod_url == test_url:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Refusing to import players from production: DATABASE_URL and "
                    "TEST_CENTER_DATABASE_URL resolve to the same database. Configure "
                    "a separate Test Center database before using this endpoint."
                ),
            )

    @staticmethod
    def _prefix_first_name(raw: str) -> str:
        """Prepend 'test ' to first_name if not already prefixed (idempotent)."""
        s = (raw or "").strip()
        if not s:
            return "test"
        if s.lower().startswith("test "):
            return s
        return f"test {s}"

    @staticmethod
    def _slugify_name(name: str) -> str:
        s = (name or "").strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s or "player"

    def import_wpba_players_from_production(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Copy real WPBA player names from the production DB into the current test
        tournament's player roster, prefixing first_name with 'test ' so every
        inserted row is visibly a test row.

        Reads (SELECT only) from the production engine (DATABASE_URL) and writes
        exclusively to the Test Center engine (TEST_CENTER_DATABASE_URL).
        """
        current = self.get_current_tournament()
        if not current:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        tournament_id = current["tournament_id"]
        cap = int(limit or current.get("max_players") or 64)
        if cap <= 0:
            cap = 64

        self._assert_prod_is_not_test()

        prod_engine = get_engine()
        rows: List[Dict[str, Any]] = []
        try:
            # READ-ONLY: the only statement executed against the production engine in this method.
            with prod_engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                        SELECT DISTINCT ON (lower(name))
                            name, country, fargo_rating, license_number, rank
                        FROM mv_latest_rankings
                        WHERE ranking_system ILIKE 'WPBA%'
                          AND name IS NOT NULL
                          AND length(trim(name)) > 0
                        ORDER BY lower(name), rank ASC NULLS LAST
                        """
                    )
                )
                colnames = list(result.keys())
                for row in result.fetchall():
                    rows.append(dict(zip(colnames, row)))
        except Exception as exc:
            logger.error("Test Center: failed reading WPBA players from production: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read WPBA players from production: {exc}",
            )

        # Sort by rank asc so the best-ranked players come first, then cap.
        rows.sort(key=lambda r: (r.get("rank") is None, r.get("rank") or 10**9))
        rows = rows[:cap]

        copied = 0
        skipped = 0
        # WRITE path: test engine only.
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            seen_names: set = set()
            for r in rows:
                raw_name = (r.get("name") or "").strip()
                if not raw_name:
                    continue
                parts = raw_name.split(None, 1)
                first_raw = parts[0] if parts else ""
                last_raw = parts[1] if len(parts) > 1 else ""
                first_name = self._prefix_first_name(first_raw)
                last_name = (last_raw or "").strip()

                dedupe_key = (first_name.lower(), last_name.lower())
                if dedupe_key in seen_names:
                    skipped += 1
                    continue
                seen_names.add(dedupe_key)

                player_id = f"test_{self._slugify_name(raw_name)}"
                country = (r.get("country") or "")
                if country:
                    country = str(country)[:3]

                cursor.execute(
                    """
                    INSERT INTO test_tournament_players
                    (tournament_id, player_id, first_name, last_name, fargo_rating,
                     current_rating, country, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'registered')
                    ON CONFLICT (tournament_id, player_id) DO NOTHING
                    """,
                    (
                        tournament_id,
                        player_id,
                        first_name,
                        last_name,
                        r.get("fargo_rating"),
                        1500.0,
                        country or None,
                    ),
                )
                if cursor.rowcount:
                    copied += 1
                else:
                    skipped += 1
            conn.commit()
        finally:
            conn.close()

        return {
            "copied": copied,
            "skipped_duplicates": skipped,
            "limit": cap,
            "source_ranking_system": "WPBA*",
        }

    @staticmethod
    def _prefix_full_display_name(raw: Optional[str]) -> str:
        """Prefix display names with 'test ' for cloned mirror rows (idempotent)."""
        s = (raw or "").strip()
        if not s:
            return ""
        if s.lower().startswith("test "):
            return s
        return f"test {s}"

    @staticmethod
    def _prefix_tournament_list_name(raw: Optional[str]) -> str:
        """Tournament list title in Test Center mirror."""
        s = (raw or "").strip()
        if not s:
            return "[Test Center]"
        return f"[Test Center] {s}"

    @staticmethod
    def _tc_clone_player_id(prod_player_id: Optional[str], fallback_display_name: str) -> str:
        """Stable VARCHAR(32) id for cloned rows in Test Center."""
        if prod_player_id and str(prod_player_id).strip():
            base = f"tc_{str(prod_player_id).strip()}"
        else:
            slug = TestTournamentManager._slugify_name(fallback_display_name)
            base = f"tc_{slug}" if slug else "tc_player"
        return base[:32]

    @staticmethod
    def _rost_split_from_prefixed_display(display_name: str) -> Dict[str, str]:
        """Split 'test First Last' into first_name/last_name like import_wpba."""
        s = (display_name or "").strip()
        rest = s
        if rest.lower().startswith("test "):
            rest = rest[5:].strip()
        parts = rest.split(None, 1)
        first_raw = parts[0] if parts else ""
        last_raw = parts[1] if len(parts) > 1 else ""
        return {
            "first_name": TestTournamentManager._prefix_first_name(first_raw),
            "last_name": (last_raw or "").strip(),
        }

    def _tc_clear_mirror_tables_only(self, cursor: Any) -> None:
        """Remove mirrored prod-like tables only (not test_* bracket workflow)."""
        cursor.execute("DELETE FROM tournament_history")
        cursor.execute("DELETE FROM rankings")
        cursor.execute("DELETE FROM fargo_rating_history")
        cursor.execute("DELETE FROM players")

    def clone_production_to_test_center(
        self,
        *,
        tournament_limit: int = 50,
        fargo_history_limit: int = 20000,
        register_players_for_current_tournament: bool = True,
    ) -> Dict[str, Any]:
        """
        Replace Test Center mirror tables with a read-only clone from production (DATABASE_URL).
        All player-facing names are prefixed with 'test '; tournament titles get '[Test Center] '.
        Writes only to TEST_CENTER_DATABASE_URL. Requires current test tournament if registering roster.
        """
        current = self.get_current_tournament()
        if not current:
            raise HTTPException(status_code=400, detail="No test tournament set up")

        self._assert_prod_is_not_test()
        tournament_limit = max(1, min(int(tournament_limit), 500))
        fargo_history_limit = max(0, min(int(fargo_history_limit), 500000))

        prod_engine = get_engine()

        def _table_exists(conn: Any, relname: str) -> bool:
            row = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema = 'public' AND table_name = :t
                    )
                    """
                ),
                {"t": relname},
            ).fetchone()
            return bool(row and row[0])

        def _columns(conn: Any, table: str) -> List[str]:
            r = conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :t
                    ORDER BY ordinal_position
                    """
                ),
                {"t": table},
            )
            return [row[0] for row in r.fetchall()]

        # --- Read production (SELECT only) ---
        prod_players: List[Dict[str, Any]] = []
        prod_rankings: List[Dict[str, Any]] = []
        prod_th: List[Dict[str, Any]] = []
        prod_tr: List[Dict[str, Any]] = []
        prod_thm: List[Dict[str, Any]] = []
        prod_frh: List[Dict[str, Any]] = []

        try:
            with prod_engine.connect() as pc:
                if _table_exists(pc, "players"):
                    res = pc.execute(text("SELECT * FROM players"))
                    keys = list(res.keys())
                    for row in res.fetchall():
                        prod_players.append(dict(zip(keys, row)))

                rc = set(_columns(pc, "rankings"))
                rank_sel = [
                    c
                    for c in (
                        "player_name",
                        "ranking_system",
                        "rank",
                        "points",
                        "country",
                        "snapshot_date",
                        "license_number",
                        "fargo_rating",
                        "fargo_last_updated",
                        "stops_played",
                        "position",
                        "source_data",
                        "alfa_rating",
                        "fargo_robustness",
                    )
                    if c in rc
                ]
                if rank_sel:
                    sub = """
                    SELECT """ + ", ".join(rank_sel) + """ FROM rankings r
                    WHERE EXISTS (
                      SELECT 1 FROM (
                        SELECT ranking_system, MAX(snapshot_date) AS md
                        FROM rankings GROUP BY ranking_system
                      ) z
                      WHERE z.ranking_system = r.ranking_system AND z.md = r.snapshot_date
                    )
                    """
                    res = pc.execute(text(sub))
                    keys = list(res.keys())
                    for row in res.fetchall():
                        prod_rankings.append(dict(zip(keys, row)))

                if _table_exists(pc, "tournament_history"):
                    res = pc.execute(
                        text(
                            """
                            SELECT * FROM tournament_history
                            ORDER BY date DESC NULLS LAST, updated_at DESC NULLS LAST
                            LIMIT :lim
                            """
                        ),
                        {"lim": tournament_limit},
                    )
                    keys = list(res.keys())
                    for row in res.fetchall():
                        prod_th.append(dict(zip(keys, row)))

                    ids = [str(r.get("tournament_id")) for r in prod_th if r.get("tournament_id")]
                    if ids:
                        # PostgreSQL native IN-list pattern used throughout this repo
                        # (database/postgres_manager.py): single bind, scalar array, no
                        # SQLAlchemy expanding-bindparam edge cases.
                        ids = list(dict.fromkeys(ids))
                        res = pc.execute(
                            text(
                                "SELECT * FROM tournament_results "
                                "WHERE tournament_id = ANY(:ids)"
                            ),
                            {"ids": ids},
                        )
                        keys = list(res.keys())
                        for row in res.fetchall():
                            prod_tr.append(dict(zip(keys, row)))

                        res = pc.execute(
                            text(
                                "SELECT * FROM tournament_history_matches "
                                "WHERE tournament_id = ANY(:ids)"
                            ),
                            {"ids": ids},
                        )
                        keys = list(res.keys())
                        for row in res.fetchall():
                            prod_thm.append(dict(zip(keys, row)))

                if fargo_history_limit > 0 and _table_exists(pc, "fargo_rating_history"):
                    res = pc.execute(
                        text(
                            """
                            SELECT * FROM fargo_rating_history
                            ORDER BY id DESC
                            LIMIT :lim
                            """
                        ),
                        {"lim": fargo_history_limit},
                    )
                    keys = list(res.keys())
                    for row in res.fetchall():
                        prod_frh.append(dict(zip(keys, row)))
        except Exception as exc:
            logger.exception("Test Center: clone read from production failed: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read from production database (read-only): {exc}",
            )

        # --- Write Test Center ---
        tc_conn = self.db.get_connection()
        cur = tc_conn.cursor()
        roster_registered = 0

        try:
            self._tc_clear_mirror_tables_only(cur)

            # players (mirror)
            players_written = 0
            seen_player_ids: set = set()
            for pr in prod_players:
                if pr.get("player_id"):
                    disp = (
                        f"{(pr.get('first_name') or '').strip()} {(pr.get('last_name') or '').strip()}"
                    ).strip()
                    if not disp:
                        disp = (pr.get("name") or "").strip()
                    pid = self._tc_clone_player_id(str(pr.get("player_id")), disp or "player")
                    if pid in seen_player_ids:
                        continue
                    seen_player_ids.add(pid)
                    fn = self._prefix_first_name(str(pr.get("first_name") or "").strip())
                    ln = str(pr.get("last_name") or "").strip()
                    fargo = pr.get("fargo_score")
                    if fargo is None:
                        fargo = pr.get("fargo_rating")
                    cur.execute(
                        """
                        INSERT INTO players (
                          player_id, first_name, last_name, nickname, email, phone,
                          license_number, avatar_url, fargo_score, nationality, hometown, state,
                          membership_status, hall_of_fame, hot_streak_count,
                          total_tournaments_played, total_points, current_rank
                        ) VALUES (
                          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        )
                        """,
                        (
                            pid,
                            fn or self._prefix_first_name("Unknown"),
                            ln or "",
                            pr.get("nickname"),
                            pr.get("email"),
                            pr.get("phone"),
                            (str(pr.get("license_number"))[:64] if pr.get("license_number") else None),
                            pr.get("avatar_url"),
                            int(fargo) if fargo is not None else None,
                            (str(pr.get("nationality"))[:255] if pr.get("nationality") else None),
                            pr.get("hometown"),
                            pr.get("state"),
                            (pr.get("membership_status") or "active"),
                            int(pr.get("hall_of_fame") or 0),
                            int(pr.get("hot_streak_count") or 0),
                            int(pr.get("total_tournaments_played") or 0),
                            float(pr.get("total_points") or 0.0),
                            int(pr["current_rank"]) if pr.get("current_rank") is not None else None,
                        ),
                    )
                    players_written += 1
                else:
                    raw_name = (pr.get("name") or "").strip()
                    if not raw_name:
                        continue
                    parts = raw_name.split(None, 1)
                    first_raw = parts[0] if parts else ""
                    last_raw = parts[1] if len(parts) > 1 else ""
                    fn = self._prefix_first_name(first_raw)
                    ln = (last_raw or "").strip()
                    pid = self._tc_clone_player_id(
                        str(pr["id"]) if pr.get("id") is not None else None, raw_name
                    )
                    if pid in seen_player_ids:
                        continue
                    seen_player_ids.add(pid)
                    fargo = pr.get("fargo_rating") or pr.get("fargo_score")
                    cur.execute(
                        """
                        INSERT INTO players (
                          player_id, first_name, last_name, license_number, avatar_url,
                          fargo_score, nationality, membership_status, hall_of_fame,
                          hot_streak_count, total_tournaments_played, total_points
                        ) VALUES (
                          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        )
                        """,
                        (
                            pid,
                            fn,
                            ln,
                            None,
                            None,
                            int(fargo) if fargo is not None else None,
                            (str(pr.get("nationality"))[:255] if pr.get("nationality") else None),
                            "active",
                            0,
                            0,
                            0,
                            0.0,
                        ),
                    )
                    players_written += 1

            # rankings
            rankings_written = 0
            seen_rank_keys: set = set()
            for rr in prod_rankings:
                pname = self._prefix_full_display_name(str(rr.get("player_name") or "").strip())
                if not pname:
                    continue
                rs = str(rr.get("ranking_system") or "").strip() or "WPBA"
                snap = rr.get("snapshot_date")
                rk_key = (pname, rs, str(snap))
                if rk_key in seen_rank_keys:
                    continue
                seen_rank_keys.add(rk_key)
                sd_raw = rr.get("source_data")
                if sd_raw is None:
                    sd_json = "{}"
                elif isinstance(sd_raw, (dict, list)):
                    sd_json = json.dumps(sd_raw, default=str)
                else:
                    sd_json = str(sd_raw)
                cur.execute(
                    """
                    INSERT INTO rankings (
                      player_name, ranking_system, rank, points, country, snapshot_date,
                      license_number, fargo_rating, fargo_last_updated, stops_played, position,
                      source_data, alfa_rating, fargo_robustness
                    ) VALUES (
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s
                    )
                    """,
                    (
                        pname,
                        str(rr.get("ranking_system") or "").strip() or "WPBA",
                        int(rr.get("rank") or 0),
                        float(rr.get("points") or 0.0),
                        rr.get("country"),
                        rr.get("snapshot_date"),
                        rr.get("license_number"),
                        rr.get("fargo_rating"),
                        rr.get("fargo_last_updated"),
                        int(rr.get("stops_played") or 0),
                        rr.get("position"),
                        sd_json,
                        rr.get("alfa_rating"),
                        rr.get("fargo_robustness"),
                    ),
                )
                rankings_written += 1

            # tournament_history / results / matches
            th_written = 0
            seen_th_id: set = set()
            for th in prod_th:
                tid = str(th.get("tournament_id") or "").strip()
                if not tid:
                    continue
                if tid in seen_th_id:
                    continue
                seen_th_id.add(tid)
                cur.execute(
                    """
                    INSERT INTO tournament_history (
                      tournament_id, name, date, location, year, association, championship,
                      champion, runner_up, final_score, status, prize_pool, source_url, bracket_url
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        tid,
                        self._prefix_tournament_list_name(str(th.get("name") or "").strip()),
                        th.get("date"),
                        th.get("location"),
                        th.get("year"),
                        th.get("association"),
                        th.get("championship"),
                        self._prefix_full_display_name(th.get("champion")),
                        self._prefix_full_display_name(th.get("runner_up")),
                        th.get("final_score"),
                        th.get("status") or "completed",
                        th.get("prize_pool"),
                        th.get("source_url"),
                        th.get("bracket_url"),
                    ),
                )
                th_written += 1

            tr_written = 0
            seen_tr: set = set()
            for tr in prod_tr:
                tid = str(tr.get("tournament_id") or "").strip()
                pname = self._prefix_full_display_name(str(tr.get("player_name") or "").strip())
                if not tid or not pname:
                    continue
                trk = (tid, pname)
                if trk in seen_tr:
                    continue
                seen_tr.add(trk)
                stops = tr.get("stops_played")
                stops_val = int(stops) if stops is not None else None
                cur.execute(
                    """
                    INSERT INTO tournament_results (
                      tournament_id, player_name, placement, points,
                      fargo_rating_at_scrape, stops_played, notes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        tid,
                        pname,
                        tr.get("placement"),
                        float(tr.get("points") or 0.0),
                        tr.get("fargo_rating_at_scrape"),
                        stops_val,
                        tr.get("notes"),
                    ),
                )
                tr_written += 1

            thm_written = 0
            seen_thm: set = set()
            for m in prod_thm:
                tid = str(m.get("tournament_id") or "").strip()
                if not tid:
                    continue
                p1 = self._prefix_full_display_name(str(m.get("operator_name") or "").strip())
                p2 = self._prefix_full_display_name(str(m.get("player2_name") or "").strip())
                wn = self._prefix_full_display_name(str(m.get("winner_name") or "").strip())
                if not p1:
                    p1 = "test TBD"
                if not p2:
                    p2 = "test TBD"
                mk = (tid, str(m.get("round_num")), m.get("match_num"), p1, p2)
                if mk in seen_thm:
                    continue
                seen_thm.add(mk)
                cur.execute(
                    """
                    INSERT INTO tournament_history_matches (
                      tournament_id, operator_name, player2_name, operator_score, player2_score,
                      winner_name, round_num, match_num, match_date, notes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        tid,
                        p1,
                        p2,
                        m.get("operator_score"),
                        m.get("player2_score"),
                        wn or None,
                        m.get("round_num"),
                        m.get("match_num"),
                        m.get("match_date"),
                        m.get("notes"),
                    ),
                )
                thm_written += 1

            frh_written = 0
            for fh in prod_frh:
                oid = str(fh.get("player_id") or "").strip()
                nid = self._tc_clone_player_id(oid, str(fh.get("player_name") or oid))
                pname = self._prefix_full_display_name(str(fh.get("player_name") or "").strip())
                if not pname:
                    pname = "test Unknown"
                cur.execute(
                    """
                    INSERT INTO fargo_rating_history (
                      player_id, player_name, ranking_system, old_fargo_rating, new_fargo_rating,
                      fargo_source, snapshot_date, archive_reason, confidence_score, data_quality
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        nid[:255],
                        pname,
                        fh.get("ranking_system"),
                        fh.get("old_fargo_rating"),
                        float(fh.get("new_fargo_rating") or 0.0),
                        fh.get("fargo_source"),
                        fh.get("snapshot_date"),
                        fh.get("archive_reason") or "update",
                        float(fh.get("confidence_score") or 0.8),
                        fh.get("data_quality") or "verified",
                    ),
                )
                frh_written += 1

            cur.execute("REFRESH MATERIALIZED VIEW mv_latest_rankings")
            cur.execute("REFRESH MATERIALIZED VIEW mv_tournament_history_recent")

            if register_players_for_current_tournament:
                cap = int(current.get("max_players") or 64)
                tournament_id = current["tournament_id"]
                cur.execute(
                    "DELETE FROM test_tournament_players WHERE tournament_id = %s",
                    (tournament_id,),
                )
                roster_registered = 0
                seen_name_lc: set = set()
                cur.execute(
                    """
                    SELECT r.player_name, r.rank, r.fargo_rating, r.country, r.license_number,
                           p.player_id, p.first_name, p.last_name, p.fargo_score
                    FROM rankings r
                    INNER JOIN players p
                      ON trim(both from concat_ws(' ', p.first_name, p.last_name))
                         = trim(both from r.player_name)
                    WHERE r.ranking_system ILIKE 'WPBA%%'
                      AND EXISTS (
                        SELECT 1 FROM (
                          SELECT ranking_system, MAX(snapshot_date) AS md
                          FROM rankings GROUP BY ranking_system
                        ) z
                        WHERE z.ranking_system = r.ranking_system AND z.md = r.snapshot_date
                      )
                    ORDER BY r.rank ASC NULLS LAST
                    LIMIT %s
                    """,
                    (cap,),
                )
                roster_rows = cur.fetchall()
                seen_pid: set = set()
                for row in roster_rows:
                    (
                        player_name,
                        _rk,
                        fr_rank,
                        country,
                        lic,
                        pid,
                        fn,
                        ln,
                        fargo_sc,
                    ) = row
                    key = str(pid).lower()
                    if key in seen_pid:
                        continue
                    seen_pid.add(key)
                    pn_lc = str(player_name or "").strip().lower()
                    if pn_lc:
                        seen_name_lc.add(pn_lc)
                    fn_s = (fn or "").strip()
                    ln_s = (ln or "").strip()
                    if not fn_s:
                        spl = self._rost_split_from_prefixed_display(str(player_name or ""))
                        fn_s = spl["first_name"]
                        ln_s = spl["last_name"]
                    fr = fr_rank if fr_rank is not None else fargo_sc
                    cur.execute(
                        """
                        INSERT INTO test_tournament_players
                        (tournament_id, player_id, first_name, last_name, fargo_rating,
                         current_rating, country, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'registered')
                        ON CONFLICT (tournament_id, player_id) DO NOTHING
                        """,
                        (
                            tournament_id,
                            str(pid)[:255],
                            fn_s,
                            ln_s,
                            int(fr) if fr is not None else None,
                            1500.0,
                            (str(country)[:3] if country else None),
                        ),
                    )
                    roster_registered += cur.rowcount

                # Fallback: fill remaining slots from WPBA ranking rows even when mirror
                # players row is missing (name mismatch between prod.players vs prod.rankings).
                if roster_registered < cap:
                    cur.execute(
                        """
                        SELECT r.player_name, r.rank, r.fargo_rating, r.country, r.license_number
                        FROM rankings r
                        WHERE r.ranking_system ILIKE 'WPBA%%'
                          AND EXISTS (
                            SELECT 1 FROM (
                              SELECT ranking_system, MAX(snapshot_date) AS md
                              FROM rankings GROUP BY ranking_system
                            ) z
                            WHERE z.ranking_system = r.ranking_system AND z.md = r.snapshot_date
                          )
                        ORDER BY r.rank ASC NULLS LAST
                        LIMIT 512
                        """
                    )
                    for row2 in cur.fetchall():
                        if roster_registered >= cap:
                            break
                        player_name2, _rk2, fr2, country2, lic2 = row2
                        pn_lc = str(player_name2 or "").strip().lower()
                        if not pn_lc or pn_lc in seen_name_lc:
                            continue
                        seen_name_lc.add(pn_lc)
                        spl = self._rost_split_from_prefixed_display(str(player_name2 or ""))
                        raw_disp = str(player_name2 or "").strip()
                        slug_src = raw_disp[5:].strip() if raw_disp.lower().startswith("test ") else raw_disp
                        pid2 = self._tc_clone_player_id(None, slug_src or raw_disp)[:255]
                        cur.execute(
                            """
                            INSERT INTO test_tournament_players
                            (tournament_id, player_id, first_name, last_name, fargo_rating,
                             current_rating, country, status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,'registered')
                            ON CONFLICT (tournament_id, player_id) DO NOTHING
                            """,
                            (
                                tournament_id,
                                pid2,
                                spl["first_name"],
                                spl["last_name"],
                                int(fr2) if fr2 is not None else None,
                                1500.0,
                                (str(country2)[:3] if country2 else None),
                            ),
                        )
                        roster_registered += cur.rowcount

            tc_conn.commit()
        except Exception:
            tc_conn.rollback()
            raise
        finally:
            tc_conn.close()

        return {
            "players_copied": players_written,
            "rankings_copied": rankings_written,
            "tournaments_copied": th_written,
            "tournament_results_copied": tr_written,
            "tournament_matches_copied": thm_written,
            "fargo_rating_history_copied": frh_written,
            "test_tournament_players_registered": roster_registered,
            "tournament_limit": tournament_limit,
            "fargo_history_limit": fargo_history_limit,
        }

    def seed_classics_demo_players(self) -> int:
        """
        Replace registration with 64 named demo players (seeds 1-32, remainder unseeded).
        For WPBA Classics-style double-elimination Test Center runs.
        """
        current = self.get_current_tournament()
        if not current:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        tournament_id = current["tournament_id"]
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM test_tournament_players WHERE tournament_id = %s",
                (tournament_id,),
            )
            for i in range(1, 65):
                player_id = f"classics_{i:03d}"
                cursor.execute(
                    """
                    INSERT INTO test_tournament_players
                    (tournament_id, player_id, first_name, last_name, seed, country, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'registered')
                    """,
                    (
                        tournament_id,
                        player_id,
                        "Demo",
                        f"Player {i:02d}",
                        i if i <= 32 else None,
                        "USA",
                    ),
                )
            conn.commit()
            return 64
        finally:
            conn.close()

    def get_matches(self, tournament_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get test tournament matches from database"""
        if not tournament_id:
            # Get from latest tournament
            current = self.get_current_tournament()
            if not current:
                return []
            tournament_id = current['tournament_id']

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT match_id, tournament_id, bracket_type, round_number,
                       operator_id, player2_id, operator_name, player2_name,
                       operator_score, player2_score, winner_id, status,
                       table_number, scheduled_time, race_to, handicap1, handicap2, notes
                FROM test_tournament_matches
                WHERE tournament_id = %s
                ORDER BY CASE bracket_type
                    WHEN 'winners' THEN 1
                    WHEN 'losers' THEN 2
                    WHEN 'grand_final' THEN 3
                    ELSE 4
                END,
                round_number ASC,
                match_id ASC
            """, (tournament_id,))
            return self._rows_to_dicts(cursor, cursor.fetchall())
        finally:
            conn.close()

    def _finishing_rank_by_record(
        self, players: List[Dict[str, Any]], matches: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Order: fewer losses first, then more wins, then more racks won (test tournament standings)."""
        stats: Dict[str, Dict[str, Any]] = {}
        for p in players:
            pid = str(p["player_id"])
            stats[pid] = {"wins": 0, "losses": 0, "racks_won": 0, "racks_lost": 0}
        for match in matches:
            if match.get("status") != "completed":
                continue
            wid = match.get("winner_id")
            for side, oid, oname in (
                (1, match.get("operator_id"), match.get("operator_name")),
                (2, match.get("player2_id"), match.get("player2_name")),
            ):
                if not oid or (oname or "").strip() in ("BYE", "TBD", ""):
                    continue
                oid_s = str(oid)
                if oid_s not in stats:
                    stats[oid_s] = {"wins": 0, "losses": 0, "racks_won": 0, "racks_lost": 0}
                sc1 = match.get("operator_score") or 0
                sc2 = match.get("player2_score") or 0
                if wid == oid:
                    stats[oid_s]["wins"] += 1
                    stats[oid_s]["racks_won"] += sc1 if side == 1 else sc2
                    stats[oid_s]["racks_lost"] += sc2 if side == 1 else sc1
                else:
                    stats[oid_s]["losses"] += 1
                    stats[oid_s]["racks_won"] += sc1 if side == 1 else sc2
                    stats[oid_s]["racks_lost"] += sc2 if side == 1 else sc1

        ordered = sorted(
            stats.keys(),
            key=lambda pid: (
                stats[pid]["losses"],
                -stats[pid]["wins"],
                -stats[pid]["racks_won"],
            ),
        )
        return {pid: i + 1 for i, pid in enumerate(ordered)}

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get test tournament leaderboard with finishing rank and WPBA-style R-points (when completed)."""
        tournament = self.get_current_tournament()
        players = self.get_registered_players()
        matches = self.get_matches()

        rank_by_id: Dict[str, int] = {}
        if tournament and tournament.get("status") == "completed" and matches:
            rank_by_id = self._finishing_rank_by_record(players, matches)

        leaderboard = []
        for player in players:
            wins = 0
            losses = 0
            total_racks_won = 0
            total_racks_lost = 0

            for match in matches:
                if match["status"] == "completed":
                    if match["winner_id"] == player["player_id"]:
                        wins += 1
                        total_racks_won += match.get(
                            "operator_score"
                            if match["winner_id"] == match["operator_id"]
                            else "player2_score",
                            0,
                        )
                        total_racks_lost += match.get(
                            "player2_score"
                            if match["winner_id"] == match["operator_id"]
                            else "operator_score",
                            0,
                        )
                    elif match["operator_id"] == player["player_id"] or match[
                        "player2_id"
                    ] == player["player_id"]:
                        losses += 1
                        total_racks_lost += match.get(
                            "operator_score"
                            if match["operator_id"] == player["player_id"]
                            else "player2_score",
                            0,
                        )
                        total_racks_won += match.get(
                            "player2_score"
                            if match["operator_id"] == player["player_id"]
                            else "operator_score",
                            0,
                        )

            pid = str(player["player_id"])
            fin_rank = rank_by_id.get(pid)
            wpba_pts = None
            if fin_rank is not None:
                wpba_pts = bracket_engine.wpba_points_for_placement(fin_rank)
            leaderboard.append(
                {
                    "player_id": player["player_id"],
                    "name": player["name"],
                    "wins": wins,
                    "losses": losses,
                    "racks_won": total_racks_won,
                    "racks_lost": total_racks_lost,
                    "win_percentage": (wins / (wins + losses)) * 100
                    if (wins + losses) > 0
                    else 0,
                    "current_rating": player["current_rating"],
                    "placement": fin_rank,
                    "wpba_r_points": wpba_pts,
                }
            )

        leaderboard.sort(
            key=lambda x: (
                x["placement"] if x["placement"] is not None else 10**6,
                -x["wins"],
                -x["win_percentage"],
                -(float(x["current_rating"] or 0)),
            )
        )

        return leaderboard

    def simulate_match(self, match_id: str, winner_bias: str = "fair") -> Dict[str, Any]:
        """Simulate a test match, advance winner, and mark tournament complete if final."""
        import random

        matches = self.get_matches()
        match = next((m for m in matches if m['match_id'] == match_id), None)

        if not match:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

        if match['status'] == 'completed':
            raise HTTPException(status_code=400, detail=f"Match {match_id} already completed")

        p1n = (match.get('operator_name') or '').strip()
        p2n = (match.get('player2_name') or '').strip()
        if p1n in ('TBD', 'BYE', '') or p2n in ('TBD', 'BYE', ''):
            raise HTTPException(
                status_code=400,
                detail="Match is not ready (missing opponent or TBD slot)",
            )
        if not match.get('operator_id') or not match.get('player2_id'):
            raise HTTPException(status_code=400, detail="Match is not ready (missing player id)")

        current_t = self.get_current_tournament()

        # Re-register draw size and format so advancement_target lookups survive
        # server restarts (bracket_engine stores these in-memory only).
        if current_t:
            bracket_engine.set_tournament_draw_size(
                current_t['tournament_id'],
                int(current_t.get('bracket_draw_size') or 64),
            )
            bracket_engine.set_tournament_format(
                current_t['tournament_id'],
                (current_t.get('format') or 'single_elimination').strip(),
            )

        race_to = int(match.get('race_to') or (current_t or {}).get('race_to') or 9)
        if race_to < 1:
            race_to = 9

        operator_win_prob = 0.5
        if winner_bias == "operator":
            operator_win_prob = 0.7
        elif winner_bias == "player2":
            operator_win_prob = 0.3

        operator_score = 0
        player2_score = 0
        while operator_score < race_to and player2_score < race_to:
            if random.random() < operator_win_prob:
                operator_score += 1
            else:
                player2_score += 1

        winner_id = match['operator_id'] if operator_score >= race_to else match['player2_id']
        return self._apply_match_completion(match, operator_score, player2_score, str(winner_id))

    def update_match_score(
        self,
        match_id: str,
        operator_score: int,
        player2_score: int,
        status: str = "completed",
    ) -> Dict[str, Any]:
        """Director/scorekeeper entry: set scores and advance bracket when complete."""
        matches = self.get_matches()
        match = next((m for m in matches if m['match_id'] == match_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
        if match['status'] == 'completed' and status == 'completed':
            raise HTTPException(status_code=400, detail=f"Match {match_id} already completed")

        p1n = (match.get('operator_name') or '').strip()
        p2n = (match.get('player2_name') or '').strip()
        if p1n in ('TBD', 'BYE', '') or p2n in ('TBD', 'BYE', ''):
            raise HTTPException(status_code=400, detail="Match is not ready (missing opponent or TBD slot)")
        if not match.get('operator_id') or not match.get('player2_id'):
            raise HTTPException(status_code=400, detail="Match is not ready (missing player id)")

        current_t = self.get_current_tournament()
        if current_t:
            bracket_engine.set_tournament_draw_size(
                current_t['tournament_id'],
                int(current_t.get('bracket_draw_size') or 64),
            )
            bracket_engine.set_tournament_format(
                current_t['tournament_id'],
                (current_t.get('format') or 'single_elimination').strip(),
            )

        race_to = int(match.get('race_to') or (current_t or {}).get('race_to') or 9)
        if race_to < 1:
            race_to = 9

        if status == 'completed':
            if operator_score >= race_to and player2_score >= race_to:
                raise HTTPException(status_code=400, detail="Both players cannot reach race to")
            if operator_score >= race_to:
                winner_id = str(match['operator_id'])
            elif player2_score >= race_to:
                winner_id = str(match['player2_id'])
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"At least one player must reach race to ({race_to}) to complete the match",
                )
            return self._apply_match_completion(match, operator_score, player2_score, winner_id)

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE test_tournament_matches
                SET operator_score = %s, player2_score = %s, status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE match_id = %s
                """,
                (operator_score, player2_score, status, match_id),
            )
            conn.commit()
        finally:
            conn.close()
        match['operator_score'] = operator_score
        match['player2_score'] = player2_score
        match['status'] = status
        return match

    def _apply_match_completion(
        self,
        match: Dict[str, Any],
        operator_score: int,
        player2_score: int,
        winner_id: str,
    ) -> Dict[str, Any]:
        match_id = match['match_id']
        winner_name = (
            match['operator_name'] if winner_id == match['operator_id'] else match['player2_name']
        )

        match['operator_score'] = operator_score
        match['player2_score'] = player2_score
        match['winner_id'] = winner_id
        match['status'] = 'completed'

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE test_tournament_matches
                SET operator_score = %s, player2_score = %s, winner_id = %s, status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE match_id = %s
                """,
                (operator_score, player2_score, winner_id, 'completed', match_id),
            )
            self._advance_winner_to_next_round(
                cursor, match['tournament_id'], match_id, winner_id, str(winner_name or '').strip()
            )
            loser_id = match["player2_id"] if winner_id == match["operator_id"] else match["operator_id"]
            loser_name = (
                match["player2_name"] if winner_id == match["operator_id"] else match["operator_name"]
            )
            ln = (loser_name or "").strip()
            if loser_id and ln not in ("BYE", "TBD", ""):
                self._route_loser_to_next_slot(
                    cursor,
                    match["tournament_id"],
                    match_id,
                    str(loser_id),
                    ln,
                )
            self._maybe_mark_tournament_complete(cursor, match['tournament_id'])
            conn.commit()
        finally:
            conn.close()

        try:
            ct = self.get_current_tournament()
            if ct and ct.get("status") == "completed":
                self._persist_completion_to_view_tables(ct.get("tournament_id") or match["tournament_id"])
        except Exception as exc:
            logger.exception("Test Center: failed to persist completion to view tables: %s", exc)

        return match

    def _num_bracket_rounds(self, tournament: Dict[str, Any]) -> int:
        dsize = int(tournament.get('bracket_draw_size') or tournament.get('max_players') or 8)
        dsize = bracket_engine.next_power_of_two(max(2, dsize))
        return int(math.log2(dsize))

    def _advance_winner_to_next_round(
        self,
        cursor: Any,
        tournament_id: str,
        completed_match_id: str,
        winner_id: str,
        winner_name: str,
    ) -> None:
        tgt = bracket_engine.advancement_target_winner(completed_match_id)
        if not tgt:
            return
        next_mid, tid, _nr, _ni, slot = tgt
        if tid != tournament_id:
            return
        bracket_engine.fill_tbd_name_for_advancement(
            cursor, tournament_id, winner_id, winner_name, next_mid, slot
        )
        cursor.execute(
            """
            SELECT operator_name, player2_name, operator_id, player2_id, status
            FROM test_tournament_matches WHERE match_id = %s
            """,
            (next_mid,),
        )
        row = cursor.fetchone()
        if not row:
            return
        n1, n2, id1, id2 = row[0], row[1], row[2], row[3]
        n1s, n2s = (n1 or '').strip(), (n2 or '').strip()
        if (
            id1
            and id2
            and n1s not in ('TBD', 'BYE', '')
            and n2s not in ('TBD', 'BYE', '')
            and row[4] == 'pending'
        ):
            cursor.execute(
                """
                UPDATE test_tournament_matches
                SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE match_id = %s
                """,
                (next_mid,),
            )

    def _route_loser_to_next_slot(
        self,
        cursor: Any,
        tournament_id: str,
        completed_match_id: str,
        loser_id: str,
        loser_name: str,
    ) -> None:
        tgt = bracket_engine.advancement_target_loser(completed_match_id)
        if not tgt:
            return
        next_mid, tid, _nr, _ni, slot = tgt
        if tid != tournament_id:
            return
        bracket_engine.fill_tbd_name_for_advancement(
            cursor, tournament_id, loser_id, loser_name, next_mid, slot
        )

    def _maybe_mark_tournament_complete(self, cursor: Any, tournament_id: str) -> None:
        cursor.execute(
            """
            SELECT COUNT(*) FROM test_tournament_matches
            WHERE tournament_id = %s AND status <> 'completed'
            """,
            (tournament_id,),
        )
        pending = cursor.fetchone()[0]
        if pending == 0:
            cursor.execute(
                """
                UPDATE test_tournaments
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE tournament_id = %s
                """,
                (tournament_id,),
            )

    def _persist_completion_to_view_tables(self, tournament_id: str) -> None:
        """Persist a completed test tournament into standard tables for Test Center view tabs."""
        tournament = self.get_current_tournament()
        if not tournament or str(tournament.get("tournament_id")) != str(tournament_id):
            return
        if tournament.get("status") != "completed":
            return

        lb = self.get_leaderboard()
        if not lb:
            logger.warning("Test Center: no leaderboard rows to persist for %s", tournament_id)
            return

        snap = date.today()
        ranking_system = (tournament.get("ranking_system") or "WPBA_Women").strip()
        assoc = (tournament.get("association") or ranking_system or "WPBA_Women").strip()
        tname = (tournament.get("name") or "Test Tournament").strip()
        display_name = f"[Test Center] {tname}"
        loc = (tournament.get("location") or "").strip() or None
        prize = tournament.get("prize_pool")
        prize_pool_str = str(prize) if prize is not None else None

        ordered = sorted(
            [r for r in lb if r.get("placement") is not None],
            key=lambda x: int(x.get("placement") or 999999),
        )
        champion = None
        runner_up = None
        if len(ordered) >= 1:
            champion = (ordered[0].get("name") or "").strip() or None
        if len(ordered) >= 2:
            runner_up = (ordered[1].get("name") or "").strip() or None

        conn = self.db.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO tournament_history (
                    tournament_id, name, date, year, location, association, championship,
                    champion, runner_up, status, prize_pool, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (tournament_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    date = EXCLUDED.date,
                    year = EXCLUDED.year,
                    location = EXCLUDED.location,
                    association = EXCLUDED.association,
                    champion = EXCLUDED.champion,
                    runner_up = EXCLUDED.runner_up,
                    status = EXCLUDED.status,
                    prize_pool = EXCLUDED.prize_pool,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    tournament_id,
                    display_name,
                    snap,
                    snap.year,
                    loc,
                    assoc,
                    tname,
                    champion,
                    runner_up,
                    prize_pool_str,
                ),
            )

            cur.execute("DELETE FROM tournament_results WHERE tournament_id = %s", (tournament_id,))
            for row in ordered:
                pname = (row.get("name") or "").strip()
                if not pname:
                    continue
                placement = int(row.get("placement") or 0)
                pts = float(row.get("wpba_r_points") or 0)
                cur.execute(
                    """
                    INSERT INTO tournament_results (tournament_id, player_name, placement, points)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                        placement = EXCLUDED.placement,
                        points = EXCLUDED.points
                    """,
                    (tournament_id, pname, placement, pts),
                )

            players = self.get_registered_players()
            for p in players:
                pid = str(p.get("player_id") or "").strip()
                fn = (p.get("first_name") or "").strip() or "Unknown"
                ln = (p.get("last_name") or "").strip() or "Unknown"
                lic = (p.get("license_number") or "").strip() or None
                country = (p.get("country") or "").strip() or None
                fargo = p.get("fargo_rating")
                try:
                    fargo_i = int(float(fargo)) if fargo is not None else None
                except (TypeError, ValueError):
                    fargo_i = None
                if not pid:
                    continue
                cur.execute(
                    """
                    INSERT INTO players (
                        player_id, first_name, last_name, license_number, nationality,
                        fargo_score, membership_status, hall_of_fame, hot_streak_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'active', 0, 0)
                    ON CONFLICT (player_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        license_number = COALESCE(EXCLUDED.license_number, players.license_number),
                        nationality = COALESCE(EXCLUDED.nationality, players.nationality),
                        fargo_score = COALESCE(EXCLUDED.fargo_score, players.fargo_score),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (pid, fn, ln, lic, country, fargo_i),
                )

            cur.execute(
                "DELETE FROM rankings WHERE ranking_system = %s AND snapshot_date = %s",
                (ranking_system, snap),
            )
            for row in ordered:
                pname = (row.get("name") or "").strip()
                if not pname:
                    continue
                placement = int(row.get("placement") or 0)
                pts = float(row.get("wpba_r_points") or 0)
                cur.execute(
                    """
                    INSERT INTO rankings (
                        player_name, ranking_system, rank, points, country, snapshot_date,
                        license_number, fargo_rating, stops_played, position, source_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        pname,
                        ranking_system,
                        placement,
                        pts,
                        None,
                        snap,
                        None,
                        None,
                        1,
                        placement,
                        "{}",
                    ),
                )

            try:
                cur.execute("REFRESH MATERIALIZED VIEW mv_latest_rankings")
                cur.execute("REFRESH MATERIALIZED VIEW mv_tournament_history_recent")
            except Exception as exc:
                logger.warning(
                    "Test Center: materialized view refresh failed (data still persisted): %s",
                    exc,
                )
            conn.commit()
            logger.info(
                "Test Center: persisted completed tournament %s to view tables (ranking_system=%s)",
                tournament_id,
                ranking_system,
            )
        finally:
            conn.close()

    def reset_all_test_data(self) -> Dict[str, int]:
        """Delete all rows from test tournament tables and mirrored view tables (same Test Center DB)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tournament_results")
            tr = cursor.rowcount
            cursor.execute("DELETE FROM tournament_history")
            th = cursor.rowcount
            cursor.execute("DELETE FROM rankings")
            rk = cursor.rowcount
            cursor.execute("DELETE FROM fargo_rating_history")
            fh = cursor.rowcount
            cursor.execute("DELETE FROM players")
            pl = cursor.rowcount
            cursor.execute("DELETE FROM test_tournament_matches")
            m = cursor.rowcount
            cursor.execute("DELETE FROM test_tournament_players")
            p = cursor.rowcount
            cursor.execute("DELETE FROM test_tournaments")
            t = cursor.rowcount
            try:
                cursor.execute("REFRESH MATERIALIZED VIEW mv_latest_rankings")
                cursor.execute("REFRESH MATERIALIZED VIEW mv_tournament_history_recent")
            except Exception as exc:
                logger.warning("Test Center reset: materialized view refresh failed: %s", exc)
            conn.commit()
            return {
                "matches_removed": m,
                "players_removed": p,
                "tournaments_removed": t,
                "tournament_results_removed": tr,
                "tournament_history_removed": th,
                "rankings_removed": rk,
                "fargo_rating_history_removed": fh,
                "players_table_removed": pl,
            }
        finally:
            conn.close()

    def delete_matches_for_tournament(self, tournament_id: str) -> int:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM test_tournament_matches WHERE tournament_id = %s",
                (tournament_id,),
            )
            n = cursor.rowcount
            conn.commit()
            return n
        finally:
            conn.close()

    def generate_bracket(
        self,
        shuffle_seeds: bool = False,
        race_to_override: Optional[int] = None,
    ) -> int:
        """Build full bracket from current tournament and registered players."""
        tournament = self.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        tournament_id = tournament['tournament_id']
        players = self.get_registered_players(tournament_id)
        eligible = [p for p in players if (p.get('name') or '').strip()]
        if len(eligible) < 2:
            raise HTTPException(
                status_code=400,
                detail="Need at least two players with names to generate a bracket",
            )

        draw = tournament.get('bracket_draw_size')
        if draw:
            draw_size = int(draw)
        else:
            draw_size = bracket_engine.next_power_of_two(len(eligible))
        if draw_size < bracket_engine.next_power_of_two(len(eligible)):
            draw_size = bracket_engine.next_power_of_two(len(eligible))

        fmt = (tournament.get('format') or 'single_elimination').strip()
        race_to = int(race_to_override or tournament.get('race_to') or 9)
        race_to_final = int(tournament.get("race_to_final") or 10)

        try:
            match_rows = bracket_engine.build_bracket_matches(
                tournament_id,
                players,
                fmt,
                draw_size,
                race_to,
                shuffle_seeds=shuffle_seeds,
                race_to_final=race_to_final,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            self.delete_matches_for_tournament(tournament_id)
            for m in match_rows:
                cursor.execute(
                    """
                    INSERT INTO test_tournament_matches
                    (match_id, tournament_id, bracket_type, round_number, operator_id, player2_id,
                     operator_name, player2_name, operator_score, player2_score, winner_id, status,
                     table_number, race_to)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        m['match_id'],
                        m['tournament_id'],
                        m['bracket_type'],
                        m['round_number'],
                        m.get('operator_id'),
                        m.get('player2_id'),
                        m.get('operator_name'),
                        m.get('player2_name'),
                        m.get('operator_score', 0),
                        m.get('player2_score', 0),
                        m.get('winner_id'),
                        m['status'],
                        m.get('table_number'),
                        m.get('race_to', race_to),
                    ),
                )
            cursor.execute(
                """
                UPDATE test_tournaments
                SET bracket_draw_size = %s, status = 'in_progress', updated_at = CURRENT_TIMESTAMP
                WHERE tournament_id = %s
                """,
                (draw_size, tournament_id),
            )
            conn.commit()
        finally:
            conn.close()

        return len(match_rows)

    def randomize_seeding(self) -> Dict[str, Any]:
        """Shuffle player seeds with dissimilarity enforcement against prior randomizations.

        Returns the new ordering and the total randomization count so far.
        Directors can press the button up to 3 times; each result must be
        observably different from every previous one (Hamming distance >= 25 %
        of the player count).
        """
        tournament = self.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        tournament_id = tournament["tournament_id"]

        players = self.get_registered_players(tournament_id)
        eligible = [p for p in players if (p.get("name") or "").strip()]
        if len(eligible) < 2:
            raise HTTPException(
                status_code=400,
                detail="Need at least two registered players to randomize seeding",
            )

        id_list = [p["player_id"] for p in eligible]
        n = len(id_list)
        min_hamming = max(2, n // 4)

        raw_history = tournament.get("seeding_history") or "[]"
        if isinstance(raw_history, str):
            try:
                history: List[List[str]] = json.loads(raw_history)
            except json.JSONDecodeError:
                history = []
        else:
            history = raw_history

        def hamming(a: List[str], b: List[str]) -> int:
            return sum(1 for x, y in zip(a, b) if x != y)

        best_order: Optional[List[str]] = None
        best_min_dist = -1
        for _attempt in range(200):
            candidate = list(id_list)
            random.shuffle(candidate)
            if not history:
                best_order = candidate
                break
            d = min(hamming(candidate, prev) for prev in history)
            if d >= min_hamming:
                best_order = candidate
                break
            if d > best_min_dist:
                best_min_dist = d
                best_order = candidate

        if best_order is None:
            best_order = list(id_list)
            random.shuffle(best_order)

        history.append(best_order)

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            for new_seed, pid in enumerate(best_order, start=1):
                cursor.execute(
                    """
                    UPDATE test_tournament_players
                    SET seed = %s
                    WHERE tournament_id = %s AND player_id = %s
                    """,
                    (new_seed, tournament_id, pid),
                )
            cursor.execute(
                """
                UPDATE test_tournaments
                SET seeding_history = %s, updated_at = CURRENT_TIMESTAMP
                WHERE tournament_id = %s
                """,
                (json.dumps(history), tournament_id),
            )
            conn.commit()
        finally:
            conn.close()

        id_to_name = {p["player_id"]: p.get("name", "") for p in eligible}
        new_order = [
            {"seed": i + 1, "player_id": pid, "name": id_to_name.get(pid, "")}
            for i, pid in enumerate(best_order)
        ]
        return {
            "randomization_count": len(history),
            "players": new_order,
        }

    def get_bracket_tree(self) -> Dict[str, Any]:
        tournament = self.get_current_tournament()
        if not tournament:
            return {"tournament": None, "rounds": {}, "sections": {}}
        matches = self.get_matches(tournament['tournament_id'])
        rounds: Dict[int, List[Dict[str, Any]]] = {}
        sections: Dict[str, Any] = {"winners": {}, "losers": {}, "grand_final": []}
        for m in matches:
            r = int(m['round_number'])
            rounds.setdefault(r, []).append(m)
            bt = (m.get("bracket_type") or "winners").strip()
            if bt == "grand_final":
                sections["grand_final"].append(m)
            else:
                dct = sections.setdefault(bt, {})
                dct.setdefault(r, []).append(m)
        for r in rounds:
            rounds[r].sort(key=lambda x: x['match_id'])
        for bt in ("winners", "losers"):
            for r in sections.get(bt, {}):
                sections[bt][r].sort(key=lambda x: x["match_id"])
        sections["grand_final"].sort(key=lambda x: x["match_id"])
        return {
            "tournament": tournament,
            "rounds": rounds,
            "sections": sections,
            "matches": matches,
        }

    def add_test_player(
        self,
        first_name: str,
        last_name: str,
        country: Optional[str] = None,
        fargo_rating: Optional[float] = None,
    ) -> Dict[str, Any]:
        current = self.get_current_tournament()
        if not current:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        tournament_id = current['tournament_id']
        first_name = (first_name or '').strip()
        last_name = (last_name or '').strip()
        if not first_name or not last_name:
            raise HTTPException(status_code=400, detail="first_name and last_name are required")
        base = f"{first_name}_{last_name}".lower().replace(' ', '_')
        player_id = f"{base}_{int(time.time() * 1000) % 1_000_000}"
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO test_tournament_players
                (tournament_id, player_id, first_name, last_name, fargo_rating, current_rating, country)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tournament_id, player_id) DO NOTHING
                """,
                (
                    tournament_id,
                    player_id,
                    first_name,
                    last_name,
                    fargo_rating,
                    1500.0,
                    (country or '')[:3] if country else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        players = self.get_registered_players(tournament_id)
        found = next((p for p in players if p['player_id'] == player_id), None)
        if not found:
            raise HTTPException(status_code=500, detail="Failed to add player")
        return found

    def _get_default_players(self) -> List[Dict[str, Any]]:
        """Get the default 64 players for test tournaments"""
        return [
            # Top 16 WPBA Women players (based on Fargo ratings)
            {"player_id": "1", "name": "Kristina Tkach", "fargo_rating": 747.0, "current_rating": 1500.0, "country": "AIN"},
            {"player_id": "2", "name": "Kelly Fisher", "fargo_rating": 715.0, "current_rating": 1500.0, "country": "GBR"},
            {"player_id": "3", "name": "Jasmin Ouschan", "fargo_rating": 698.0, "current_rating": 1500.0, "country": "AUT"},
            {"player_id": "4", "name": "Chen Siming", "fargo_rating": 688.0, "current_rating": 1500.0, "country": "CHN"},
            {"player_id": "5", "name": "Han Yu", "fargo_rating": 691.0, "current_rating": 1500.0, "country": "CHN"},
            {"player_id": "6", "name": "Kim Ga-young", "fargo_rating": 684.0, "current_rating": 1500.0, "country": "KOR"},
            {"player_id": "7", "name": "Karen Corr", "fargo_rating": 680.0, "current_rating": 1500.0, "country": "NIR"},
            {"player_id": "8", "name": "Farnaz Jahangiri", "fargo_rating": 675.0, "current_rating": 1500.0, "country": "IRI"},
            {"player_id": "9", "name": "Natalia Seroshtan", "fargo_rating": 672.0, "current_rating": 1500.0, "country": "UKR"},
            {"player_id": "10", "name": "Chloe Dubois", "fargo_rating": 668.0, "current_rating": 1500.0, "country": "FRA"},
            {"player_id": "11", "name": "Monica Sanches", "fargo_rating": 665.0, "current_rating": 1500.0, "country": "BRA"},
            {"player_id": "12", "name": "Mieszko Fortunski", "fargo_rating": 660.0, "current_rating": 1500.0, "country": "POL"},
            {"player_id": "13", "name": "Karla Urrutia", "fargo_rating": 655.0, "current_rating": 1500.0, "country": "MEX"},
            {"player_id": "14", "name": "Daria Sirotina", "fargo_rating": 650.0, "current_rating": 1500.0, "country": "RUS"},
            {"player_id": "15", "name": "Diana Stateczny", "fargo_rating": 645.0, "current_rating": 1500.0, "country": "POL"},
            {"player_id": "16", "name": "Nicolette Lillian", "fargo_rating": 702.0, "current_rating": 1500.0, "country": "USA"},

            # Slots 17–64: blank until user fills (no "Player 17" placeholders)
            {"player_id": "17", "name": "", "fargo_rating": 640.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "18", "name": "", "fargo_rating": 635.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "19", "name": "", "fargo_rating": 630.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "20", "name": "", "fargo_rating": 625.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "21", "name": "", "fargo_rating": 620.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "22", "name": "", "fargo_rating": 615.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "23", "name": "", "fargo_rating": 610.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "24", "name": "", "fargo_rating": 605.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "25", "name": "", "fargo_rating": 600.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "26", "name": "", "fargo_rating": 595.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "27", "name": "", "fargo_rating": 590.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "28", "name": "", "fargo_rating": 585.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "29", "name": "", "fargo_rating": 580.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "30", "name": "", "fargo_rating": 575.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "31", "name": "", "fargo_rating": 570.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "32", "name": "", "fargo_rating": 565.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "33", "name": "", "fargo_rating": 560.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "34", "name": "", "fargo_rating": 555.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "35", "name": "", "fargo_rating": 550.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "36", "name": "", "fargo_rating": 545.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "37", "name": "", "fargo_rating": 540.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "38", "name": "", "fargo_rating": 535.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "39", "name": "", "fargo_rating": 530.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "40", "name": "", "fargo_rating": 525.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "41", "name": "", "fargo_rating": 520.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "42", "name": "", "fargo_rating": 515.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "43", "name": "", "fargo_rating": 510.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "44", "name": "", "fargo_rating": 505.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "45", "name": "", "fargo_rating": 500.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "46", "name": "", "fargo_rating": 495.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "47", "name": "", "fargo_rating": 490.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "48", "name": "", "fargo_rating": 485.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "49", "name": "", "fargo_rating": 480.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "50", "name": "", "fargo_rating": 475.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "51", "name": "", "fargo_rating": 470.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "52", "name": "", "fargo_rating": 465.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "53", "name": "", "fargo_rating": 460.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "54", "name": "", "fargo_rating": 455.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "55", "name": "", "fargo_rating": 450.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "56", "name": "", "fargo_rating": 445.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "57", "name": "", "fargo_rating": 440.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "58", "name": "", "fargo_rating": 435.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "59", "name": "", "fargo_rating": 430.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "60", "name": "", "fargo_rating": 425.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "61", "name": "", "fargo_rating": 420.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "62", "name": "", "fargo_rating": 415.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "63", "name": "", "fargo_rating": 410.0, "current_rating": 1500.0, "country": "USA"},
            {"player_id": "64", "name": "", "fargo_rating": 405.0, "current_rating": 1500.0, "country": "USA"}
        ]


class TournamentSetupRequest(BaseModel):
    name: str
    format: str
    max_players: int
    entry_fee: float
    tables: int
    race_to: int
    ranking_system: Optional[str] = "WPBA_Women"
    game_type: Optional[str] = "9-ball"
    association: Optional[str] = None
    bracket_template_id: Optional[int] = None
    bracket_draw_size: Optional[int] = None
    bye_strategy: Optional[str] = "top_seed"
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prize_pool: Optional[float] = None
    points_structure: Optional[Dict[str, Any]] = None
    race_to_final: Optional[int] = 10


class AddTestPlayerRequest(BaseModel):
    first_name: str
    last_name: str
    country: Optional[str] = None
    fargo_rating: Optional[float] = None

# Global test tournament manager instance
test_manager = TestTournamentManager()

@router.get("/current")
async def get_current_test_tournament():
    """Get current test tournament"""
    try:
        tournament = test_manager.get_current_tournament()
        return {"success": True, "tournament": tournament}
    except Exception as e:
        logger.error(f"Error getting test tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players")
async def get_test_tournament_players():
    """Get test tournament players"""
    try:
        players = test_manager.get_registered_players()
        return {"success": True, "players": players}
    except Exception as e:
        logger.error(f"Error getting test players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateTestPlayerNameRequest(BaseModel):
    name: str


@router.put("/players/{player_id}/name")
async def update_test_player_name(
    player_id: str,
    body: UpdateTestPlayerNameRequest,
    _auth: dict = Depends(require_director_or_admin),
):
    """Update a test tournament player's display name"""
    try:
        player = test_manager.update_player_name(player_id, body.name)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found in current test tournament")
        return {"success": True, "player": player}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating test player name: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-fill")
async def auto_fill_test_tournament(
    _auth: dict = Depends(require_director_or_admin),
):
    """Add top players from the default list until the tournament is full"""
    try:
        tournament = test_manager.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        added = test_manager.auto_fill_players()
        return {"success": True, "added": added, "message": f"Added {added} player(s)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-filling test tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-registration")
async def clear_test_tournament_registration(
    _auth: dict = Depends(require_director_or_admin),
):
    """Remove all players from the current test tournament so you can re-use Auto Fill"""
    try:
        tournament = test_manager.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=400, detail="No test tournament set up")
        removed = test_manager.clear_registration()
        return {"success": True, "removed": removed, "message": f"Cleared {removed} player(s)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing test tournament registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-classics-demo-players")
async def seed_classics_demo_players(
    _auth: dict = Depends(require_director_or_admin),
):
    """Register 64 demo players (seeds 1-32) for WPBA-style Test Center brackets."""
    try:
        n = test_manager.seed_classics_demo_players()
        return {"success": True, "added": n, "message": f"Registered {n} demo players"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error seeding classics demo players: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-wpba-players-from-production")
async def import_wpba_players_from_production(
    data: Optional[Dict[str, Any]] = None,
    _auth: dict = Depends(require_admin_or_super_admin),
):
    """
    Copy real WPBA player names from the production DB into the current test
    tournament, prefixing each first_name with 'test ' so every row is visibly
    a test row. Reads (SELECT only) from DATABASE_URL; writes only to
    TEST_CENTER_DATABASE_URL.
    """
    try:
        limit = None
        if isinstance(data, dict) and data.get("limit") is not None:
            try:
                limit = int(data.get("limit"))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="limit must be an integer")
        result = test_manager.import_wpba_players_from_production(limit=limit)
        return {
            "success": True,
            "message": (
                f"Copied {result['copied']} WPBA players from production "
                f"(skipped {result['skipped_duplicates']} duplicate(s))."
            ),
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error importing WPBA players from production: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clone-production-to-test-center")
async def clone_production_to_test_center_route(
    data: Optional[Dict[str, Any]] = None,
    _auth: dict = Depends(require_admin_or_super_admin),
):
    """
    Replace Test Center mirror tables (players, rankings, tournament history,
    results, match history, Fargo history) with read-only data cloned from
    production. Names are prefixed with 'test '. Writes only to the Test Center DB.
    Requires a current test tournament (for roster registration).
    """
    try:
        body = data if isinstance(data, dict) else {}
        tlim = body.get("tournament_limit", 50)
        flim = body.get("fargo_history_limit", 20000)
        reg = body.get("register_players_for_current_tournament", True)
        try:
            tournament_limit = int(tlim)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="tournament_limit must be an integer")
        try:
            fargo_history_limit = int(flim)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="fargo_history_limit must be an integer")
        if isinstance(reg, str):
            register_players = reg.lower() in ("1", "true", "yes")
        else:
            register_players = bool(reg)

        result = test_manager.clone_production_to_test_center(
            tournament_limit=tournament_limit,
            fargo_history_limit=fargo_history_limit,
            register_players_for_current_tournament=register_players,
        )
        return {
            "success": True,
            "message": (
                f"Cloned production into Test Center mirror: "
                f"{result['players_copied']} players, {result['rankings_copied']} ranking rows, "
                f"{result['tournaments_copied']} tournaments; "
                f"{result['test_tournament_players_registered']} roster registrations."
            ),
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error cloning production to test center: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matches")
async def get_test_tournament_matches():
    """Get test tournament matches"""
    try:
        matches = test_manager.get_matches()
        return {"success": True, "matches": matches}
    except Exception as e:
        logger.error(f"Error getting test matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard")
async def get_test_tournament_leaderboard():
    """Get test tournament leaderboard"""
    try:
        leaderboard = test_manager.get_leaderboard()
        return {"success": True, "leaderboard": leaderboard}
    except Exception as e:
        logger.error(f"Error getting test leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/setup")
async def setup_test_tournament(
    request: TournamentSetupRequest,
    _auth: dict = Depends(require_director_or_admin),
):
    """Setup a test tournament (admin or super_admin)."""
    try:
        name = request.name
        format_type = request.format
        max_players = request.max_players
        entry_fee = request.entry_fee
        tables = request.tables
        race_to = request.race_to

        ranking_system = getattr(request, "ranking_system", None) or "WPBA_Women"
        game_type = getattr(request, "game_type", None) or "9-ball"
        association = (request.association or "").strip() or None
        bracket_template_id = request.bracket_template_id
        bye_strategy = (request.bye_strategy or "top_seed").strip()
        if request.bracket_draw_size:
            bracket_draw_size = int(request.bracket_draw_size)
        else:
            bracket_draw_size = bracket_engine.next_power_of_two(max(2, max_players))

        loc = (request.location or "").strip() or "Test Venue"
        prize_pool = float(request.prize_pool) if request.prize_pool is not None else float(entry_fee * max_players)
        race_to_final = int(request.race_to_final or 10)
        ps = request.points_structure
        if ps is None:
            ps = bracket_engine.wpba_default_points_structure()
        points_json = json.dumps(ps)

        start_ts = request.start_date or datetime.now().isoformat()
        end_ts = request.end_date

        tournament_data = {
            "tournament_id": f"test_tournament_{int(time.time())}",
            "name": name,
            "format": format_type,
            "max_players": max_players,
            "entry_fee": entry_fee,
            "prize_pool": prize_pool,
            "tables": tables,
            "race_to": race_to,
            "race_to_final": race_to_final,
            "status": "registration",
            "start_date": start_ts,
            "end_date": end_ts,
            "location": loc,
            "ranking_system": ranking_system,
            "game_type": game_type,
            "association": association,
            "bracket_template_id": bracket_template_id,
            "bracket_draw_size": bracket_draw_size,
            "bye_strategy": bye_strategy,
            "points_structure": ps,
        }

        conn = test_manager.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO test_tournaments
                (tournament_id, name, format, max_players, entry_fee, prize_pool, tables, race_to,
                 race_to_final, status, location, start_date, end_date, points_structure, ranking_system, game_type, association,
                 bracket_template_id, bracket_draw_size, bye_strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tournament_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    format = EXCLUDED.format,
                    max_players = EXCLUDED.max_players,
                    entry_fee = EXCLUDED.entry_fee,
                    prize_pool = EXCLUDED.prize_pool,
                    tables = EXCLUDED.tables,
                    race_to = EXCLUDED.race_to,
                    race_to_final = EXCLUDED.race_to_final,
                    status = EXCLUDED.status,
                    location = EXCLUDED.location,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    points_structure = EXCLUDED.points_structure,
                    ranking_system = EXCLUDED.ranking_system,
                    game_type = EXCLUDED.game_type,
                    association = EXCLUDED.association,
                    bracket_template_id = EXCLUDED.bracket_template_id,
                    bracket_draw_size = EXCLUDED.bracket_draw_size,
                    bye_strategy = EXCLUDED.bye_strategy,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    tournament_data["tournament_id"],
                    tournament_data["name"],
                    tournament_data["format"],
                    tournament_data["max_players"],
                    tournament_data["entry_fee"],
                    tournament_data["prize_pool"],
                    tournament_data["tables"],
                    tournament_data["race_to"],
                    tournament_data["race_to_final"],
                    tournament_data["status"],
                    tournament_data.get("location"),
                    tournament_data["start_date"],
                    tournament_data.get("end_date"),
                    points_json,
                    tournament_data.get("ranking_system"),
                    tournament_data.get("game_type"),
                    tournament_data.get("association"),
                    tournament_data.get("bracket_template_id"),
                    tournament_data.get("bracket_draw_size"),
                    tournament_data.get("bye_strategy"),
                ),
            )

            # Do NOT insert any default players here. Rosters are built exclusively from
            # the 'test '-prefixed copy of production players (see
            # /api/test-tournaments/import-wpba-players-from-production and
            # auto_fill_players()), so no un-prefixed or hard-coded names ever land in
            # the test database.

            conn.commit()
        finally:
            conn.close()

        return {"success": True, "tournament": tournament_data}
    except Exception as e:
        logger.error(f"Error setting up test tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-bracket")
async def generate_test_bracket(
    data: Dict[str, Any],
    _auth: dict = Depends(require_director_or_admin),
):
    """Generate full single-elimination (or winners-only double-elim) bracket."""
    try:
        shuffle_seeds = bool(data.get("shuffle_seeds", False))
        race_to = data.get("race_to")
        race_to_override = int(race_to) if race_to is not None else None
        n = test_manager.generate_bracket(
            shuffle_seeds=shuffle_seeds, race_to_override=race_to_override
        )
        return {"success": True, "matches_created": n}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating test bracket: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/randomize-seeding")
async def randomize_test_seeding(
    _auth: dict = Depends(require_director_or_admin),
):
    """Randomize player seeding order (dissimilar to all prior randomizations)."""
    try:
        result = test_manager.randomize_seeding()
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error randomizing seeding: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bracket-tree")
async def get_test_bracket_tree():
    """Bracket grouped by round for UI."""
    try:
        tree = test_manager.get_bracket_tree()
        return {"success": True, **tree}
    except Exception as e:
        logger.error("Error building bracket tree: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/matches/{match_id}/score")
async def update_test_match_score(
    match_id: str,
    score: MatchScoreUpdate,
    _auth: dict = Depends(require_director_or_admin),
):
    """Update test match score and advance bracket (director/admin)."""
    try:
        match = test_manager.update_match_score(
            match_id,
            score.operator_score,
            score.player2_score,
            (score.status.value if hasattr(score.status, "value") else str(score.status)),
        )
        return {"success": True, "match": match}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating test match score: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-database")
async def reset_test_database(
    _auth: dict = Depends(require_admin_or_super_admin),
):
    """Remove all test tournament rows (matches, players, tournaments)."""
    try:
        stats = test_manager.reset_all_test_data()
        return {"success": True, **stats}
    except Exception as e:
        logger.error("Error resetting test database: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/players")
async def add_test_tournament_player(
    body: AddTestPlayerRequest,
    _auth: dict = Depends(require_director_or_admin),
):
    """Add a player to the current test tournament."""
    try:
        player = test_manager.add_test_player(
            body.first_name,
            body.last_name,
            country=body.country,
            fargo_rating=body.fargo_rating,
        )
        return {"success": True, "player": player}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error adding test player: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate-match")
async def simulate_test_match(
    data: Dict[str, Any],
    _auth: dict = Depends(require_director_or_admin),
):
    """Simulate a test match."""
    try:
        match_id = data.get("match_id")
        winner_bias = data.get("winner_bias", "fair")

        if not match_id:
            raise HTTPException(status_code=400, detail="match_id is required")

        match = test_manager.simulate_match(match_id, winner_bias)
        return {"success": True, "match": match}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error simulating test match: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate-all-remaining")
async def simulate_all_remaining_test_matches(
    data: Dict[str, Any],
    _auth: dict = Depends(require_director_or_admin),
):
    """Simulate every playable pending match until none remain (fair bias)."""
    winner_bias = data.get("winner_bias", "fair")
    simulated: List[str] = []
    max_iters = 5000
    it = 0
    try:
        while it < max_iters:
            it += 1
            matches = test_manager.get_matches()
            playable = []
            for m in matches:
                if m.get("status") != "pending":
                    continue
                n1 = (m.get("operator_name") or "").strip()
                n2 = (m.get("player2_name") or "").strip()
                if n1 in ("TBD", "BYE", "") or n2 in ("TBD", "BYE", ""):
                    continue
                if not m.get("operator_id") or not m.get("player2_id"):
                    continue
                playable.append(m)
            if not playable:
                break
            playable.sort(key=lambda x: bracket_engine.simulation_sort_key(x))
            pick = playable[0]
            mid = pick["match_id"]
            test_manager.simulate_match(mid, winner_bias)
            simulated.append(mid)
        return {"success": True, "simulated_match_ids": simulated, "count": len(simulated)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in simulate-all: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EXPORT/IMPORT ENDPOINTS
# ==========================================

class ExportTournamentRequest(BaseModel):
    include_full_data: bool = True
    compress: bool = False
    generate_checksum: bool = True

class ExportScenarioRequest(BaseModel):
    name: str
    description: Optional[str] = None
    test_sequence: List[Dict[str, Any]]
    expected_results: Dict[str, Any]
    include_full_data: bool = True
    compress: bool = False
    generate_checksum: bool = True

class ExportBulkRequest(BaseModel):
    items: List[Dict[str, Any]]  # List of export requests
    name: str
    compress: bool = False
    generate_checksum: bool = True

class ExportTemplateRequest(BaseModel):
    template_name: str
    category: str
    difficulty: str
    estimated_duration: int
    recommended_players: int
    customization_hints: List[str] = []
    compress: bool = False
    generate_checksum: bool = True

class ImportRequest(BaseModel):
    data: str  # JSON string of import data
    validate_only: bool = False
    skip_validation: bool = False
    overwrite_existing: bool = False
    create_backup: bool = True
    migration_strategy: str = "auto"

class BulkImportRequest(BaseModel):
    data: str  # JSON string of bulk import data
    validate_only: bool = False
    skip_validation: bool = False
    overwrite_existing: bool = False
    create_backup: bool = True
    migration_strategy: str = "auto"


@router.post("/export/tournament")
async def export_test_tournament(request: ExportTournamentRequest):
    """Export current test tournament configuration"""
    try:
        tournament = test_manager.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=404, detail="No active test tournament found")

        players = test_manager.get_registered_players()
        matches = test_manager.get_matches()
        leaderboard = test_manager.get_leaderboard()

        # Build export data structure
        export_data = {
            "type": "tournament",
            "version": "1.0",
            "exportedAt": datetime.now().isoformat(),
            "metadata": {
                "name": tournament.get("name", "Test Tournament Export"),
                "description": f"Test tournament exported on {datetime.now().strftime('%Y-%m-%d')}",
                "tournamentType": tournament.get("format", "single_elimination"),
                "maxPlayers": tournament.get("max_players", 8),
                "format": tournament.get("format", "single_elimination")
            },
            "data": {
                "workflowState": {
                    "currentStep": "results",  # Assume completed tournament
                    "tournamentSetup": {
                        "name": tournament.get("name"),
                        "format": tournament.get("format"),
                        "maxPlayers": tournament.get("max_players"),
                        "entryFee": tournament.get("entry_fee", 0),
                        "prizePool": tournament.get("prize_pool", 0),
                        "tables": tournament.get("tables", 1),
                        "raceTo": tournament.get("race_to", 7),
                        "createdAt": tournament.get("created_at", datetime.now().isoformat()),
                        "updatedAt": tournament.get("updated_at", datetime.now().isoformat())
                    },
                    "bracketSetup": {
                        "shuffleSeeds": False,
                        "raceTo": tournament.get("race_to", 7),
                        "byePlayerIds": [],
                        "byeSeedPositions": []
                    },
                    "tournament": tournament if request.include_full_data else None,
                    "players": players if request.include_full_data else None,
                    "matches": matches if request.include_full_data else None,
                    "leaderboard": leaderboard if request.include_full_data else None
                }
            },
            "checksum": ""
        }

        # Generate checksum if requested
        if request.generate_checksum:
            import hashlib
            import json
            data_str = json.dumps(export_data, sort_keys=True, default=str)
            export_data["checksum"] = hashlib.sha256(data_str.encode()).hexdigest()

        return {"success": True, "export": export_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting test tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/scenario")
async def export_test_scenario(request: ExportScenarioRequest):
    """Export a test scenario with parameters and expected results"""
    try:
        tournament = test_manager.get_current_tournament()
        if not tournament:
            raise HTTPException(status_code=404, detail="No active test tournament found")

        # Build scenario export data
        export_data = {
            "type": "scenario",
            "version": "1.0",
            "exportedAt": datetime.now().isoformat(),
            "metadata": {
                "name": request.name,
                "description": request.description,
                "scenarioType": "full_workflow",  # Determine based on test sequence
                "expectedDuration": len(request.test_sequence) * 30000,  # Estimate 30 seconds per step
                "testParameters": request.test_sequence
            },
            "data": {
                "workflowState": {
                    "currentStep": "setup",
                    "tournamentSetup": {
                        "name": tournament.get("name"),
                        "format": tournament.get("format"),
                        "maxPlayers": tournament.get("max_players"),
                        "entryFee": tournament.get("entry_fee", 0),
                        "prizePool": tournament.get("prize_pool", 0),
                        "tables": tournament.get("tables", 1),
                        "raceTo": tournament.get("race_to", 7),
                        "createdAt": tournament.get("created_at", datetime.now().isoformat()),
                        "updatedAt": tournament.get("updated_at", datetime.now().isoformat())
                    },
                    "bracketSetup": {
                        "shuffleSeeds": False,
                        "raceTo": tournament.get("race_to", 7),
                        "byePlayerIds": [],
                        "byeSeedPositions": []
                    }
                },
                "testSequence": request.test_sequence,
                "expectedResults": request.expected_results
            },
            "checksum": ""
        }

        # Generate checksum if requested
        if request.generate_checksum:
            import hashlib
            import json
            data_str = json.dumps(export_data, sort_keys=True, default=str)
            export_data["checksum"] = hashlib.sha256(data_str.encode()).hexdigest()

        return {"success": True, "export": export_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting test scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/bulk")
async def export_bulk_test_data(request: ExportBulkRequest):
    """Export multiple test items in bulk"""
    try:
        exported_items = []

        for item_request in request.items:
            item_type = item_request.get("type")
            if item_type == "tournament":
                # Export tournament
                tournament_export = await export_test_tournament(ExportTournamentRequest(**item_request))
                exported_items.append(tournament_export["export"])
            elif item_type == "scenario":
                # Export scenario
                scenario_export = await export_test_scenario(ExportScenarioRequest(**item_request))
                exported_items.append(scenario_export["export"])
            # Add other item types as needed

        # Build bulk export
        bulk_export = {
            "type": "bulk",
            "version": "1.0",
            "exportedAt": datetime.now().isoformat(),
            "metadata": {
                "name": request.name,
                "itemCount": len(exported_items),
                "items": [
                    {
                        "id": f"bulk_item_{index}",
                        "name": item["metadata"]["name"],
                        "type": item["type"],
                        "size": len(json.dumps(item)),
                        "exportedAt": item["exportedAt"]
                    }
                    for index, item in enumerate(exported_items)
                ],
                "summary": {
                    "totalSize": sum(len(json.dumps(item)) for item in exported_items),
                    "typeBreakdown": {
                        item_type: sum(1 for item in exported_items if item["type"] == item_type)
                        for item_type in set(item["type"] for item in exported_items)
                    },
                    "oldestItem": min(item["exportedAt"] for item in exported_items),
                    "newestItem": max(item["exportedAt"] for item in exported_items),
                    "averageComplexity": 0.5  # Placeholder
                }
            },
            "data": {
                "tournaments": [item for item in exported_items if item["type"] == "tournament"],
                "scenarios": [item for item in exported_items if item["type"] == "scenario"],
                "templates": [],
                "other": [item for item in exported_items if item["type"] not in ["tournament", "scenario"]]
            },
            "checksum": ""
        }

        # Generate checksum if requested
        if request.generate_checksum:
            import hashlib
            import json
            data_str = json.dumps(bulk_export, sort_keys=True, default=str)
            bulk_export["checksum"] = hashlib.sha256(data_str.encode()).hexdigest()

        return {"success": True, "export": bulk_export}
    except Exception as e:
        logger.error(f"Error exporting bulk test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/template")
async def export_test_template(request: ExportTemplateRequest):
    """Export a tournament template"""
    try:
        # Create template data
        template_data = {
            "type": "template",
            "version": "1.0",
            "exportedAt": datetime.now().isoformat(),
            "metadata": {
                "name": request.template_name,
                "category": request.category,
                "tags": request.customization_hints,
                "recommendedFor": [f"{request.difficulty} users", f"{request.recommended_players} players"],
                "estimatedDuration": request.estimated_duration,
                "recommendedPlayers": request.recommended_players
            },
            "data": {
                "workflowState": {
                    "currentStep": "setup",
                    "tournamentSetup": {
                        "name": request.template_name,
                        "format": "single_elimination",
                        "maxPlayers": request.recommended_players,
                        "entryFee": 50,
                        "prizePool": request.recommended_players * 50,
                        "tables": max(1, request.recommended_players // 8),
                        "raceTo": 7,
                        "createdAt": datetime.now().isoformat(),
                        "updatedAt": datetime.now().isoformat()
                    },
                    "bracketSetup": {
                        "shuffleSeeds": True,
                        "raceTo": 7,
                        "byePlayerIds": [],
                        "byeSeedPositions": []
                    }
                },
                "templateSettings": {
                    "isTemplate": True,
                    "category": request.category,
                    "difficulty": request.difficulty,
                    "estimatedDuration": request.estimated_duration,
                    "recommendedPlayers": request.recommended_players,
                    "customizationHints": request.customization_hints,
                    "presetConfigurations": {}
                }
            },
            "checksum": ""
        }

        # Generate checksum if requested
        if request.generate_checksum:
            import hashlib
            import json
            data_str = json.dumps(template_data, sort_keys=True, default=str)
            template_data["checksum"] = hashlib.sha256(data_str.encode()).hexdigest()

        return {"success": True, "export": template_data}
    except Exception as e:
        logger.error(f"Error exporting test template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_test_data(request: ImportRequest):
    """Import tournament data, scenarios, or templates"""
    try:
        import json
        import hashlib

        data = json.loads(request.data)
        data_type = data.get("type")

        # Validate data structure
        if not data_type:
            raise HTTPException(status_code=400, detail="Invalid import data: missing type")

        # Verify checksum if present
        if data.get("checksum") and not request.skip_validation:
            data_without_checksum = {k: v for k, v in data.items() if k != "checksum"}
            calculated_checksum = hashlib.sha256(
                json.dumps(data_without_checksum, sort_keys=True, default=str).encode()
            ).hexdigest()

            if calculated_checksum != data["checksum"]:
                raise HTTPException(status_code=400, detail="Data integrity check failed")

        # Handle different import types
        if data_type == "tournament":
            # Import tournament configuration
            workflow_state = data["data"]["workflowState"]

            # Create tournament in database
            tournament_data = {
                "tournament_id": f"imported_{int(time.time())}_{hashlib.md5(request.data.encode()).hexdigest()[:8]}",
                "name": workflow_state["tournamentSetup"]["name"],
                "format": workflow_state["tournamentSetup"]["format"],
                "max_players": workflow_state["tournamentSetup"]["maxPlayers"],
                "entry_fee": workflow_state["tournamentSetup"]["entryFee"],
                "prize_pool": workflow_state["tournamentSetup"]["prizePool"],
                "tables": workflow_state["tournamentSetup"]["tables"],
                "race_to": workflow_state["tournamentSetup"]["raceTo"],
                "status": "setup",
                "start_date": datetime.now().isoformat()
            }

            # Save to database
            conn = test_manager.db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO test_tournaments
                    (tournament_id, name, format, max_players, entry_fee, prize_pool, tables, race_to, status, start_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tournament_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        format = EXCLUDED.format,
                        max_players = EXCLUDED.max_players,
                        entry_fee = EXCLUDED.entry_fee,
                        prize_pool = EXCLUDED.prize_pool,
                        tables = EXCLUDED.tables,
                        race_to = EXCLUDED.race_to,
                        status = EXCLUDED.status,
                        start_date = EXCLUDED.start_date,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    tournament_data['tournament_id'],
                    tournament_data['name'],
                    tournament_data['format'],
                    tournament_data['max_players'],
                    tournament_data['entry_fee'],
                    tournament_data['prize_pool'],
                    tournament_data['tables'],
                    tournament_data['race_to'],
                    tournament_data['status'],
                    tournament_data['start_date']
                ))

                # Import players if available
                if workflow_state.get("players"):
                    for player in workflow_state["players"]:
                        cursor.execute("""
                            INSERT INTO test_tournament_players
                            (tournament_id, player_id, first_name, last_name, fargo_rating, current_rating, country)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (tournament_id, player_id) DO NOTHING
                        """, (
                            tournament_data['tournament_id'],
                            player['player_id'],
                            player['name'].split()[0] if player.get('name') else '',
                            ' '.join(player['name'].split()[1:]) if player.get('name') and len(player['name'].split()) > 1 else '',
                            player.get('fargo_rating'),
                            player.get('current_rating', 1500.0),
                            player.get('country')
                        ))

                conn.commit()
            finally:
                conn.close()

            return {
                "success": True,
                "importedId": tournament_data['tournament_id'],
                "type": "tournament",
                "message": f"Tournament '{tournament_data['name']}' imported successfully"
            }

        elif data_type == "scenario":
            # Import scenario (store in database or return for frontend handling)
            return {
                "success": True,
                "importedId": f"scenario_{int(time.time())}",
                "type": "scenario",
                "data": data,
                "message": f"Scenario '{data['metadata']['name']}' ready for import"
            }

        elif data_type == "template":
            # Import template (return for frontend handling)
            return {
                "success": True,
                "importedId": f"template_{int(time.time())}",
                "type": "template",
                "data": data,
                "message": f"Template '{data['metadata']['name']}' ready for import"
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import type: {data_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/bulk")
async def import_bulk_test_data(request: BulkImportRequest):
    """Import multiple items in bulk"""
    try:
        import json

        data = json.loads(request.data)

        if data.get("type") != "bulk":
            raise HTTPException(status_code=400, detail="Invalid bulk import data")

        results = []
        successful_imports = 0
        failed_imports = 0
        warnings = []
        errors = []

        # Import each item
        all_items = [
            *(data["data"].get("tournaments") or []),
            *(data["data"].get("scenarios") or []),
            *(data["data"].get("templates") or [])
        ]

        for item in all_items:
            try:
                item_import_request = ImportRequest(
                    data=json.dumps(item),
                    validate_only=request.validate_only,
                    skip_validation=request.skip_validation,
                    overwrite_existing=request.overwrite_existing,
                    create_backup=request.create_backup,
                    migration_strategy=request.migration_strategy
                )

                result = await import_test_data(item_import_request)

                if result["success"]:
                    successful_imports += 1
                else:
                    failed_imports += 1

                if result.get("warnings"):
                    warnings.extend(result["warnings"])
                if result.get("errors"):
                    errors.extend(result["errors"])

                results.append(result)

            except Exception as e:
                failed_imports += 1
                error_msg = f"Failed to import item {item.get('metadata', {}).get('name', 'Unknown')}: {str(e)}"
                errors.append(error_msg)
                results.append({
                    "success": False,
                    "type": item.get("type"),
                    "errors": [error_msg]
                })

        return {
            "totalItems": len(all_items),
            "successfulImports": successful_imports,
            "failedImports": failed_imports,
            "results": results,
            "warnings": warnings,
            "errors": errors,
            "success": failed_imports == 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing bulk test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/templates")
async def get_available_templates():
    """Get list of available tournament templates"""
    try:
        # Return predefined templates
        templates = [
            {
                "id": "beginner-8-player",
                "name": "Beginner 8-Player Single Elimination",
                "description": "Perfect for new players learning tournament basics",
                "category": "beginner",
                "difficulty": "beginner",
                "estimatedDuration": 120,
                "recommendedPlayers": 8,
                "tags": ["beginner", "single-elimination", "quick", "educational"]
            },
            {
                "id": "competitive-64-pro",
                "name": "Professional 64-Player Championship",
                "description": "High-stakes professional tournament with rigorous bracket structure",
                "category": "professional",
                "difficulty": "expert",
                "estimatedDuration": 720,
                "recommendedPlayers": 64,
                "tags": ["professional", "championship", "high-stakes", "rigorous"]
            },
            {
                "id": "casual-32-group-stage",
                "name": "Casual 32-Player Group Stage Tournament",
                "description": "Relaxed tournament with group stage to ensure fair matchups",
                "category": "casual",
                "difficulty": "intermediate",
                "estimatedDuration": 360,
                "recommendedPlayers": 32,
                "tags": ["casual", "group-stage", "fair-matchups", "social"]
            }
        ]

        return {"success": True, "templates": templates}
    except Exception as e:
        logger.error(f"Error getting available templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))