"""
Fargo Ratings DB Client — Manual Import Only.
"""

import logging
import unicodedata
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Set

logger = logging.getLogger(__name__)

ORG_TO_SYSTEM: Dict[str, str] = {
    "WPBA": "WPBA_Women",
    "WPA": "WPA_Women",
    "WPA_Women": "WPA_Women",
    "WPA_Men": "WPA_Men",
    "WPBA_Women": "WPBA_Women",
    "WPA_Heyball_Men": "WPA_Heyball_Men",
    "WPA_Heyball_Women": "WPA_Heyball_Women",
    "WPA_Artistic": "WPA_Artistic",
}


def normalize_name(name: str) -> str:
    """Normalize name: trim, collapse internal whitespace."""
    if not name or not isinstance(name, str):
        return ""
    return " ".join(name.split()).strip()


def parse_name(name: str) -> Tuple[str, str]:
    """
    Parse name to (first, last) in lowercase.
    Handles: "First Last" or "Last, First" formats.
    """
    if not name:
        return "", ""
    
    s = normalize_name(name)
    if "," in s:
        # "Last, First" format
        parts = s.split(",", 1)
        last = parts[0].strip().lower()
        first = parts[1].strip().lower() if len(parts) > 1 else ""
    else:
        # "First Last" format
        parts = s.rsplit(" ", 1)
        if len(parts) == 2:
            first = parts[0].strip().lower()
            last = parts[1].strip().lower()
        else:
            first = ""
            last = parts[0].strip().lower() if parts else ""
    
    return first, last


def canonical_form(name: str) -> str:
    """
    Canonical form for cross-format matching: lowercase "firstname lastname".
    Converts "Last, First" → "first last" for matching.
    """
    first, last = parse_name(name)
    return f"{first} {last}".strip()


def normalized_match_key(name: str) -> str:
    """
    Stable key for joining names across punctuation/order/accent differences.
    """
    base = canonical_form(name)
    if not base:
        return ""
    ascii_name = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_name.lower() if ch.isalnum())


def _name_match_keys(name: str) -> Set[str]:
    """
    Candidate matching keys for ambiguous ordering formats.
    Includes:
    - canonical key
    - raw-order key
    - "move last token to front" key
    """
    keys: Set[str] = set()
    raw = normalize_name(name)
    if not raw:
        return keys

    primary = normalized_match_key(raw)
    if primary:
        keys.add(primary)

    raw_ascii = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw_key = "".join(ch for ch in raw_ascii.lower() if ch.isalnum())
    if raw_key:
        keys.add(raw_key)

    tokens = [t for t in raw.replace(",", " ").split() if t]
    if len(tokens) >= 2:
        moved = " ".join([tokens[-1], *tokens[:-1]])
        moved_key = normalized_match_key(moved)
        if moved_key:
            keys.add(moved_key)

    return keys


def _players_columns(conn) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'players'")
    return [row[0] for row in cur.fetchall()]


def _rankings_columns(conn) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'rankings'")
    return [row[0] for row in cur.fetchall()]


def _build_player_id_index(conn) -> Dict[str, List[str]]:
    """Build index mapping normalized name keys -> player_id list."""
    cur = conn.cursor()
    cur.execute("SELECT player_id, first_name, last_name, nickname FROM players")
    idx: Dict[str, List[str]] = {}
    for pid, first, last, nick in cur.fetchall():
        full = f"{first or ''} {last or ''}".strip()
        names_to_try = [full]
        if nick:
            names_to_try.append(f"{nick} {last or ''}".strip())
        for n in names_to_try:
            for k in _name_match_keys(n):
                idx.setdefault(k, []).append(pid)
    return idx


