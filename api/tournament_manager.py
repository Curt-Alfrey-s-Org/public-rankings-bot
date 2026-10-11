"""
Tournament Manager - Business Logic for Tournament Management. Postgres only.
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Any
import logging
import math

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


class DuplicatePlayerError(ValueError):
    """Raised when creating a player that already exists (same license or name)."""
    pass


class TournamentManager:
    """Manages tournaments, brackets, matches, and rankings."""

    def __init__(self, db_path: str = None):
        """Initialize tournament manager. db_path is ignored (legacy parameter)."""
        from database.postgres_manager import PostgresManager as DatabaseManager
        self._db_manager = DatabaseManager()

    def get_connection(self):
        """Get database connection."""
        return self._db_manager.get_connection()

    def _table_columns(self, conn, table_name: str) -> set:
        """Return set of column names for table (Postgres via SQLAlchemy inspector)."""
        try:
            inspector = inspect(self._db_manager.engine)
            columns = inspector.get_columns(table_name)
            if columns:
                return {col["name"] for col in columns}
        except Exception as e:
            logger.warning("Column lookup failed for table '%s': %s", table_name, e)
        return set()

    # ==========================================
    # PLAYER OPERATIONS
    # ==========================================
    
    def create_player(self, player_data: Dict) -> str:
        """Create a new player and return player_id. Raises DuplicatePlayerError if duplicate."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Prevent duplicates: same license_number (required to play, unique per player)
        license_number = (player_data.get('license_number') or '').strip()
        if license_number:
            cursor.execute(
                "SELECT player_id, first_name, last_name FROM players WHERE TRIM(license_number) = %s",
                (license_number,)
            )
            row = cursor.fetchone()
            if row:
                r = self._row_to_dict(cursor, row)
                conn.close()
                raise DuplicatePlayerError(
                    f"A player with this license number already exists: {r.get('first_name', '')} {r.get('last_name', '')} ({r.get('player_id', '')})."
                )
        
        # Generate player_id
        cursor.execute("SELECT MAX(CAST(substr(player_id, 2) AS INTEGER)) FROM players WHERE player_id LIKE 'P%'")
        max_id_result = cursor.fetchone()[0]
        next_id = (max_id_result or 0) + 1
        player_id = f"P{next_id:06d}"
        
        player_cols = self._table_columns(conn, "players")
        cols = [
            "player_id", "first_name", "last_name", "nickname", "email", "phone",
            "license_number", "avatar_url", "fargo_score", "nationality", "hometown", "state",
            "membership_status", "hall_of_fame"
        ]
        vals = [
            player_id, player_data['first_name'], player_data['last_name'],
            player_data.get('nickname'), player_data.get('email'), player_data.get('phone'),
            player_data.get('license_number'), player_data.get('avatar_url'),
            player_data.get('fargo_score'), player_data.get('nationality'),
            player_data.get('hometown'), player_data.get('state'),
            player_data.get('membership_status', 'active'),
            1 if player_data.get('hall_of_fame') else 0
        ]
        if "license_expiry_date" in player_cols:
            cols.append("license_expiry_date")
            vals.append(player_data.get("license_expiry_date"))
        for fcol in ("fargo_robustness", "fargo_last_sync", "fargo_source"):
            if fcol in player_cols:
                cols.append(fcol)
                vals.append(player_data.get(fcol))
        cursor.execute(
            f"INSERT INTO players ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            vals
        )
        
        # Initialize player statistics
        cursor.execute("""
            INSERT INTO player_statistics (player_id)
            VALUES (%s)
        """, (player_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created player: {player_id} - {player_data['first_name']} {player_data['last_name']}")
        return player_id
    
    def get_player(self, player_id: str) -> Optional[Dict]:
        """Get player by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM players WHERE player_id = %s", (player_id,))
        row = cursor.fetchone()
        result = self._row_to_dict(cursor, row) if row else None
        conn.close()
        
        return result
    
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

    def get_all_players(self, active_only: bool = True) -> List[Dict]:
        """Get all players"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute("SELECT * FROM players WHERE membership_status = 'active' ORDER BY last_name, first_name")
        else:
            cursor.execute("SELECT * FROM players ORDER BY last_name, first_name")

        players = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return players

    def get_players_for_association(self, association: str, active_only: bool = True) -> List[Dict]:
        """Players who appear in at least one tournament with this association."""
        if not (association or "").strip():
            return self.get_all_players(active_only=active_only)
        assoc = association.strip()
        q = """
            SELECT DISTINCT p.*
            FROM players p
            INNER JOIN tournament_players tp ON tp.player_id = p.player_id
            INNER JOIN tournaments t ON t.tournament_id = tp.tournament_id
            WHERE t.association = :assoc
        """
        if active_only:
            q += " AND p.membership_status = 'active'"
        q += " ORDER BY p.last_name, p.first_name"
        with self._db_manager.engine.connect() as conn:
            result = conn.execute(text(q), {"assoc": assoc})
            rows = result.mappings().all()
        return [dict(r) for r in rows]

    def get_players_for_association_by_frequency(self, association: str, active_only: bool = True) -> List[Dict]:
        """Same as get_players_for_association but order by number of past events in that association."""
        if not (association or "").strip():
            return self.get_all_players(active_only=active_only)
        assoc = association.strip()
        active_clause = " AND p.membership_status = 'active'" if active_only else ""
        q = """
            SELECT p.*, COALESCE(cnt.c, 0) AS assoc_event_count
            FROM players p
            INNER JOIN (
                SELECT tp.player_id, COUNT(DISTINCT tp.tournament_id) AS c
                FROM tournament_players tp
                INNER JOIN tournaments t ON t.tournament_id = tp.tournament_id
                WHERE t.association = :assoc
                GROUP BY tp.player_id
            ) cnt ON cnt.player_id = p.player_id
            WHERE 1=1
        """ + active_clause + """
            ORDER BY cnt.c DESC, p.last_name, p.first_name
        """
        with self._db_manager.engine.connect() as conn:
            result = conn.execute(text(q), {"assoc": assoc})
            rows = result.mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d.pop("assoc_event_count", None)
            out.append(d)
        return out

    def update_player(self, player_id: str, updates: Dict) -> bool:
        """Update player information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic UPDATE query
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key in ['first_name', 'last_name', 'nickname', 'email', 'phone', 'license_number',
                      'avatar_url', 'fargo_score', 'fargo_robustness', 'fargo_last_sync', 'fargo_source',
                      'nationality', 'hometown', 'state', 'membership_status',
                      'license_expiry_date']:
                set_clauses.append(f"{key} = %s")
                values.append(value)
            elif key == 'hall_of_fame':
                set_clauses.append("hall_of_fame = %s")
                values.append(1 if value else 0)
        
        if not set_clauses:
            conn.close()
            return False
        
        values.append(player_id)
        query = f"UPDATE players SET {', '.join(set_clauses)} WHERE player_id = %s"
        
        cursor.execute(query, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        logger.info(f"Updated player: {player_id}")
        return success
    
    def delete_player(self, player_id: str) -> bool:
        """Soft delete player (set to inactive)"""
        return self.update_player(player_id, {'membership_status': 'inactive'})

    def sync_fargo_player(self, player_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Sync Fargo rating for a single player. (DEPRECATED: Fargo scraping is disabled)"""
        return None, "Fargo scraping is disabled. Use CSV import."

    def sync_all_fargo(self) -> Dict:
        """Sync Fargo ratings for all active players. Returns {synced, failed, errors}."""
        players = self.get_all_players(active_only=True)
        synced = 0
        failed = 0
        errors = []
        for p in players:
            pid = p.get("player_id")
            if not pid:
                continue
            _, err = self.sync_fargo_player(pid)
            if err:
                failed += 1
                errors.append({"player_id": pid, "error": err})
            else:
                synced += 1
        return {"synced": synced, "failed": failed, "errors": errors}

    def create_player_from_ranking(
        self,
        name: str,
        country: Optional[str] = None,
        fargo_rating: Optional[int] = None,
        license_number: Optional[str] = None,
    ) -> str:
        """Create a player from a rankings row (WPBA/WPA). Parses name into first/last. Uses license_number from rankings when provided."""
        name = (name or "").strip()
        if not name:
            raise ValueError("name is required")
        # Parse "Last, First" or "First Last"
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            last_name = parts[0] or "Unknown"
            first_name = parts[1] if len(parts) > 1 and parts[1] else "Unknown"
        else:
            parts = name.split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = " ".join(parts[1:])
            elif len(parts) == 1:
                first_name = parts[0]
                last_name = "Unknown"
            else:
                first_name = "Unknown"
                last_name = "Unknown"
        nationality = (country or "").strip()[:3] if country else None
        license_val = (license_number or "").strip() or None
        return self.create_player({
            "first_name": first_name,
            "last_name": last_name,
            "license_number": license_val,
            "nationality": nationality,
            "fargo_score": fargo_rating,
            "membership_status": "active",
        })

    def dedupe_players(self) -> dict:
        """
        Remove duplicate players: same license_number (keep first, deactivate rest);
        same (first_name, last_name) normalized (keep first by player_id, deactivate rest).
        Returns { removed: int, by_license: int, by_name: int, details: list }.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        removed = 0
        by_license = 0
        by_name = 0
        details = []
        try:
            # Duplicates by license_number (non-empty, same value)
            cursor.execute("""
                SELECT license_number, STRING_AGG(player_id, ',' ORDER BY player_id) as ids
                FROM players
                WHERE TRIM(COALESCE(license_number, '')) != ''
                GROUP BY TRIM(license_number)
                HAVING COUNT(*) > 1
            """)
            for row in cursor.fetchall():
                license_number, ids_str = row[0], row[1]
                ids = [x.strip() for x in ids_str.split(",") if x.strip()]
                ids.sort()  # keep first (e.g. P000001)
                keep, drop = ids[0], ids[1:]
                for pid in drop:
                    cursor.execute("UPDATE players SET membership_status = 'inactive' WHERE player_id = %s", (pid,))
                    by_license += 1
                    removed += 1
                    details.append({"player_id": pid, "reason": "duplicate_license", "keep": keep})
            # Duplicates by (first_name, last_name) normalized
            cursor.execute("""
                SELECT LOWER(TRIM(first_name)), LOWER(TRIM(last_name)), STRING_AGG(player_id, ',' ORDER BY player_id) as ids
                FROM players
                WHERE membership_status = 'active'
                GROUP BY LOWER(TRIM(first_name)), LOWER(TRIM(last_name))
                HAVING COUNT(*) > 1
            """)
            for row in cursor.fetchall():
                ids_str = row[2]
                ids = [x.strip() for x in ids_str.split(",") if x.strip()]
                ids.sort()
                keep, drop = ids[0], ids[1:]
                for pid in drop:
                    cursor.execute("UPDATE players SET membership_status = 'inactive' WHERE player_id = %s", (pid,))
                    by_name += 1
                    removed += 1
                    details.append({"player_id": pid, "reason": "duplicate_name", "keep": keep})
            conn.commit()
        finally:
            conn.close()
        return {"removed": removed, "by_license": by_license, "by_name": by_name, "details": details}

    # ==========================================
    # TOURNAMENT OPERATIONS
    # ==========================================
    
    def create_tournament(self, tournament_data: Dict) -> str:
        """Create a new tournament and return tournament_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Generate tournament_id
        cursor.execute("SELECT MAX(CAST(substr(tournament_id, 2) AS INTEGER)) FROM tournaments WHERE tournament_id LIKE 'T%'")
        max_id_result = cursor.fetchone()[0]
        next_id = (max_id_result or 0) + 1
        tournament_id = f"T{next_id:06d}"
        
        points_structure_json = json.dumps(tournament_data['points_structure'])
        
        existing_cols = self._table_columns(conn, "tournaments")
        columns = [
            "tournament_id", "tournament_name", "tournament_date", "location",
            "elimination_type", "max_players", "points_structure", "status",
            "template_id", "created_by", "notes"
        ]
        values = [
            tournament_id,
            tournament_data['tournament_name'],
            tournament_data['tournament_date'],
            tournament_data.get('location'),
            tournament_data['elimination_type'],
            tournament_data.get('max_players', 32),
            points_structure_json,
            'setup',
            tournament_data.get('template_id'),
            tournament_data.get('created_by'),
            tournament_data.get('notes'),
        ]
        if 'game_type' in existing_cols:
            columns.append('game_type')
            values.append(tournament_data.get('game_type'))
        if 'tables_available' in existing_cols:
            columns.append('tables_available')
            values.append(tournament_data.get('tables_available'))
        if 'rules' in existing_cols:
            columns.append('rules')
            values.append(tournament_data.get('rules'))
        if 'stage2_cutoff' in existing_cols:
            columns.append('stage2_cutoff')
            values.append(tournament_data.get('stage2_cutoff'))
        if 'stage2_elimination_type' in existing_cols:
            columns.append('stage2_elimination_type')
            values.append(tournament_data.get('stage2_elimination_type'))
        if 'stage2_seed_strategy' in existing_cols:
            columns.append('stage2_seed_strategy')
            values.append(tournament_data.get('stage2_seed_strategy'))
        if 'stage2_started_at' in existing_cols:
            columns.append('stage2_started_at')
            values.append(tournament_data.get('stage2_started_at'))
        if 'association' in existing_cols:
            columns.append('association')
            values.append(tournament_data.get('association'))
        if 'tournament_end_date' in existing_cols:
            columns.append('tournament_end_date')
            values.append(tournament_data.get('tournament_end_date'))
        if 'bracket_template_id' in existing_cols:
            columns.append('bracket_template_id')
            values.append(tournament_data.get('bracket_template_id'))
        placeholders = ", ".join(["%s"] * len(columns))
        cursor.execute(
            f"INSERT INTO tournaments ({', '.join(columns)}) VALUES ({placeholders})",
            values
        )
        
        # If template was used, increment times_used
        if tournament_data.get('template_id'):
            cursor.execute("""
                UPDATE tournament_templates
                SET times_used = times_used + 1
                WHERE id = %s
            """, (tournament_data['template_id'],))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created tournament: {tournament_id} - {tournament_data['tournament_name']}")
        return tournament_id
    
    def get_tournament(self, tournament_id: str) -> Optional[Dict]:
        """Get tournament by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tournaments WHERE tournament_id = %s", (tournament_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        tournament = self._row_to_dict(cursor, row)
        if isinstance(tournament.get('points_structure'), str):
            tournament['points_structure'] = json.loads(tournament['points_structure'])
        
        conn.close()
        return tournament
    
    def get_completed_results(self, limit: int = 20) -> List[Dict]:
        """
        Get completed tournaments with winner and runner-up names for dashboard/leaderboard.
        Returns list of dicts: tournament_id, tournament_name, tournament_date, winner_name, runner_up_name.
        """
        columns = self._table_columns(None, "tournaments")
        conditions = ["t.status = 'completed'"]
        # Test tournaments are stored in separate tables, no need to filter here
        where_clause = " AND ".join(conditions)

        with self._db_manager.engine.connect() as conn:
            result = conn.execute(
                text(f"""
                    SELECT t.tournament_id, t.tournament_name, t.tournament_date,
                           COALESCE(TRIM(w.first_name || ' ' || w.last_name), NULL) AS winner_name,
                           COALESCE(TRIM(r.first_name || ' ' || r.last_name), NULL) AS runner_up_name
                    FROM tournaments t
                    LEFT JOIN players w ON t.winner_player_id = w.player_id
                    LEFT JOIN players r ON t.runner_up_player_id = r.player_id
                    WHERE {where_clause}
                    ORDER BY t.tournament_date DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            rows = result.mappings().all()

        return [dict(row) for row in rows]

    def get_all_tournaments(self, status: Optional[str] = None, include_test: bool = False) -> List[Dict]:
        """
        Get all tournaments, optionally filtered by status.
        By default, excludes test tournaments unless include_test=True.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build query with test tournament filter
        base_query = "SELECT * FROM tournaments"
        conditions = []
        params = []
        
        # Test tournaments are stored in separate tables, no need to filter here
        
        if status:
            conditions.append("status = %s")
            params.append(status)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " ORDER BY tournament_date DESC"

        cursor.execute(base_query, tuple(params))

        tournaments = []
        column_names = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            tournament = dict(zip(column_names, row))
            tournament['points_structure'] = json.loads(tournament['points_structure'])
            tournaments.append(tournament)
        
        conn.close()
        return tournaments
    
    def update_tournament(self, tournament_id: str, updates: Dict) -> bool:
        """Update tournament information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        columns = self._table_columns(conn, "tournaments")
        
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key in ['tournament_name', 'tournament_date', 'location', 'status', 'notes', 'game_type', 'rules']:
                set_clauses.append(f"{key} = %s")
                values.append(value)
            elif key == 'tables_available':
                set_clauses.append("tables_available = %s")
                values.append(value)
            elif key == 'points_structure':
                set_clauses.append("points_structure = %s")
                values.append(json.dumps(value))
            elif key == 'stage2_cutoff' and 'stage2_cutoff' in columns:
                set_clauses.append("stage2_cutoff = %s")
                values.append(value)
            elif key == 'stage2_elimination_type' and 'stage2_elimination_type' in columns:
                set_clauses.append("stage2_elimination_type = %s")
                values.append(value)
            elif key == 'stage2_seed_strategy' and 'stage2_seed_strategy' in columns:
                set_clauses.append("stage2_seed_strategy = %s")
                values.append(value)
            elif key == 'stage2_started_at' and 'stage2_started_at' in columns:
                set_clauses.append("stage2_started_at = %s")
                values.append(value)
        
        if not set_clauses:
            conn.close()
            return False
        
        # If status changed to completed, set completed_at
        if updates.get('status') == 'completed':
            set_clauses.append("completed_at = %s")
            values.append(datetime.now().isoformat())
        
        values.append(tournament_id)
        query = f"UPDATE tournaments SET {', '.join(set_clauses)} WHERE tournament_id = %s"
        
        cursor.execute(query, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        logger.info(f"Updated tournament: {tournament_id}")
        return success

    def delete_tournament(self, tournament_id: str) -> bool:
        """Delete a tournament and all related matches and player registrations."""
        if not self.get_tournament(tournament_id):
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                DELETE FROM games WHERE match_id IN (
                    SELECT match_id FROM matches WHERE tournament_id = %s
                )
                """,
                (tournament_id,),
            )
            if self._table_calls_exists(cursor):
                cursor.execute("DELETE FROM table_calls WHERE tournament_id = %s", (tournament_id,))
            cursor.execute("DELETE FROM matches WHERE tournament_id = %s", (tournament_id,))
            cursor.execute("DELETE FROM tournament_players WHERE tournament_id = %s", (tournament_id,))
            cursor.execute("DELETE FROM tournaments WHERE tournament_id = %s", (tournament_id,))
            conn.commit()
            logger.info(f"Deleted tournament: {tournament_id}")
            return True
        finally:
            conn.close()

    def register_player(self, tournament_id: str, player_id: str, seed_position: Optional[int] = None) -> bool:
        """Register a player for a tournament"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO tournament_players (tournament_id, player_id, seed_position)
                VALUES (%s, %s, %s)
            """, (tournament_id, player_id, seed_position))
            
            conn.commit()
            logger.info(f"Registered player {player_id} for tournament {tournament_id}")
            return True
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.warning(f"Player {player_id} already registered for tournament {tournament_id}")
                return False
            raise
        finally:
            conn.close()
    
    def unregister_player(self, tournament_id: str, player_id: str) -> bool:
        """Unregister a player from a tournament"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM tournament_players
            WHERE tournament_id = %s AND player_id = %s
        """, (tournament_id, player_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        logger.info(f"Unregistered player {player_id} from tournament {tournament_id}")
        return success
    
    def get_tournament_players(self, tournament_id: str) -> List[Dict]:
        """Get all players registered for a tournament"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                tp.*,
                p.first_name,
                p.last_name,
                p.nickname,
                p.avatar_url,
                p.fargo_score
            FROM tournament_players tp
            JOIN players p ON tp.player_id = p.player_id
            WHERE tp.tournament_id = %s
            ORDER BY tp.seed_position, p.last_name
        """, (tournament_id,))
        
        players = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return players

    def record_check_in(self, tournament_id: str, player_id: str) -> bool:
        """Record player check-in for tournament. Returns True if updated."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournament_players
            SET check_in_at = %s
            WHERE tournament_id = %s AND player_id = %s
        """, (datetime.now().isoformat(), tournament_id, player_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def generate_bracket(
        self,
        tournament_id: str,
        race_to: int = 7,
        shuffle_seeds: bool = False,
        bye_player_ids: Optional[List[str]] = None,
        bye_seed_positions: Optional[List[int]] = None,
    ) -> int:
        """
        Generate bracket matches for a tournament
        Returns number of matches created
        """
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        players = self.get_tournament_players(tournament_id)
        if len(players) < 2:
            raise ValueError("Need at least 2 players to generate bracket")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sort players by seed
        if shuffle_seeds:
            import random
            random.shuffle(players)
        else:
            players.sort(key=lambda p: p['seed_position'] if p['seed_position'] else 999)

        player_ids = [p['player_id'] for p in players]
        
        # Calculate bracket size (next power of 2)
        num_players = len(player_ids)
        bracket_size = 2 ** math.ceil(math.log2(num_players))
        
        elimination_type = tournament['elimination_type']
        matches_created = 0
        
        round1_slots: Optional[List[Optional[str]]] = None
        if elimination_type in ('single', 'double'):
            bye_player_ids = self._resolve_bye_player_ids(
                players,
                player_ids,
                bracket_size,
                bye_player_ids=bye_player_ids,
                bye_seed_positions=bye_seed_positions,
            )
            round1_slots = self._build_round1_slots(player_ids, bracket_size, bye_player_ids)

        if elimination_type == 'single':
            matches_created = self._generate_single_elimination(
                conn,
                cursor,
                tournament_id,
                player_ids,
                bracket_size,
                race_to,
                round1_slots,
                bracket_type="winners",
                match_id_prefix="R",
            )
        elif elimination_type == 'double':
            matches_created = self._generate_double_elimination(
                conn, cursor, tournament_id, player_ids, bracket_size, race_to, round1_slots
            )
        elif elimination_type == 'round_robin':
            matches_created = self._generate_round_robin(
                conn, cursor, tournament_id, player_ids, race_to
            )
        elif elimination_type == 'group_stage':
            num_groups = tournament.get('num_groups')
            players_per_group = tournament.get('players_per_group')
            group_format = tournament.get('group_format', 'round_robin')

            # Calculate defaults if not provided
            if not num_groups or not players_per_group:
                total_players = len(player_ids)
                # Default to 4 groups for tournaments with 16+ players
                if total_players >= 16:
                    num_groups = 4
                    players_per_group = min(8, max(4, total_players // 4))
                elif total_players >= 8:
                    num_groups = 2
                    players_per_group = total_players // 2
                else:
                    # Use round robin for small tournaments
                    matches_created = self._generate_round_robin(
                        conn, cursor, tournament_id, player_ids, race_to
                    )
                    elimination_type = 'round_robin'  # Override for small tournaments

            if elimination_type == 'group_stage':
                matches_created = self._generate_group_stage(
                    conn, cursor, tournament_id, player_ids, race_to,
                    num_groups, players_per_group, group_format
                )
        else:
            raise ValueError(f"Unsupported elimination_type: {elimination_type}")
        
        # Update tournament status
        cursor.execute("""
            UPDATE tournaments
            SET status = 'in_progress'
            WHERE tournament_id = %s
        """, (tournament_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Generated {matches_created} matches for tournament {tournament_id}")
        return matches_created

    def start_stage2(
        self,
        tournament_id: str,
        cutoff: int,
        advancing_player_ids: Optional[List[str]] = None,
        seed_strategy: str = "placement",
        race_to: int = 7,
        bye_player_ids: Optional[List[str]] = None,
        bye_seed_positions: Optional[List[int]] = None,
    ) -> Dict:
        """Start stage 2 single-elimination bracket for a tournament."""
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM matches WHERE tournament_id = %s AND bracket_type = 'stage2' LIMIT 1",
            (tournament_id,),
        )
        if cursor.fetchone():
            conn.close()
            raise ValueError("Stage 2 has already been started for this tournament")

        cursor.execute(
            "SELECT player_id, seed_position, final_placement FROM tournament_players WHERE tournament_id = %s",
            (tournament_id,),
        )
        players_rows = self._rows_to_dicts(cursor, cursor.fetchall())
        if not players_rows:
            conn.close()
            raise ValueError("No registered players found for tournament")

        player_map = {p["player_id"]: p for p in players_rows}

        if advancing_player_ids is not None:
            if len(advancing_player_ids) != cutoff:
                conn.close()
                raise ValueError("Advancing player count must match cutoff")
            unknown = set(advancing_player_ids) - set(player_map.keys())
            if unknown:
                conn.close()
                raise ValueError(f"Unknown player_ids for stage 2: {sorted(unknown)}")
            advancing = [player_map[pid] for pid in advancing_player_ids]
        else:
            cursor.execute(
                """
                SELECT player_id, seed_position, final_placement
                FROM tournament_players
                WHERE tournament_id = %s AND final_placement IS NOT NULL
                ORDER BY final_placement ASC
                LIMIT %s
                """,
                (tournament_id, cutoff),
            )
            advancing = self._rows_to_dicts(cursor, cursor.fetchall())
            if len(advancing) < cutoff:
                conn.close()
                raise ValueError("Not enough final placements to determine stage 2 cutoff")

        seed_strategy = (seed_strategy or "placement").lower()
        if seed_strategy == "placement":
            missing = [p["player_id"] for p in advancing if p.get("final_placement") is None]
            if missing:
                conn.close()
                raise ValueError("Final placement required for placement-based seeding")
            advancing.sort(key=lambda p: p.get("final_placement"))
        elif seed_strategy == "seed":
            advancing.sort(key=lambda p: p.get("seed_position") if p.get("seed_position") is not None else 999)
        elif seed_strategy == "manual":
            pass
        else:
            conn.close()
            raise ValueError("seed_strategy must be placement, seed, or manual")

        advancing_ids = [p["player_id"] for p in advancing]
        bracket_size = 2 ** math.ceil(math.log2(len(advancing_ids)))

        bye_player_ids = self._resolve_bye_player_ids(
            advancing,
            advancing_ids,
            bracket_size,
            bye_player_ids=bye_player_ids,
            bye_seed_positions=bye_seed_positions,
        )
        round1_slots = self._build_round1_slots(advancing_ids, bracket_size, bye_player_ids)

        matches_created = self._generate_single_elimination(
            conn,
            cursor,
            tournament_id,
            advancing_ids,
            bracket_size,
            race_to,
            round1_slots,
            bracket_type="stage2",
            match_id_prefix="S2-R",
        )

        columns = self._table_columns(conn, "tournaments")
        updates = []
        values = []
        if "stage2_cutoff" in columns:
            updates.append("stage2_cutoff = %s")
            values.append(cutoff)
        if "stage2_elimination_type" in columns:
            updates.append("stage2_elimination_type = %s")
            values.append("single")
        if "stage2_seed_strategy" in columns:
            updates.append("stage2_seed_strategy = %s")
            values.append(seed_strategy)
        if "stage2_started_at" in columns:
            updates.append("stage2_started_at = %s")
            values.append(datetime.now().isoformat())
        if updates:
            values.append(tournament_id)
            cursor.execute(
                f"UPDATE tournaments SET {', '.join(updates)} WHERE tournament_id = %s",
                values,
            )

        conn.commit()
        conn.close()

        return {
            "matches_created": matches_created,
            "advancing_count": len(advancing_ids),
            "bracket_size": bracket_size,
        }

    def _resolve_bye_player_ids(
        self,
        players: List[Dict],
        player_ids: List[str],
        bracket_size: int,
        bye_player_ids: Optional[List[str]] = None,
        bye_seed_positions: Optional[List[int]] = None,
    ) -> List[str]:
        bye_count = bracket_size - len(player_ids)
        if bye_count <= 0:
            return []

        resolved: List[str] = []
        if bye_seed_positions:
            seed_map = {p.get("seed_position"): p.get("player_id") for p in players}
            for seed in bye_seed_positions:
                pid = seed_map.get(seed)
                if not pid:
                    raise ValueError(f"Seed position {seed} not found for BYE assignment")
                resolved.append(pid)

        if bye_player_ids:
            unknown = set(bye_player_ids) - set(player_ids)
            if unknown:
                raise ValueError(f"Unknown player_ids for BYE assignment: {sorted(unknown)}")
            resolved.extend(bye_player_ids)

        # De-duplicate while preserving order
        seen = set()
        resolved = [pid for pid in resolved if not (pid in seen or seen.add(pid))]

        if len(resolved) > bye_count:
            raise ValueError("Too many BYE assignments for bracket size")

        if len(resolved) < bye_count:
            # Auto-assign remaining BYEs to top seeds not already selected
            for pid in player_ids:
                if pid in resolved:
                    continue
                resolved.append(pid)
                if len(resolved) == bye_count:
                    break

        return resolved

    def _build_round1_slots(
        self,
        player_ids: List[str],
        bracket_size: int,
        bye_player_ids: List[str],
    ) -> List[Optional[str]]:
        slots: List[Optional[str]] = []
        bye_set = set(bye_player_ids)
        remaining = [pid for pid in player_ids if pid not in bye_set]

        for pid in bye_player_ids:
            slots.extend([pid, None])

        slots.extend(remaining)

        if len(slots) < bracket_size:
            slots.extend([None] * (bracket_size - len(slots)))

        return slots
    
    def _generate_single_elimination(
        self,
        conn,
        cursor,
        tournament_id: str,
        player_ids: List[str],
        bracket_size: int,
        race_to: int,
        round1_slots: Optional[List[Optional[str]]] = None,
        bracket_type: str = "winners",
        match_id_prefix: str = "R",
    ) -> int:
        """Generate single elimination bracket"""
        num_rounds = int(math.log2(bracket_size))
        matches_created = 0

        # Round 1: Pair players in order, assign BYEs if needed
        slots = round1_slots or (player_ids + [None] * (bracket_size - len(player_ids)))
        if len(slots) != bracket_size:
            raise ValueError("Round 1 slots must match bracket size")

        round_1_matches = bracket_size // 2
        for match_num in range(1, round_1_matches + 1):
            p1_idx = (match_num - 1) * 2
            p2_idx = p1_idx + 1

            operator_id = slots[p1_idx]
            player2_id = slots[p2_idx]
            
            # If only one player, it's a BYE
            status = 'bye' if (operator_id and not player2_id) or (player2_id and not operator_id) else 'pending'
            winner_id = operator_id if status == 'bye' else None
            
            match_id = f"{tournament_id}-{match_id_prefix}1-M{match_num:02d}"
            
            cursor.execute("""
                INSERT INTO matches (
                    match_id, tournament_id, round_number, match_number,
                    bracket_type, operator_id, player2_id, race_to, status, winner_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (match_id, tournament_id, 1, match_num, bracket_type, 
                  operator_id, player2_id, race_to, status, winner_id))
            
            matches_created += 1
        
        # Subsequent rounds: Create placeholder matches
        for round_num in range(2, num_rounds + 1):
            num_matches = bracket_size // (2 ** round_num)
            for match_num in range(1, num_matches + 1):
                match_id = f"{tournament_id}-{match_id_prefix}{round_num}-M{match_num:02d}"
                
                cursor.execute("""
                    INSERT INTO matches (
                        match_id, tournament_id, round_number, match_number,
                        bracket_type, race_to, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (match_id, tournament_id, round_num, match_num, bracket_type, race_to, 'pending'))
                
                matches_created += 1
        
        # Round 1 BYE winners have no opponent, so update_match_score/set_match_outcome
        # will never fire for them -- advance them into Round 2 now that it exists.
        if num_rounds >= 2:
            cursor.execute("""
                SELECT * FROM matches
                WHERE tournament_id = %s AND bracket_type = %s AND round_number = 1 AND status = 'bye'
            """, (tournament_id, bracket_type))
            for bye_match in self._rows_to_dicts(cursor, cursor.fetchall()):
                self._advance_winner(conn, cursor, bye_match, bye_match['winner_id'])
        
        return matches_created
    
    def _generate_double_elimination(
        self,
        conn,
        cursor,
        tournament_id: str,
        player_ids: List[str],
        bracket_size: int,
        race_to: int,
        round1_slots: Optional[List[Optional[str]]] = None,
    ) -> int:
        """Generate double elimination bracket (winners + losers brackets + grand final)."""
        matches_created = self._generate_single_elimination(
            conn,
            cursor,
            tournament_id,
            player_ids,
            bracket_size,
            race_to,
            round1_slots,
            bracket_type="winners",
            match_id_prefix="R",
        )
        num_rounds = int(math.log2(bracket_size))

        # Losers bracket rounds: 2 * num_rounds - 2
        # Matches per round repeat twice, halving after every two rounds.
        losers_rounds = max(0, (2 * num_rounds) - 2)
        matches_in_round = bracket_size // 4
        for round_num in range(1, losers_rounds + 1):
            for match_num in range(1, matches_in_round + 1):
                match_id = f"{tournament_id}-L{round_num}-M{match_num:02d}"
                cursor.execute("""
                    INSERT INTO matches (
                        match_id, tournament_id, round_number, match_number,
                        bracket_type, race_to, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (match_id, tournament_id, round_num, match_num, 'losers', race_to, 'pending'))
                matches_created += 1
            if round_num % 2 == 0:
                matches_in_round = max(1, matches_in_round // 2)

        # Grand final: winners final winner vs losers final winner
        match_id = f"{tournament_id}-GF-M01"
        cursor.execute("""
            INSERT INTO matches (
                match_id, tournament_id, round_number, match_number,
                bracket_type, race_to, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (match_id, tournament_id, num_rounds + 1, 1, 'grand_final', race_to, 'pending'))
        matches_created += 1
        return matches_created

    def _generate_round_robin(self, conn, cursor, tournament_id: str, player_ids: List[str], race_to: int) -> int:
        """Generate round robin: each player plays every other player once. Uses circle algorithm."""
        n = len(player_ids)
        if n < 2:
            return 0
        ids = list(player_ids)
        if n % 2 == 1:
            ids.append(None)
            n += 1
        # Circle algorithm: fix index 0, rotate 1..n-1. Round r: 0 vs (1+r), then pair rest.
        num_rounds = n - 1
        matches_created = 0
        for r in range(num_rounds):
            # Round r pairs: (0, 1+r) and remaining (n-2)/2 pairs from indices excluding 0 and 1+r
            opp = (1 + r) % (n - 1) + 1
            rest = [i for i in range(1, n) if i != opp]
            pairs = [(0, opp)]
            # Pair rest: first with last, second with second-last, etc.
            for k in range(len(rest) // 2):
                pairs.append((rest[k], rest[len(rest) - 1 - k]))
            for p1_idx, p2_idx in pairs:
                p1, p2 = ids[p1_idx], ids[p2_idx]
                if p1 is None or p2 is None:
                    continue
                matches_created += 1
                match_id = f"{tournament_id}-RR-R{r+1}-M{matches_created:02d}"
                cursor.execute("""
                    INSERT INTO matches (
                        match_id, tournament_id, round_number, match_number,
                        bracket_type, operator_id, player2_id, race_to, status, winner_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (match_id, tournament_id, r + 1, matches_created, 'round_robin', p1, p2, race_to, 'pending', None))
        return matches_created

    def _generate_group_stage(self, conn, cursor, tournament_id: str, player_ids: List[str],
                            race_to: int, num_groups: int, players_per_group: int,
                            group_format: str = 'round_robin') -> int:
        """
        Generate group stage: divide players into groups, then generate playoffs from group winners.

        Args:
            tournament_id: Tournament identifier
            player_ids: List of player IDs
            race_to: Race-to value for matches
            num_groups: Number of groups to create
            players_per_group: Target players per group
            group_format: Format within groups ('round_robin' or 'single_elimination')

        Returns:
            Total number of matches created
        """
        total_players = len(player_ids)
        matches_created = 0

        # Validate parameters
        if num_groups < 2:
            raise ValueError("Must have at least 2 groups")
        if players_per_group < 2:
            raise ValueError("Groups must have at least 2 players")

        # Calculate actual group sizes (distribute players as evenly as possible)
        base_size = total_players // num_groups
        remainder = total_players % num_groups

        group_sizes = [base_size + (1 if i < remainder else 0) for i in range(num_groups)]

        # Shuffle players for random group assignment
        import random
        shuffled_players = player_ids.copy()
        random.shuffle(shuffled_players)

        # Assign players to groups
        groups = []
        start_idx = 0
        for group_size in group_sizes:
            group_players = shuffled_players[start_idx:start_idx + group_size]
            groups.append(group_players)
            start_idx += group_size

        # Generate matches within each group
        group_winners = []
        for group_idx, group_players in enumerate(groups):
            if len(group_players) < 2:
                continue

            group_id = f"G{group_idx + 1}"

            if group_format == 'round_robin':
                # Generate round robin within group
                n = len(group_players)
                if n % 2 == 1:
                    group_players = group_players + [None]
                    n += 1

                num_rounds = n - 1
                for r in range(num_rounds):
                    opp = (1 + r) % (n - 1) + 1
                    rest = [i for i in range(1, n) if i != opp]
                    pairs = [(0, opp)]
                    for k in range(len(rest) // 2):
                        pairs.append((rest[k], rest[len(rest) - 1 - k]))

                    for p1_idx, p2_idx in pairs:
                        p1, p2 = group_players[p1_idx], group_players[p2_idx]
                        if p1 is None or p2 is None:
                            continue
                        matches_created += 1
                        match_id = f"{tournament_id}-{group_id}-RR-R{r+1}-M{matches_created:02d}"
                        cursor.execute("""
                            INSERT INTO matches (
                                match_id, tournament_id, round_number, match_number,
                                bracket_type, operator_id, player2_id, race_to, status, winner_id
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (match_id, tournament_id, r + 1, matches_created, 'group_stage', p1, p2, race_to, 'pending', None))

            elif group_format == 'single_elimination':
                # Generate single elimination bracket within group
                group_bracket_size = 2 ** math.ceil(math.log2(len(group_players)))
                group_byes = self._resolve_bye_player_ids(
                    [{"player_id": pid} for pid in group_players],
                    group_players,
                    group_bracket_size,
                )
                round1_slots = self._build_round1_slots(group_players, group_bracket_size, group_byes)

                group_matches = self._generate_single_elimination(
                    conn, cursor, tournament_id, group_players, group_bracket_size,
                    race_to, round1_slots, bracket_type="group_stage",
                    match_id_prefix=f"{group_id}-R"
                )
                matches_created += group_matches

            # Group winner determined by highest points (calculated after group matches complete)
            if group_players:
                group_winners.append(group_players[0])  # Placeholder - would be determined by group results

        # Generate playoff bracket from group winners
        if len(group_winners) >= 2:
            playoff_bracket_size = 2 ** math.ceil(math.log2(len(group_winners)))
            playoff_byes = self._resolve_bye_player_ids(
                [{"player_id": pid} for pid in group_winners],
                group_winners,
                playoff_bracket_size,
            )
            playoff_slots = self._build_round1_slots(group_winners, playoff_bracket_size, playoff_byes)

            playoff_matches = self._generate_single_elimination(
                conn, cursor, tournament_id, group_winners, playoff_bracket_size,
                race_to, playoff_slots, bracket_type="playoffs",
                match_id_prefix="PO-R"
            )
            matches_created += playoff_matches

        return matches_created
    
    # ==========================================
    # MATCH OPERATIONS
    # ==========================================

    def set_match_outcome(
        self, match_id: str, outcome: str, reason: str, winner_id: Optional[str] = None
    ) -> bool:
        """Director records forfeit or DQ. Sets winner (advancing player), loser (forfeiting/DQ'd)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = %s", (match_id,))
        match = cursor.fetchone()
        if not match:
            conn.close()
            return False
        match_dict = self._row_to_dict(cursor, match)
        p1, p2 = match_dict.get("operator_id"), match_dict.get("player2_id")
        if winner_id and winner_id in (p1, p2):
            loser_id = p2 if winner_id == p1 else p1
        elif p1 and p2:
            return False  # Must specify who advances
        else:
            winner_id = p1 or p2
            loser_id = None
        match_cols = self._table_columns(conn, "matches")
        set_parts = [
            "status = 'completed'",
            "winner_id = %s",
            "loser_id = %s",
            "completed_at = %s",
        ]
        vals = [winner_id, loser_id, datetime.now().isoformat()]
        if "outcome" in match_cols and "outcome_reason" in match_cols:
            set_parts.extend(["outcome = %s", "outcome_reason = %s"])
            vals.extend([outcome, reason])
        cursor.execute(
            f"UPDATE matches SET {', '.join(set_parts)} WHERE match_id = %s",
            vals + [match_id],
        )
        if winner_id and loser_id:
            tournament_id = match_dict["tournament_id"]
            cursor.execute(
                """
                UPDATE tournament_players SET matches_played = matches_played + 1, matches_won = matches_won + 1
                WHERE tournament_id = %s AND player_id = %s
                """,
                (tournament_id, winner_id),
            )
            cursor.execute(
                """
                UPDATE tournament_players SET matches_played = matches_played + 1, matches_lost = matches_lost + 1
                WHERE tournament_id = %s AND player_id = %s
                """,
                (tournament_id, loser_id),
            )
            self._advance_winner(conn, cursor, match_dict, winner_id)
            self._advance_loser(conn, cursor, match_dict, loser_id)
        conn.commit()
        conn.close()
        return True

    def update_match_score(self, match_id: str, operator_score: int, player2_score: int, 
                          status: str = 'completed') -> bool:
        """Update match score and determine winner"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get match details
        cursor.execute("SELECT * FROM matches WHERE match_id = %s", (match_id,))
        match = cursor.fetchone()
        
        if not match:
            conn.close()
            return False
        
        match_dict = self._row_to_dict(cursor, match)
        operator_id = match_dict['operator_id']
        player2_id = match_dict['player2_id']
        race_to = match_dict['race_to'] or 7
        p1_race = match_dict.get('operator_handicapped_race') or race_to
        p2_race = match_dict.get('player2_handicapped_race') or race_to

        # Determine winner (use handicapped race when applied)
        winner_id = None
        loser_id = None
        if operator_score >= p1_race:
            winner_id = operator_id
            loser_id = player2_id
        elif player2_score >= p2_race:
            winner_id = player2_id
            loser_id = operator_id
        
        # Update match
        cursor.execute("""
            UPDATE matches
            SET operator_score = %s,
                player2_score = %s,
                winner_id = %s,
                loser_id = %s,
                status = %s,
                completed_at = %s
            WHERE match_id = %s
        """, (operator_score, player2_score, winner_id, loser_id, status, 
              datetime.now().isoformat() if status == 'completed' else None, match_id))
        
        # Update tournament_players stats
        if status == 'completed' and winner_id and loser_id:
            tournament_id = match_dict['tournament_id']
            
            # Update winner stats
            cursor.execute("""
                UPDATE tournament_players
                SET matches_played = matches_played + 1,
                    matches_won = matches_won + 1,
                    total_games_won = total_games_won + %s,
                    total_games_lost = total_games_lost + %s
                WHERE tournament_id = %s AND player_id = %s
            """, (operator_score if winner_id == operator_id else player2_score,
                  player2_score if winner_id == operator_id else operator_score,
                  tournament_id, winner_id))
            
            # Update loser stats
            cursor.execute("""
                UPDATE tournament_players
                SET matches_played = matches_played + 1,
                    matches_lost = matches_lost + 1,
                    total_games_won = total_games_won + %s,
                    total_games_lost = total_games_lost + %s
                WHERE tournament_id = %s AND player_id = %s
            """, (player2_score if loser_id == player2_id else operator_score,
                  operator_score if loser_id == player2_id else player2_score,
                  tournament_id, loser_id))
            
            # Advance winner and loser to next matches (if applicable)
            bracket_type = (match_dict.get("bracket_type") or "winners").lower()
            is_gf2 = "-GF2-" in (match_dict.get("match_id") or "")
            if bracket_type == "grand_final" and not is_gf2:
                # True grand final: if losers-bracket winner (L4) beats winners-bracket winner, bracket reset
                tournament_id = match_dict["tournament_id"]
                gf_player2 = match_dict.get("player2_id")  # L4 winner typically in slot 2
                if winner_id == gf_player2:
                    # L bracket winner beat W bracket winner → need GF2 (reset)
                    self._create_grand_final_reset(conn, cursor, tournament_id, winner_id, loser_id, race_to)
                else:
                    # W bracket winner won GF → tournament over
                    self._advance_winner(conn, cursor, match_dict, winner_id)
                    self._advance_loser(conn, cursor, match_dict, loser_id)
            else:
                self._advance_winner(conn, cursor, match_dict, winner_id)
                self._advance_loser(conn, cursor, match_dict, loser_id)
        
        conn.commit()
        conn.close()
        
        # Broadcast events for SSE stream
        try:
            from api.services.tournament_events import emit
            tid = match_dict.get("tournament_id")
            if tid:
                emit(tid, "match_score_update", {"match_id": match_id, "operator_score": operator_score, "player2_score": player2_score})
                if status == "completed" and winner_id:
                    emit(tid, "match_completed", {"match_id": match_id, "winner_id": winner_id, "loser_id": loser_id})
        except Exception as e:
            logger.warning("Failed to emit tournament SSE events for match %s: %s", match_id, e)
        
        logger.info(f"Updated match {match_id}: {operator_score}-{player2_score}, winner: {winner_id}")
        return True

    def _create_grand_final_reset(self, conn, cursor, tournament_id: str, gf_winner_id: str, gf_loser_id: str, race_to: int):
        """Create GF2 match when L bracket winner beats W bracket winner in GF (true grand final)."""
        gf2_id = f"{tournament_id}-GF2-M01"
        cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (gf2_id,))
        if cursor.fetchone():
            return  # GF2 already exists
        cursor.execute("""
            INSERT INTO matches (
                match_id, tournament_id, round_number, match_number,
                bracket_type, operator_id, player2_id, race_to, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (gf2_id, tournament_id, 999, 1, "grand_final", gf_winner_id, gf_loser_id, race_to, "pending"))
        logger.info("Grand final reset: created %s (%s vs %s)", gf2_id, gf_winner_id, gf_loser_id)

    def update_match(self, match_id: str, updates: Dict) -> bool:
        """Update match fields (e.g. table_number, score, forfeit). Only allowed keys are updated."""
        allowed = {'table_number', 'scheduled_time', 'notes', 'status', 'operator_score', 'player2_score', 
                   'is_forfeit', 'forfeit_reason', 'forfeit_notes', 'started_at', 'completed_at',
                   'operator_handicapped_race', 'player2_handicapped_race', 'handicap_applied'}
        updates = {k: v for k, v in updates.items() if k in allowed}
        if not updates:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
        if not cursor.fetchone():
            conn.close()
            return False
        set_parts = []
        values = []
        for k, v in updates.items():
            set_parts.append(f"{k} = %s")
            values.append(v)
        values.append(match_id)
        cursor.execute(f"UPDATE matches SET {', '.join(set_parts)} WHERE match_id = %s", values)
        conn.commit()
        conn.close()
        logger.info(f"Updated match {match_id}: {list(updates.keys())}")
        return True

    def calculate_match_handicap(self, match_id: str) -> Optional[Dict]:
        """Calculate Fargo-based handicap for a match. Returns suggested operator_race, player2_race or None."""
        match = self.get_match(match_id)
        if not match:
            return None
        p1_id = match.get("operator_id")
        p2_id = match.get("player2_id")
        if not p1_id or not p2_id:
            return None
        p1 = self.get_player(p1_id)
        p2 = self.get_player(p2_id)
        if not p1 or not p2:
            return None
        race_to = match.get("race_to") or 7
        bracket_type = (match.get("bracket_type") or "winners").lower()
        from api.services.fargo_handicap import calculate_handicap
        p1_race, p2_race = calculate_handicap(
            p1.get("fargo_score"), p2.get("fargo_score"),
            race_to=race_to, bracket_type=bracket_type
        )
        return {
            "match_id": match_id,
            "operator_handicapped_race": p1_race,
            "player2_handicapped_race": p2_race,
            "handicap_applied": p1_race != race_to or p2_race != race_to,
        }

    def apply_fargo_handicaps(self, tournament_id: str) -> Dict:
        """Apply Fargo handicaps to all matches in tournament. Returns {applied, skipped, errors}."""
        matches = self.get_tournament_matches(tournament_id)
        applied = 0
        skipped = 0
        errors = []
        for m in matches:
            mid = m.get("match_id")
            if not mid or not m.get("operator_id") or not m.get("player2_id"):
                skipped += 1
                continue
            result = self.calculate_match_handicap(mid)
            if not result or not result.get("handicap_applied"):
                skipped += 1
                continue
            success = self.update_match(mid, {
                "operator_handicapped_race": result["operator_handicapped_race"],
                "player2_handicapped_race": result["player2_handicapped_race"],
                "handicap_applied": 1,
            })
            if success:
                applied += 1
            else:
                errors.append(mid)
        return {"applied": applied, "skipped": skipped, "errors": errors}
    
    def _advance_winner(self, conn, cursor, match: Dict, winner_id: str):
        """Advance winner to next round match.

        Winners/stage2 bracket: advances to next round (or grand final) via a
        next-round match lookup, using the standard halve-match-number pairing.

        Losers bracket (double elim only): the LB's internal shape alternates
        between two patterns, so it cannot use the generic lookup above. See
        _advance_loser for how winners-bracket losers drop into the LB; this
        method handles the LB's own internal winner progression:
          - LB round r (odd) winner advances to LB round r+1, same match
            index, slot 'player2' (waiting to be paired with that WB round's
            drop-in, which fills slot 'operator' -- see _advance_loser).
          - LB round r (even) winner advances to LB round r+1, match index
            ceil(match_number/2), slot by parity of match_number (pairing two
            LB winners together).
          - The LB final (round == 2*num_rounds-2) winner advances to the
            grand final, slot 'player2' (the WB champion occupies slot
            'operator', set when the WB final's winner advances below).
        """
        tournament_id = match['tournament_id']
        round_number = int(match['round_number'])
        match_number = int(match['match_number'])
        bracket_type = (match.get('bracket_type') or 'winners').lower()
        if bracket_type == 'grand_final':
            return

        if bracket_type == 'losers':
            num_rounds = self._winners_bracket_num_rounds(cursor, tournament_id)
            last_lb_round = max(0, 2 * num_rounds - 2)
            if last_lb_round and round_number == last_lb_round:
                target_id, slot = f"{tournament_id}-GF-M01", 'player2_id'
            elif round_number % 2 == 1:
                target_id = f"{tournament_id}-L{round_number + 1}-M{match_number:02d}"
                slot = 'player2_id'
            else:
                next_match_num = (match_number + 1) // 2
                target_id = f"{tournament_id}-L{round_number + 1}-M{next_match_num:02d}"
                slot = 'operator_id' if match_number % 2 == 1 else 'player2_id'
            cursor.execute(f"UPDATE matches SET {slot} = %s WHERE match_id = %s", (winner_id, target_id))
            return

        next_round = round_number + 1
        next_match_num = (match_number + 1) // 2
        # For winners bracket: next is winners or grand_final; for stage2: next is stage2
        if bracket_type == 'stage2':
            cursor.execute("""
                SELECT * FROM matches
                WHERE tournament_id = %s AND round_number = %s AND match_number = %s
                AND bracket_type = 'stage2'
            """, (tournament_id, next_round, next_match_num))
        else:
            cursor.execute("""
                SELECT * FROM matches
                WHERE tournament_id = %s AND round_number = %s AND match_number = %s
                AND bracket_type IN ('winners', 'grand_final')
            """, (tournament_id, next_round, next_match_num))
        next_match_row = cursor.fetchone()
        if not next_match_row:
            return
        next_match = self._row_to_dict(cursor, next_match_row)
        if match_number % 2 == 1:
            cursor.execute("UPDATE matches SET operator_id = %s WHERE match_id = %s", (winner_id, next_match['match_id']))
        else:
            cursor.execute("UPDATE matches SET player2_id = %s WHERE match_id = %s", (winner_id, next_match['match_id']))

    def _winners_bracket_num_rounds(self, cursor, tournament_id: str) -> int:
        """Number of winners-bracket rounds for this tournament (log2 of bracket size).

        Read from the generated matches themselves (MAX round_number where
        bracket_type='winners') rather than recomputed from player counts, so it
        stays correct even if registration changed after bracket generation.
        """
        cursor.execute(
            "SELECT MAX(round_number) AS n FROM matches WHERE tournament_id = %s AND bracket_type = 'winners'",
            (tournament_id,),
        )
        row = cursor.fetchone()
        n = row[0] if row else None
        return int(n) if n else 0

    def _advance_loser(self, conn, cursor, match: Dict, loser_id: str):
        """Drop a winners-bracket loser into the losers bracket (double elim only).

        Only applies to winners-bracket matches: the loser gets a second life in
        the LB. A losers-bracket match loser has now lost twice and is simply
        eliminated -- no further routing -- so this is a no-op for bracket_type
        'losers' (the LB match's *winner* progression is handled by
        _advance_winner instead).

        Generalized for any power-of-two bracket size (previously hardcoded to
        the 8-player/3-round shape only, which silently dropped the
        winners-bracket-final loser for any other bracket size):
          - WB round 1 losers pair directly into LB round 1 (two losers per match).
          - WB round r >= 2 (including the WB final) loser drops into LB round
            2*(r-1), same match index, slot 'operator'.
        """
        bracket_type = (match.get('bracket_type') or 'winners').lower()
        if bracket_type != 'winners':
            return
        tournament_id = match['tournament_id']
        round_number = int(match['round_number'])
        match_number = int(match['match_number'])
        prefix = f"{tournament_id}-"

        target, slot = None, None
        if round_number == 1:
            target = f"{prefix}L1-M{(match_number + 1) // 2:02d}"
            slot = 'operator_id' if match_number % 2 == 1 else 'player2_id'
        elif round_number >= 2:
            lb_round = 2 * (round_number - 1)
            target = f"{prefix}L{lb_round}-M{match_number:02d}"
            slot = 'operator_id'
        if not target or not slot:
            return
        cursor.execute(
            f"UPDATE matches SET {slot} = %s WHERE match_id = %s",
            (loser_id, target),
        )

    def get_tournament_matches(self, tournament_id: str) -> List[Dict]:
        """Get all matches for a tournament"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.*,
                p1.first_name || ' ' || p1.last_name as operator_name,
                p2.first_name || ' ' || p2.last_name as player2_name
            FROM matches m
            LEFT JOIN players p1 ON m.operator_id = p1.player_id
            LEFT JOIN players p2 ON m.player2_id = p2.player_id
            WHERE m.tournament_id = %s
            ORDER BY
                CASE m.bracket_type WHEN 'winners' THEN 1 WHEN 'losers' THEN 2 WHEN 'stage2' THEN 3 WHEN 'grand_final' THEN 4 ELSE 5 END,
                m.round_number, m.match_number
        """, (tournament_id,))
        
        matches = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return matches

    # ==========================================
    # FORFEIT / DQ OPERATIONS
    # ==========================================

    def get_match(self, match_id: str) -> Optional[Dict]:
        """Get a single match by match_id with player names"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.*,
                p1.first_name || ' ' || p1.last_name as operator_name,
                p2.first_name || ' ' || p2.last_name as player2_name
            FROM matches m
            LEFT JOIN players p1 ON m.operator_id = p1.player_id
            LEFT JOIN players p2 ON m.player2_id = p2.player_id
            WHERE m.match_id = %s
        """, (match_id,))
        
        match = cursor.fetchone()
        result = self._row_to_dict(cursor, match) if match else None
        conn.close()
        return result

    def forfeit_match(self, match_id: str, winner_id: str, reason: str, notes: Optional[str] = None) -> bool:
        """Mark match as forfeit, set winner, and advance to next round"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get match details
        cursor.execute("SELECT * FROM matches WHERE match_id = %s", (match_id,))
        match = cursor.fetchone()
        
        if not match:
            conn.close()
            return False
        
        match_dict = self._row_to_dict(cursor, match)
        tournament_id = match_dict['tournament_id']
        operator_id = match_dict['operator_id']
        player2_id = match_dict['player2_id']
        
        # Determine loser (other player)
        loser_id = player2_id if winner_id == operator_id else operator_id
        
        # Update match (status = 'completed' so frontend shows as done; forfeit_reason indicates DQ)
        cursor.execute("""
            UPDATE matches
            SET is_forfeit = 1,
                status = %s,
                winner_id = %s,
                loser_id = %s,
                forfeit_reason = %s,
                forfeit_notes = %s,
                completed_at = %s
            WHERE match_id = %s
        """, ('completed', winner_id, loser_id, reason, notes, datetime.now().isoformat(), match_id))
        
        # Update tournament_players stats
        cursor.execute("""
            UPDATE tournament_players
            SET matches_played = matches_played + 1,
                matches_won = matches_won + 1
            WHERE tournament_id = %s AND player_id = %s
        """, (tournament_id, winner_id))
        
        # Update loser stats
        cursor.execute("""
            UPDATE tournament_players
            SET matches_played = matches_played + 1,
                matches_lost = matches_lost + 1
            WHERE tournament_id = %s AND player_id = %s
        """, (tournament_id, loser_id))
        
        # Advance winner and loser to next matches
        self._advance_winner(conn, cursor, match_dict, winner_id)
        self._advance_loser(conn, cursor, match_dict, loser_id)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Forfeit match {match_id}: winner={winner_id}, loser={loser_id}, reason={reason}")
        return True

    def get_matches_by_table(self, tournament_id: str, table_number: int) -> List[Dict]:
        """Get all matches for a specific table in a tournament"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.*,
                p1.first_name || ' ' || p1.last_name as operator_name,
                p2.first_name || ' ' || p2.last_name as player2_name
            FROM matches m
            LEFT JOIN players p1 ON m.operator_id = p1.player_id
            LEFT JOIN players p2 ON m.player2_id = p2.player_id
            WHERE m.tournament_id = %s AND m.table_number = %s
            ORDER BY m.round_number, m.match_number
        """, (tournament_id, table_number))
        
        matches = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return matches

    def get_matches_for_score_keeper(self, tournament_id: str, user_id: str) -> List[Dict]:
        """Get matches for a score keeper based on their table or round assignment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Query score_keeper_assignments
        cursor.execute("""
            SELECT table_number, round_number
            FROM score_keeper_assignments
            WHERE tournament_id = %s AND user_id = %s
            LIMIT 1
        """, (tournament_id, user_id))
        
        assignment = cursor.fetchone()
        
        if assignment:
            assignment_dict = self._row_to_dict(cursor, assignment)
            if assignment_dict.get('table_number'):
                # Table-specific assignment
                cursor.execute("""
                    SELECT 
                        m.*,
                        p1.first_name || ' ' || p1.last_name as operator_name,
                        p2.first_name || ' ' || p2.last_name as player2_name
                    FROM matches m
                    LEFT JOIN players p1 ON m.operator_id = p1.player_id
                    LEFT JOIN players p2 ON m.player2_id = p2.player_id
                    WHERE m.tournament_id = %s AND m.table_number = %s
                    ORDER BY m.round_number, m.match_number
                """, (tournament_id, assignment_dict['table_number']))
            elif assignment_dict.get('round_number'):
                # Round-specific assignment (not yet implemented)
                conn.close()
                logger.debug(f"Round-specific assignment not yet implemented for user {user_id}")
                return []
            else:
                # No specific assignment, return all tournament matches
                cursor.execute("""
                    SELECT 
                        m.*,
                        p1.first_name || ' ' || p1.last_name as operator_name,
                        p2.first_name || ' ' || p2.last_name as player2_name
                    FROM matches m
                    LEFT JOIN players p1 ON m.operator_id = p1.player_id
                    LEFT JOIN players p2 ON m.player2_id = p2.player_id
                    WHERE m.tournament_id = %s
                    ORDER BY m.round_number, m.match_number
                """, (tournament_id,))
        else:
            # No assignment found, return all tournament matches
            cursor.execute("""
                SELECT 
                    m.*,
                    p1.first_name || ' ' || p1.last_name as operator_name,
                    p2.first_name || ' ' || p2.last_name as player2_name
                FROM matches m
                LEFT JOIN players p1 ON m.operator_id = p1.player_id
                LEFT JOIN players p2 ON m.player2_id = p2.player_id
                WHERE m.tournament_id = %s
                ORDER BY m.round_number, m.match_number
            """, (tournament_id,))
        
        matches = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return matches

    # ==========================================
    # TABLE CALLS (report-to-table warnings)
    # ==========================================

    def _table_calls_exists(self, cursor) -> bool:
        try:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'table_calls'"
            )
            return cursor.fetchone() is not None
        except Exception:
            return False

    def create_table_call(
        self,
        match_id: str,
        tournament_id: str,
        table_number: int,
        report_by_utc: datetime,
        warning_minutes: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        """Create a table call for a match. Default warning_minutes [20, 15, 10, 5, 1]. Returns the created row or None."""
        warning_minutes = warning_minutes if warning_minutes is not None else [20, 15, 10, 5, 1]
        conn = self.get_connection()
        cursor = conn.cursor()
        if not self._table_calls_exists(cursor):
            conn.close()
            return None
        cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
        if not cursor.fetchone():
            conn.close()
            return None
        cursor.execute(
            """INSERT INTO table_calls (match_id, tournament_id, table_number, report_by_utc, warning_minutes, sent_warnings)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (match_id, tournament_id, table_number, report_by_utc, json.dumps(warning_minutes), json.dumps([])),
        )
        row_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        # Update match table_number
        self.update_match(match_id, {"table_number": table_number})
        return {
            "id": row_id,
            "match_id": match_id,
            "tournament_id": tournament_id,
            "table_number": table_number,
            "report_by_utc": report_by_utc.isoformat() if hasattr(report_by_utc, "isoformat") else str(report_by_utc),
            "warning_minutes": warning_minutes,
            "sent_warnings": [],
            "created_at": datetime.utcnow().isoformat(),
        }

    def get_table_calls(self, tournament_id: str) -> List[Dict]:
        """Return all table calls for a tournament."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if not self._table_calls_exists(cursor):
            conn.close()
            return []
        cursor.execute(
            "SELECT * FROM table_calls WHERE tournament_id = %s ORDER BY report_by_utc DESC",
            (tournament_id,),
        )
        rows = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        for r in rows:
            if isinstance(r.get("report_by_utc"), datetime):
                r["report_by_utc"] = r["report_by_utc"].isoformat()
            if isinstance(r.get("warning_minutes"), str):
                try:
                    r["warning_minutes"] = json.loads(r["warning_minutes"]) if r["warning_minutes"] else [20, 15, 10, 5, 1]
                except Exception:
                    r["warning_minutes"] = [20, 15, 10, 5, 1]
            if isinstance(r.get("sent_warnings"), str):
                try:
                    r["sent_warnings"] = json.loads(r["sent_warnings"]) if r["sent_warnings"] else []
                except Exception:
                    r["sent_warnings"] = []
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
        return rows

    def process_table_call_warnings(self) -> Dict[str, int]:
        """Send due table-call warnings (20/15/10/5/1 min) to players via email. Returns {sent: N, errors: N}."""
        from api.notifications import send_email
        conn = self.get_connection()
        cursor = conn.cursor()
        if not self._table_calls_exists(cursor):
            conn.close()
            return {"sent": 0, "errors": 0}
        now = datetime.utcnow()
        cursor.execute("SELECT * FROM table_calls")
        rows = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        sent = 0
        errors = 0
        for r in rows:
            call_id = r.get("id")
            report_by = r.get("report_by_utc")
            if isinstance(report_by, str):
                try:
                    report_by = datetime.fromisoformat(report_by.replace("Z", "+00:00"))
                except Exception:
                    continue
            if hasattr(report_by, "tzinfo") and report_by.tzinfo:
                report_by = report_by.replace(tzinfo=None)
            if report_by <= now:
                continue
            mins = r.get("warning_minutes")
            if isinstance(mins, str):
                try:
                    mins = json.loads(mins) if mins else [20, 15, 10, 5, 1]
                except Exception:
                    mins = [20, 15, 10, 5, 1]
            sent_list = list(r.get("sent_warnings") or [])
            if isinstance(sent_list, str):
                try:
                    sent_list = json.loads(sent_list) if sent_list else []
                except Exception:
                    sent_list = []
            match_id = r["match_id"]
            tournament_id = r["tournament_id"]
            table_number = r["table_number"]
            conn2 = self.get_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                "SELECT operator_id, player2_id FROM matches WHERE match_id = %s",
                (match_id,),
            )
            m = cur2.fetchone()
            if not m:
                conn2.close()
                continue
            p1_id, p2_id = m[0], m[1]
            emails = []
            for pid in (p1_id, p2_id):
                if not pid:
                    continue
                cur2.execute("SELECT email FROM players WHERE player_id = %s", (pid,))
                e = cur2.fetchone()
                if e and e[0]:
                    emails.append(e[0])
            conn2.close()
            if not emails:
                continue
            for minutes in mins:
                if minutes in sent_list:
                    continue
                target_time = report_by - timedelta(minutes=minutes)
                if now >= target_time:
                    subject = f"Table call: Report to table #{table_number} in {minutes} minute(s)"
                    body = f"Your match is called. Please report to table #{table_number} in {minutes} minute(s)."
                    for email in emails:
                        if send_email(email, subject, body):
                            sent += 1
                        else:
                            errors += 1
                    sent_list.append(minutes)
                    conn3 = self.get_connection()
                    cur3 = conn3.cursor()
                    cur3.execute(
                        "UPDATE table_calls SET sent_warnings = %s WHERE id = %s",
                        (json.dumps(sent_list), call_id),
                    )
                    conn3.commit()
                    conn3.close()
                    break
        return {"sent": sent, "errors": errors}

    def process_match_reminders(self, reminder_minutes: int = 15) -> Dict[str, int]:
        """Send match reminder emails X minutes before scheduled/projected start. Returns {sent, errors}."""
        import os
        from api.services.projected_times import compute_projected_times

        def _parse_dt(s):
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
                return dt.replace(tzinfo=None) if hasattr(dt, "tzinfo") and dt.tzinfo else dt
            except Exception:
                return None
        if not os.getenv("MATCH_REMINDER_EMAIL_ENABLED", "true").lower() in ("1", "true", "yes"):
            return {"sent": 0, "errors": 0}
        from api.notifications import send_email
        conn = self.get_connection()
        cursor = conn.cursor()
        cols = self._table_columns(conn, "matches")
        has_reminder_sent = "match_reminder_sent" in cols
        if not has_reminder_sent:
            conn.close()
            return {"sent": 0, "errors": 0}
        now = datetime.utcnow()
        window_end = now + timedelta(minutes=reminder_minutes)
        cursor.execute("""
            SELECT m.*, t.tournament_date, t.tournament_name
            FROM matches m
            JOIN tournaments t ON m.tournament_id = t.tournament_id
            WHERE m.status IN ('pending', 'in_progress')
            AND m.operator_id IS NOT NULL AND m.player2_id IS NOT NULL
            AND (m.match_reminder_sent IS NULL OR m.match_reminder_sent = 0)
        """)
        matches = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        sent = 0
        errors = 0
        for m in matches:
            start_dt = None
            sched = m.get("scheduled_time")
            if sched:
                try:
                    start_dt = datetime.fromisoformat(str(sched).replace("Z", "+00:00"))
                    if hasattr(start_dt, "tzinfo") and start_dt.tzinfo:
                        start_dt = start_dt.replace(tzinfo=None)
                except Exception as e:
                    logger.debug("Could not parse scheduled_time '%s' for match %s: %s", sched, m.get("match_id"), e)
            if not start_dt:
                tid = m.get("tournament_id")
                tdate = m.get("tournament_date")
                td_str = tdate.isoformat() if hasattr(tdate, "isoformat") else str(tdate or "")
                enriched = compute_projected_times([m], tournament_date=td_str)
                if enriched:
                    start_dt = _parse_dt(enriched[0].get("projected_start_time"))
            if not start_dt or start_dt < now or start_dt > window_end:
                continue
            p1_id, p2_id = m.get("operator_id"), m.get("player2_id")
            emails = []
            conn2 = self.get_connection()
            cur2 = conn2.cursor()
            for pid in (p1_id, p2_id):
                if not pid:
                    continue
                cur2.execute("SELECT email, first_name, last_name FROM players WHERE player_id = %s", (pid,))
                row = cur2.fetchone()
                if row and row[0]:
                    emails.append((row[0], f"{row[1] or ''} {row[2] or ''}".strip()))
            conn2.close()
            table_num = m.get("table_number") or "TBD"
            tournament_name = m.get("tournament_name", "Tournament")
            subject = f"Match reminder: {tournament_name} — {reminder_minutes} min"
            body = f"Your match starts in about {reminder_minutes} minutes. Table: {table_num}. Tournament: {tournament_name}."
            for email, _ in emails:
                if send_email(email, subject, body):
                    sent += 1
                else:
                    errors += 1
            if emails:
                conn3 = self.get_connection()
                cur3 = conn3.cursor()
                cur3.execute("UPDATE matches SET match_reminder_sent = 1 WHERE match_id = %s", (m["match_id"],))
                conn3.commit()
                conn3.close()
        return {"sent": sent, "errors": errors}
    
    # ==========================================
    # RANKINGS CALCULATION
    # ==========================================
    
    def recalculate_rankings(self) -> int:
        """Recalculate rankings for all players based on completed tournaments"""
        conn = self.get_connection()
        cursor = conn.cursor()
        columns = self._table_columns(conn, "tournaments")
        conditions = ["status = 'completed'"]
        # Test tournaments are stored in separate tables, no need to filter here
        where_clause = " AND ".join(conditions)

        # Get all completed, non-test tournaments
        cursor.execute(f"""
            SELECT tournament_id, points_structure, tournament_date
            FROM tournaments
            WHERE {where_clause}
            ORDER BY tournament_date DESC
        """)
        
        tournaments = self._rows_to_dicts(cursor, cursor.fetchall())
        
        # Reset all player points
        cursor.execute("UPDATE players SET total_points = 0.0, current_rank = NULL")
        
        # Calculate points for each player
        for tournament in tournaments:
            tournament_id = tournament['tournament_id']
            ps = tournament['points_structure']
            points_structure = json.loads(ps) if isinstance(ps, str) else (ps or {})
            
            # Get final placements
            cursor.execute("""
                SELECT player_id, final_placement
                FROM tournament_players
                WHERE tournament_id = %s AND final_placement IS NOT NULL
            """, (tournament_id,))
            
            for row in cursor.fetchall():
                player_id = row[0]
                placement = str(row[1])
                points = points_structure.get(placement, 0)
                
                # Add points to player
                cursor.execute("""
                    UPDATE players
                    SET total_points = total_points + %s
                    WHERE player_id = %s
                """, (points, player_id))
                
                # Update tournament_players points_earned
                cursor.execute("""
                    UPDATE tournament_players
                    SET points_earned = %s
                    WHERE tournament_id = %s AND player_id = %s
                """, (points, tournament_id, player_id))
        
        # Assign ranks based on total points
        cursor.execute("""
            SELECT player_id, total_points
            FROM players
            WHERE membership_status = 'active' AND total_points > 0
            ORDER BY total_points DESC
        """)
        
        rank = 1
        for row in cursor.fetchall():
            player_id = row[0]
            cursor.execute("""
                UPDATE players
                SET current_rank = %s
                WHERE player_id = %s
            """, (rank, player_id))
            rank += 1
        
        # Save ranking snapshot
        cursor.execute("""
            INSERT INTO ranking_history (player_id, rank_position, total_points, snapshot_date)
            SELECT player_id, current_rank, total_points, CURRENT_DATE
            FROM players
            WHERE current_rank IS NOT NULL
        """)
        
        conn.commit()
        players_ranked = rank - 1
        conn.close()
        
        logger.info(f"Recalculated rankings for {players_ranked} players")
        return players_ranked
    
    def get_current_rankings(self, limit: Optional[int] = None) -> List[Dict]:
        """Get current player rankings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM v_current_rankings"
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        rankings = [dict(zip(column_names, row)) for row in rows]
        conn.close()
        return rankings

    # ==========================================
    # GAME/RACK METHODS
    # ==========================================

    def create_game(self, match_id: str, game_number: int, winner_id: str,
                    breaking_player_id: Optional[str] = None, innings: Optional[int] = None,
                    run_out: bool = False, break_and_run: bool = False,
                    notes: Optional[str] = None) -> int:
        """Create a new game/rack result. Returns game ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        run_out_val = 1 if run_out else 0
        break_and_run_val = 1 if break_and_run else 0

        # Check for duplicate game_number in this match (idempotency)
        cursor.execute("""
            SELECT id FROM games WHERE match_id = %s AND game_number = %s
        """, (match_id, game_number))

        existing = cursor.fetchone()
        if existing:
            # Update existing game instead of creating duplicate
            cursor.execute("""
                UPDATE games SET
                    winner_id = %s, breaking_player_id = %s, innings = %s,
                    run_out = %s, break_and_run = %s, notes = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (winner_id, breaking_player_id, innings, run_out_val, break_and_run_val, notes, existing[0]))
            conn.commit()
            conn.close()
            return existing[0]

        # Create new game
        cursor.execute("""
            INSERT INTO games (match_id, game_number, winner_id, breaking_player_id,
                              innings, run_out, break_and_run, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (match_id, game_number, winner_id, breaking_player_id, innings, run_out_val, break_and_run_val, notes))

        game_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return game_id

    def get_game(self, game_id: int) -> Optional[Dict]:
        """Get game by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = %s", (game_id,))
        row = cursor.fetchone()
        result = self._row_to_dict(cursor, row) if row else None
        conn.close()
        return result

    def update_game(self, game_id: int, updates: Dict) -> bool:
        """Update game result. Returns True if successful."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Build update query dynamically
        set_parts = []
        values = []
        for key, value in updates.items():
            if key in ['winner_id', 'breaking_player_id', 'innings', 'run_out', 'break_and_run', 'notes']:
                if key in ('run_out', 'break_and_run') and isinstance(value, bool):
                    value = 1 if value else 0
                set_parts.append(f"{key} = %s")
                values.append(value)

        if not set_parts:
            conn.close()
            return False

        query = f"UPDATE games SET {', '.join(set_parts)} WHERE id = %s"
        values.append(game_id)

        cursor.execute(query, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_match_games(self, match_id: str) -> List[Dict]:
        """Get all games for a match, ordered by game_number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM games WHERE match_id = %s ORDER BY game_number
        """, (match_id,))
        games = self._rows_to_dicts(cursor, cursor.fetchall())
        conn.close()
        return games

    def synchronize_match_score_from_games(self, match_id: str) -> bool:
        """Update match score based on game results. Returns True if successful."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Count wins for each player
        cursor.execute("""
            SELECT
                winner_id,
                COUNT(*) as wins
            FROM games
            WHERE match_id = %s AND winner_id IS NOT NULL
            GROUP BY winner_id
        """, (match_id,))

        player_wins = {row[0]: row[1] for row in cursor.fetchall()}

        # Get match info
        cursor.execute("""
            SELECT operator_id, player2_id, race_to, status
            FROM matches WHERE match_id = %s
        """, (match_id,))

        match_row = cursor.fetchone()
        if not match_row:
            conn.close()
            return False

        operator_id, player2_id, race_to, current_status = match_row
        race_to = race_to or 7  # Default race_to

        operator_score = player_wins.get(operator_id, 0)
        player2_score = player_wins.get(player2_id, 0)

        # Determine winner and status
        winner_id = None
        loser_id = None
        new_status = current_status

        if operator_score >= race_to:
            winner_id = operator_id
            loser_id = player2_id
            new_status = 'completed'
        elif player2_score >= race_to:
            winner_id = player2_id
            loser_id = operator_id
            new_status = 'completed'
        elif current_status != 'completed':
            new_status = 'in_progress'

        # Update match
        cursor.execute("""
            UPDATE matches SET
                operator_score = %s, player2_score = %s, winner_id = %s, loser_id = %s, status = %s,
                completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE match_id = %s
        """, (operator_score, player2_score, winner_id, loser_id, new_status, new_status, match_id))

        conn.commit()
        conn.close()
        return True
