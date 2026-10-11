"""
Head-to-head player comparison API. Uses shared DB (get_database_manager).
"""

import logging
import math
from fastapi import APIRouter, HTTPException
from psycopg2.errors import UndefinedTable

from fastapi import Depends

from database import get_database_manager
from api.auth import get_optional_user
from api.services.alfa_engine import get_alfa_player

logger = logging.getLogger(__name__)
router = APIRouter(tags=["head-to-head"])


def calculate_fargo_win_probability(player_fargo, opponent_fargo):
    """
    Calculate win probability based on Fargo ratings using the ELO-style formula.
    
    Formula: P(player wins) = 1 / (1 + 10^((opponent_fargo - player_fargo) / 400))
    
    Args:
        player_fargo: Player's Fargo rating (float or None)
        opponent_fargo: Opponent's Fargo rating (float or None)
    
    Returns:
        float: Win probability (0.0 to 1.0), or None if either rating is missing
    """
    if player_fargo is None or opponent_fargo is None:
        return None
    
    try:
        # Convert to float if needed
        player_fargo = float(player_fargo)
        opponent_fargo = float(opponent_fargo)
        
        # Calculate win probability using Fargo formula
        rating_diff = opponent_fargo - player_fargo
        probability = 1.0 / (1.0 + math.pow(10, rating_diff / 400.0))
        
        return probability
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.warning(f"Error calculating Fargo win probability: {e}")
        return None


def _safe_row_val(row, index_or_key, default=None):
    """Get value from row by index or key without raising."""
    if row is None:
        return default
    try:
        if isinstance(index_or_key, int):
            return row[index_or_key] if index_or_key < len(row) else default
        return row[index_or_key] if index_or_key in row.keys() else default
    except (IndexError, KeyError, TypeError):
        return default