def _load_name_aliases(conn, ranking_system: Optional[str] = None) -> Dict[str, str]:
    """Load player_name_aliases mapping scraped name to canonical name."""
    alias_map: Dict[str, str] = {}
    try:
        cur = conn.cursor()
        if ranking_system:
            cur.execute(
                """
                SELECT scraped_name, canonical_name
                FROM player_name_aliases
                WHERE ranking_system = %s
                """,
                (ranking_system,),
            )
        else:
            cur.execute("SELECT scraped_name, canonical_name FROM player_name_aliases")
        for scraped_name, canonical_name in cur.fetchall():
            key = normalized_match_key(scraped_name or "")
            if key and canonical_name:
                alias_map[key] = canonical_name
    except Exception as e:
        logger.debug("Could not load player_name_aliases: %s", e)
    return alias_map


def get_distinct_player_names(conn, org_code: str) -> List[str]:
    """Get distinct player names from rankings for org (latest snapshot)."""
    cur = conn.cursor()
    system = ORG_TO_SYSTEM.get(org_code, org_code)
    cur.execute(
        """SELECT player_name FROM rankings
           WHERE ranking_system = %s 
           AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = %s)
           ORDER BY rank ASC""",
        (system, system),
    )
    return [row[0] for row in cur.fetchall() if row and row[0]]


def get_names_missing_fargo(conn, org_code: str) -> List[str]:
    """Get player names in org whose player profile still has NULL Fargo score."""
    cur = conn.cursor()
    system = ORG_TO_SYSTEM.get(org_code, org_code)
    cur.execute(
        """
        WITH players_by_name AS (
          SELECT
            LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
            MAX(fargo_score) AS fargo_score
          FROM players
          GROUP BY LOWER(TRIM(first_name || ' ' || last_name))
        )
        SELECT r.player_name
        FROM rankings r
        LEFT JOIN players_by_name p_direct
          ON p_direct.full_name = LOWER(
            TRIM(
              REGEXP_REPLACE(
                CASE
                  WHEN POSITION(',' IN r.player_name) > 0
                    THEN TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                  ELSE r.player_name
                END,
                '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                ''
              )
            )
          )
        LEFT JOIN players_by_name p_swapped
          ON p_swapped.full_name = LOWER(
            TRIM(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  CASE
                    WHEN POSITION(',' IN r.player_name) > 0
                      THEN TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                    ELSE r.player_name
                  END,
                  '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                  ''
                ),
                '^(.*)\\s+([^\\s]+)$',
                '\\2 \\1'
              )
            )
          )
        WHERE r.ranking_system = %s
          AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = %s)
          AND COALESCE(p_direct.fargo_score, p_swapped.fargo_score, r.fargo_rating) IS NULL
        ORDER BY r.rank ASC
        """,
        (system, system),
    )
    return [row[0] for row in cur.fetchall() if row and row[0]]


def update_rankings_with_fargo(
    conn,
    fargo_data: List[Dict[str, Any]],
    ranking_system: Optional[str] = None,
) -> int:
    """
    Update players table with Fargo ratings by player_name match.
    Stores fargo_source_name for future lookup reuse.
    
    Args:
        conn: Database connection (Postgres)
        fargo_data: List of {player_name, fargo_rating, fargo_robustness, updated_at, fargo_source_name}
    
    Returns:
        Count of rows updated
    """
    updated = 0
    unmatched = 0
    try:
        cur = conn.cursor()
        player_cols = _players_columns(conn)
        if "fargo_score" not in player_cols:
            logger.warning("players table missing fargo_score; skipping Fargo update")
            return 0
        has_last_updated = "fargo_last_updated" in player_cols
        has_robustness = "fargo_robustness" in player_cols
        player_ids_by_key = _build_player_id_index(conn)
        alias_map = _load_name_aliases(conn, ranking_system)
        
        for row in fargo_data:
            player_name = row.get("player_name", "")
            fargo = row.get("fargo_rating")
            updated_at = row.get("updated_at", datetime.now(timezone.utc).isoformat())
            robustness = row.get("fargo_robustness")
            
            if not player_name or fargo is None:
                continue

            raw_key = normalized_match_key(player_name)
            alias_name = alias_map.get(raw_key, player_name)

            target_player_ids: List[str] = []
            seen: Set[str] = set()
            candidate_keys: Set[str] = set()
            for nm in (player_name, alias_name):
                candidate_keys.update(_name_match_keys(nm))
            for key in candidate_keys:
                for player_id in player_ids_by_key.get(key, []):
                    if player_id not in seen:
                        seen.add(player_id)
                        target_player_ids.append(player_id)
            if not target_player_ids:
                unmatched += 1
                continue

            set_parts = ["fargo_score = %s"]
            params: List[Any] = [fargo]
            if has_last_updated:
                set_parts.append("fargo_last_updated = %s")
                params.append(updated_at)
            if has_robustness and robustness is not None:
                set_parts.append("fargo_robustness = %s")
                params.append(robustness)

            fargo_source = row.get("fargo_source") or "system_update"
            for player_id in target_player_ids:
                # Keep previous Fargo in history before updating
                cur.execute(
                    "SELECT fargo_score FROM players WHERE player_id = %s",
                    (player_id,),
                )
                old_row = cur.fetchone()
                old_fargo = float(old_row[0]) if old_row and old_row[0] is not None else None

                cur.execute(
                    "UPDATE players SET " + ", ".join(set_parts) + " WHERE player_id = %s",
                    [*params, player_id],
                )
                n = cur.rowcount
                updated += n
                if n and old_fargo != fargo:
                    try:
                        cur.execute(
                            """
                            INSERT INTO fargo_rating_history (
                                player_id, player_name, ranking_system,
                                old_fargo_rating, new_fargo_rating, fargo_source,
                                snapshot_date, confidence_score, data_quality
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                player_id,
                                player_name,
                                ranking_system or None,
                                old_fargo,
                                float(fargo),
                                fargo_source,
                                date.today(),
                                0.8,
                                "verified",
                            ),
                        )
                    except Exception as hist_err:
                        logger.warning(
                            "Could not archive Fargo history for %s: %s",
                            player_id,
                            hist_err,
                        )
        
        conn.commit()
        logger.info(
            "Updated %d players with Fargo ratings (unmatched rows=%d, system=%s)",
            updated,
            unmatched,
            ranking_system or "any",
        )
    except Exception as e:
        logger.exception("Failed to update players with Fargo: %s", e)
    
    return updated


def import_fargo_ratings_manual(
    conn, system: str, ratings_list: List[Dict[str, Any]]
) -> Tuple[int, Optional[str]]:
    """
    Manually import Fargo ratings (e.g., from CSV).
    system: 'WPBA' or 'WPA'
    """
    ranking_system = ORG_TO_SYSTEM.get(system, ORG_TO_SYSTEM.get(system.upper(), system))
    
    try:
        cur = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        normalized_rows: List[Dict[str, Any]] = []

        for row in ratings_list:
            player_name = (row.get("player_name") or row.get("name") or "").strip()
            try:
                fargo = float(row.get("fargo_rating") or row.get("rating", 0))
            except (TypeError, ValueError):
                continue
            if not player_name:
                continue

            scraped_name = (row.get("fargo_source_name") or row.get("fargo_name_format") or "").strip()
            if scraped_name and scraped_name != player_name:
                cur.execute(
                    """
                    INSERT INTO player_name_aliases (scraped_name, canonical_name, ranking_system)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (scraped_name, ranking_system)
                    DO UPDATE SET canonical_name = EXCLUDED.canonical_name
                    """,
                    (scraped_name, player_name, ranking_system),
                )

            normalized_rows.append(
                {
                    "player_name": player_name,
                    "fargo_rating": fargo,
                    "fargo_robustness": row.get("fargo_robustness"),
                    "updated_at": now_iso,
                    "fargo_source_name": scraped_name or player_name,
                    "fargo_source": "manual_import",
                }
            )

        updated = update_rankings_with_fargo(conn, normalized_rows, ranking_system=ranking_system)
        logger.info("Manual Fargo import: updated %d rows for %s", updated, ranking_system)
        return updated, None
    except Exception as e:
        logger.exception("Manual Fargo import failed: %s", e)
        return 0, str(e)