# Ranking systems to try when looking up players (matches player-names API)
_HEAD_TO_HEAD_SYSTEMS = ("WPBA_Women", "WPA_Women", "WPA_Men", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPBA", "WPA")


def _player_data(cursor, player_id: str, system: str):
    """Fetch one player's ranking row and recent trends. Returns dict or None. Uses case-insensitive name match."""
    player_id_str = (player_id or "").strip()
    id_is_numeric = player_id_str.isdigit()
    if id_is_numeric:
        query = """
            SELECT player_name, rank, points, fargo_rating, fargo_last_updated
            FROM rankings
            WHERE (player_name = %s OR id = %s) AND ranking_system = %s
            ORDER BY snapshot_date DESC LIMIT 1
            """
        params = (player_id_str, int(player_id_str), system)
    else:
        query = """
            SELECT player_name, rank, points, fargo_rating, fargo_last_updated
            FROM rankings
            WHERE LOWER(TRIM(player_name)) = LOWER(TRIM(%s)) AND ranking_system = %s
            ORDER BY snapshot_date DESC LIMIT 1
            """
        params = (player_id_str, system)
    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
        return None
    # Column order: player_name=0, rank=1, points=2, fargo_rating=3, fargo_last_updated=4
    player_name = _safe_row_val(row, 0) or _safe_row_val(row, "player_name") or ""
    cursor.execute(
        """
        SELECT old_rank, new_rank FROM ranking_changes
        WHERE player_name = %s AND ranking_system = %s
        ORDER BY change_date DESC LIMIT 5
        """,
        (player_name, system),
    )
    trend_rows = cursor.fetchall()
    trends = []
    for r in trend_rows:
        try:
            trends.append({"old": r[0], "new": r[1]})
        except (IndexError, TypeError) as e:
            logger.warning("Could not parse ranking trend row for player '%s': %s", player_name, e)
    rank_val = _safe_row_val(row, 1)
    if rank_val is None:
        rank_val = _safe_row_val(row, "rank")
    points_val = _safe_row_val(row, 2)
    if points_val is None:
        points_val = _safe_row_val(row, "points")
    fargo_val = _safe_row_val(row, 3)
    if fargo_val is None:
        fargo_val = _safe_row_val(row, "fargo_rating")
    return {
        "id": player_name,
        "name": player_name,
        "rank": rank_val,
        "fargo_rating": fargo_val,
        "points": points_val,
        "ranking_trend": trends[:5],
        "recent_matches": [],
        "wins": 0,
        "losses": 0,
        "win_pct": 0.0,
    }


def _find_player(cursor, player_id: str):
    """Try each ranking system until player is found. Returns dict or None."""
    for system in _HEAD_TO_HEAD_SYSTEMS:
        p = _player_data(cursor, player_id, system)
        if p:
            return p
    return None


def _can_see_alfa(user) -> bool:
    role = (user or {}).get("role") or ""
    return role in ("admin", "super_admin")


@router.get("/api/players/{player_id}/head-to-head/{opponent_id}")
async def get_head_to_head(
    player_id: str,
    opponent_id: str,
    user=Depends(get_optional_user),
):
    """
    Return head-to-head comparison: operator, player2, head_to_head.
    Includes detailed match history from tournaments.
    """
    conn = None
    try:
        conn = get_database_manager().get_connection()
        cursor = conn.cursor()
        p1 = _find_player(cursor, player_id)
        p2 = _find_player(cursor, opponent_id)
        if not p1:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        if not p2:
            raise HTTPException(status_code=404, detail=f"Player {opponent_id} not found")

        # Add ALFa Rating when available (admin/super_admin only)
        if _can_see_alfa(user):
            db_manager = get_database_manager()
            for p, name in [(p1, p1["name"]), (p2, p2["name"])]:
                try:
                    alfa = get_alfa_player(db_manager, name)
                    if alfa:
                        p["alfa_rating"] = alfa.get("alfa_rating")
                except Exception as e:
                    logger.warning("Could not fetch ALFa rating for '%s': %s", name, e)
                    p["alfa_rating"] = None
        else:
            p1["alfa_rating"] = None
            p2["alfa_rating"] = None

        # Query direct matches between the two players
        operator_name = p1["name"]
        player2_name = p2["name"]
        
        # Try to fetch tournament match history - gracefully handle if tables don't exist
        matches = []
        direct_wins_p1 = 0
        direct_losses_p1 = 0
        
        try:
            cursor.execute("""
                SELECT 
                    thm.id,
                    thm.tournament_id,
                    th.name as tournament_name,
                    th.date as tournament_date,
                    th.location,
                    th.year,
                    thm.round_num,
                    thm.operator_name,
                    thm.player2_name,
                    thm.operator_score,
                    thm.player2_score,
                    thm.winner_name,
                    thm.notes
                FROM tournament_history_matches thm
                JOIN tournament_history th ON thm.tournament_id = th.tournament_id
                WHERE (
                    (LOWER(TRIM(thm.operator_name)) = LOWER(TRIM(%s)) AND LOWER(TRIM(thm.player2_name)) = LOWER(TRIM(%s)))
                    OR (LOWER(TRIM(thm.operator_name)) = LOWER(TRIM(%s)) AND LOWER(TRIM(thm.player2_name)) = LOWER(TRIM(%s)))
                )
                ORDER BY th.year DESC, th.date DESC, thm.round_num DESC
            """, (operator_name, player2_name, player2_name, operator_name))
            
            match_rows = cursor.fetchall()
            
            for row in match_rows:
                match_dict = dict(row)
                # Count wins/losses for operator
                winner = (match_dict.get("winner_name") or "").strip()
                if winner and operator_name and winner.lower() == operator_name.lower():
                    direct_wins_p1 += 1
                elif winner and player2_name and winner.lower() == player2_name.lower():
                    direct_losses_p1 += 1
                
                # Format match data for frontend
                matches.append({
                    "id": match_dict.get("id"),
                    "tournament_id": match_dict.get("tournament_id"),
                    "tournament_name": match_dict.get("tournament_name"),
                    "date": match_dict.get("tournament_date"),
                    "location": match_dict.get("location") or "Unknown location",
                    "year": match_dict.get("year"),
                    "round": match_dict.get("round_num"),
                    "operator_name": match_dict.get("operator_name"),
                    "player2_name": match_dict.get("player2_name"),
                    "operator_score": match_dict.get("operator_score"),
                    "player2_score": match_dict.get("player2_score"),
                    "winner": winner,
                    "notes": match_dict.get("notes"),
                })
        except UndefinedTable as e:
            logger.info("Tournament history tables not found, returning empty match history: %s", e)
            # Tables don't exist yet - return empty matches list
            matches = []
            direct_wins_p1 = 0
            direct_losses_p1 = 0
        except Exception as e:
            logger.warning("Error fetching tournament match history (non-critical): %s", e)
            # Don't fail the entire request - just log and continue with empty matches
            matches = []
            direct_wins_p1 = 0
            direct_losses_p1 = 0
        
        # Calculate Fargo-based win probabilities
        p1_fargo = p1.get("fargo_rating")
        p2_fargo = p2.get("fargo_rating")
        fargo_win_prob_p1 = calculate_fargo_win_probability(p1_fargo, p2_fargo)
        fargo_win_prob_p2 = calculate_fargo_win_probability(p2_fargo, p1_fargo)

        out: dict = {
            "operator": p1,
            "player2": p2,
            "head_to_head": {
                "direct_wins_p1": direct_wins_p1,
                "direct_losses_p1": direct_losses_p1,
                "fargo_win_probability_p1": fargo_win_prob_p1,
                "fargo_win_probability_p2": fargo_win_prob_p2,
                "common_opponents": [],
                "matches": matches,
            },
        }

        _FALLBACK_NARRATIVE = "AI summary is temporarily unavailable."
        try:
            from api.services.ollama_narratives import generate_matchup_narrative
            from api.services.ollama_client import is_ollama_enabled
            from api.services.player_narrative_cache import (
                get_cached_narrative,
                hash_overview_payload,
                h2h_narrative_cache_key,
                remember_narrative,
            )

            if is_ollama_enabled():
                # Limit matches for prompt size / stable hashing
                matches_for_llm = matches[:40]
                h2h_data = {
                    "operator_name": p1.get("name"),
                    "player2_name": p2.get("name"),
                    "operator": p1,
                    "player2": p2,
                    "head_to_head": {
                        "direct_wins_p1": direct_wins_p1,
                        "direct_losses_p1": direct_losses_p1,
                        "fargo_win_probability_p1": fargo_win_prob_p1,
                        "fargo_win_probability_p2": fargo_win_prob_p2,
                        "matches": matches_for_llm,
                    },
                }
                ckey = h2h_narrative_cache_key(player_id, opponent_id)
                payload_hash = hash_overview_payload(h2h_data)
                cached_text = get_cached_narrative(ckey, payload_hash)
                if cached_text is not None:
                    out["narrative"] = cached_text
                    out["narrative_unchanged"] = True
                else:
                    narrative = await generate_matchup_narrative(h2h_data)
                    if narrative and narrative.strip():
                        out["narrative"] = narrative.strip()
                        out["narrative_unchanged"] = False
                        remember_narrative(ckey, payload_hash, narrative.strip())
                    else:
                        out["narrative"] = _FALLBACK_NARRATIVE
                        out["narrative_unchanged"] = False
        except Exception as narr_err:
            logger.warning("Head-to-head narrative skipped: %s", narr_err)
            try:
                from api.services.ollama_client import is_ollama_enabled as _ioe

                if _ioe():
                    out["narrative"] = _FALLBACK_NARRATIVE
                    out["narrative_unchanged"] = False
            except Exception:
                pass

        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Head-to-head failed for %s vs %s: %s", player_id, opponent_id, e)
        msg = str(e).lower()
        if "database" in msg or "connection" in msg or "engine" in msg or "db" in msg or "unavailable" in msg:
            raise HTTPException(status_code=503, detail="Rankings database not available.") from e
        raise HTTPException(status_code=500, detail="Head-to-head comparison failed. Please try again.") from e
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                logger.warning("Error closing head-to-head connection: %s", e)
