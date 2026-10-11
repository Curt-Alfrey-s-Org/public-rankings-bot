"""
Test Center read-only mirrors: same response shapes as production rankings / tournaments / tournament-history,
using PostgresManager(engine=get_test_center_engine()) only.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from database import get_test_center_engine
from database.postgres_manager import PostgresManager
from api.routes.tournament_history import (
    REAL_TOURNAMENTS_WHERE_TH,
    LEADERBOARD_PAST_RESULTS_BUCKET_KEYS,
    _leaderboard_bucket_filter_sql,
    _LEADERBOARD_PAST_RESULTS_SELECT,
)
from api.models.tournament_models import (
    CurrentRankingResponse,
    HotStreakPlayerResponse,
    TournamentPerformanceResponse,
    TournamentTabCoverageResponse,
    TournamentTabCoverageListResponse,
)


def _stale_after_hours() -> int:
    try:
        value = int(os.getenv("RANKINGS_STALE_AFTER_HOURS", "48"))
        return max(1, value)
    except ValueError:
        return 48


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-center", tags=["test-center-views"])


def _tc_db() -> PostgresManager:
    return PostgresManager(engine=get_test_center_engine())


def _rankings_payload(db: PostgresManager, system: str, limit: int, offset: int, association: str, division: str, ranking_type: str) -> Dict[str, Any]:
    result = db.get_rankings_paginated(system, limit, offset)
    return {
        **result,
        "association": association,
        "division": division,
        "ranking_type": ranking_type,
    }


# --- Rankings mirrors ---


@router.get("/rankings/wpba-tournament-systems")
async def tc_wpba_tournament_systems():
    try:
        systems = _tc_db().get_wpba_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("test-center wpba-tournament-systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


@router.get("/rankings/wpa-men-tournament-systems")
async def tc_wpa_men_tournament_systems():
    try:
        systems = _tc_db().get_wpa_men_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("test-center wpa-men-tournament-systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


@router.get("/rankings/wpa-women-tournament-systems")
async def tc_wpa_women_tournament_systems():
    try:
        systems = _tc_db().get_wpa_women_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("test-center wpa-women-tournament-systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


@router.get("/rankings/wpba-women")
async def tc_wpba_women(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPBA_Women", limit, offset, "WPBA", "Women", "WPBA_Women")


@router.get("/rankings/wpa-women")
async def tc_wpa_women(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPA_Women", limit, offset, "WPA", "Women", "WPA_Women")


@router.get("/rankings/wpa-men")
async def tc_wpa_men(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPA_Men", limit, offset, "WPA", "Men", "WPA_Men")


@router.get("/rankings/wpa-heyball-men")
async def tc_wpa_heyball_men(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPA_Heyball_Men", limit, offset, "WPA", "Heyball Men", "WPA_Heyball_Men")


@router.get("/rankings/wpa-heyball-women")
async def tc_wpa_heyball_women(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPA_Heyball_Women", limit, offset, "WPA", "Heyball Women", "WPA_Heyball_Women")


@router.get("/rankings/wpa-artistic")
async def tc_wpa_artistic(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "WPA_Artistic", limit, offset, "WPA", "Artistic", "WPA_Artistic")


@router.get("/rankings/cp-9ball")
async def tc_cp_9ball(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "Competitors_Pool_9Ball", limit, offset, "CP", "9-Ball", "Competitors_Pool_9Ball")


@router.get("/rankings/cp-10ball")
async def tc_cp_10ball(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "Competitors_Pool_10Ball", limit, offset, "CP", "10-Ball", "Competitors_Pool_10Ball")


@router.get("/rankings/cp-8ball")
async def tc_cp_8ball(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "Competitors_Pool_8Ball", limit, offset, "CP", "8-Ball", "Competitors_Pool_8Ball")


@router.get("/rankings/cp-women-9ball")
async def tc_cp_women_9ball(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "Competitors_Pool_Women_9Ball", limit, offset, "CP", "Women 9-Ball", "Competitors_Pool_Women_9Ball")


@router.get("/rankings/cp-men-9ball")
async def tc_cp_men_9ball(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return _rankings_payload(db, "Competitors_Pool_Men_9Ball", limit, offset, "CP", "Men 9-Ball", "Competitors_Pool_Men_9Ball")


@router.get("/rankings/by-system/{ranking_system:path}")
async def tc_by_system(ranking_system: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = _tc_db()
    return db.get_rankings_paginated(ranking_system, limit, offset)


@router.get("/rankings/last-update")
async def tc_last_update():
    try:
        db = _tc_db()
        wpba_update = db.get_last_snapshot_date("WPBA_Women")
        wpa_update = db.get_last_snapshot_date("WPA_Women")
        stale_after_hours = _stale_after_hours()
        return {
            "wpba": wpba_update,
            "wpa": wpa_update,
            "staleness": {
                "threshold_hours": stale_after_hours,
                "wpba": db.get_staleness_info("WPBA_Women", stale_after_hours),
                "wpa": db.get_staleness_info("WPA_Women", stale_after_hours),
            },
        }
    except Exception as e:
        logger.error("test-center last-update: %s", e, exc_info=True)
        stale_after_hours = _stale_after_hours()
        return {
            "wpba": None,
            "wpa": None,
            "degraded": True,
            "error": str(e)[:200],
            "staleness": {
                "threshold_hours": stale_after_hours,
                "wpba": {"stale": True, "reason": "unavailable"},
                "wpa": {"stale": True, "reason": "unavailable"},
            },
        }


# --- Tournaments mirrors (subset) ---


@router.get("/tournaments/rankings/current", response_model=List[CurrentRankingResponse])
async def tc_current_rankings(
    limit: Optional[int] = None,
    system: Optional[str] = Query(None),
):
    try:
        db = _tc_db()
        rankings = db.get_leaderboard_from_rankings(limit=limit, ranking_system=system)
        return [CurrentRankingResponse(**r) for r in rankings]
    except Exception as e:
        logger.error("test-center rankings/current: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tournaments/completed-results")
async def tc_completed_results(limit: int = Query(20, ge=1, le=100)):
    """Completed test tournaments from tournament_history (not director tournaments table)."""
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT th.tournament_id, th.name AS tournament_name, th.date AS tournament_date,
                   th.champion AS first_place_name, th.runner_up AS second_place_name
            FROM tournament_history th
            WHERE th.status = 'completed' AND th.date IS NOT NULL
            ORDER BY th.date DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        tournaments = []
        for r in rows:
            tournaments.append(
                {
                    "tournament_id": r[0],
                    "tournament_name": r[1],
                    "tournament_date": str(r[2]) if r[2] else "",
                    "first_place_name": r[3],
                    "second_place_name": r[4],
                    "third_place_name": None,
                }
            )
        return {"tournaments": tournaments}
    finally:
        conn.close()


@router.get("/tournaments/hot-streak", response_model=List[HotStreakPlayerResponse])
async def tc_hot_streak(
    lookback: int = Query(3, ge=2, le=6),
    min_tournaments: int = Query(3, ge=2, le=6),
    limit: Optional[int] = Query(None, ge=1, le=100),
    association: Optional[str] = None,
):
    try:
        db = _tc_db()
        players = db.get_hot_streak_players(
            lookback=lookback, min_tournaments=min_tournaments, limit=limit, association=association
        )
        return [HotStreakPlayerResponse(**r) for r in players]
    except Exception as e:
        logger.error("test-center hot-streak: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tournaments/hot-streak/fargo", response_model=List[HotStreakPlayerResponse])
async def tc_hot_streak_fargo(
    lookback: int = Query(3, ge=2, le=6),
    min_tournaments: int = Query(3, ge=2, le=6),
    limit: Optional[int] = Query(None, ge=1, le=100),
    association: Optional[str] = None,
):
    try:
        db = _tc_db()
        players = db.get_fargo_hot_streak_players(
            lookback=lookback, min_tournaments=min_tournaments, limit=limit, association=association
        )
        return [HotStreakPlayerResponse(**r) for r in players]
    except Exception as e:
        logger.error("test-center hot-streak/fargo: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tournaments")
async def tc_list_tournaments(status_filter: Optional[str] = None):
    """Director tournaments list — empty in Test Center (test events are in tournament_history only)."""
    return []


@router.get("/tournaments/history/{tournament_id}/performance", response_model=TournamentPerformanceResponse)
async def tc_tournament_performance(tournament_id: str):
    try:
        db = _tc_db()
        performance = db.get_tournament_performance(tournament_id=tournament_id)
        if not performance:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        return TournamentPerformanceResponse(**performance)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("test-center performance: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tournaments/history/{tournament_id}/tab-coverage", response_model=TournamentTabCoverageResponse)
async def tc_tab_coverage(
    tournament_id: str,
    include_payload: bool = Query(False),
):
    """No archived tab files in Test Center — return empty coverage with valid shape."""
    return TournamentTabCoverageResponse(
        tournament_id=tournament_id,
        tournament_name=None,
        tab_overview={} if include_payload else None,
    )


@router.get("/tournaments/history/tab-coverage", response_model=TournamentTabCoverageListResponse)
async def tc_tab_coverage_list(
    limit: int = Query(300, ge=1, le=500),
    year: Optional[int] = None,
    association: Optional[str] = None,
    incomplete_only: bool = False,
):
    return TournamentTabCoverageListResponse(total=0, items=[])


# --- Tournament history mirrors ---


def _th_rows_to_dicts(cursor, rows):
    if not rows:
        return []
    colnames = [d[0] for d in cursor.description]
    return [dict(zip(colnames, row)) for row in rows]


@router.get("/tournament-history/years")
async def tc_th_years():
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT year FROM tournament_history
            WHERE year IS NOT NULL
            ORDER BY year DESC
            """
        )
        years = [r[0] for r in cur.fetchall() if r[0] is not None]
        return {"success": True, "years": years}
    finally:
        conn.close()


@router.get("/tournament-history/tournaments")
async def tc_th_tournaments(
    year: Optional[int] = None,
    association: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
):
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        query = (
            "SELECT th.id, th.tournament_id, th.name, th.year, th.date, th.location, th.association, "
            "th.championship, th.prize_pool, th.status "
            "FROM tournament_history th WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE"
            + REAL_TOURNAMENTS_WHERE_TH
        )
        params: List[Any] = []
        if year:
            query += " AND th.year = %s"
            params.append(year)
        if association:
            query += " AND th.association ILIKE %s"
            params.append(f"%{association}%")
        query += " ORDER BY th.date DESC NULLS LAST LIMIT %s"
        params.append(limit)
        cur.execute(query, tuple(params))
        tournaments = _th_rows_to_dicts(cur, cur.fetchall())
        return {"success": True, "count": len(tournaments), "tournaments": tournaments}
    finally:
        conn.close()


@router.get("/tournament-history/tournaments/results-counts")
async def tc_th_results_counts(
    tournament_ids: str = Query(..., description="Comma-separated tournament_ids"),
):
    """Bulk results-count lookup for tournament cards (mirrors production route)."""
    ids = [tid.strip() for tid in tournament_ids.split(",") if tid.strip()]
    if not ids:
        return {"counts": {}}
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"SELECT tournament_id, COUNT(*) AS cnt FROM tournament_results "
            f"WHERE tournament_id IN ({placeholders}) GROUP BY tournament_id",
            ids,
        )
        return {"counts": {row[0]: row[1] for row in cur.fetchall()}}
    except Exception as e:
        logger.error("test-center results-counts: %s", e, exc_info=True)
        return {"counts": {}}
    finally:
        conn.close()


@router.get("/tournament-history/tournaments/{tournament_id}")
async def tc_th_detail(tournament_id: str):
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tournament_history WHERE tournament_id = %s", (tournament_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tournament not found")
        colnames = [d[0] for d in cur.description]
        tournament = dict(zip(colnames, row))
        cur.execute(
            """
            SELECT id, tournament_id, player_name, placement, points, notes
            FROM tournament_results WHERE tournament_id = %s ORDER BY placement ASC
            """,
            (tournament_id,),
        )
        results = _th_rows_to_dicts(cur, cur.fetchall())
        return {"success": True, "tournament": tournament, "results": results, "total_participants": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("test-center th detail: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@router.get("/tournament-history/leaderboard-results-by-association")
async def tc_leaderboard_results_by_association(limit_per_association: int = Query(3, ge=1, le=10)):
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()

        def _name(d: dict, key: str):
            v = d.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()
            low = key.lower()
            if low != key:
                v = d.get(low)
                if v is not None and str(v).strip():
                    return str(v).strip()
            return None

        ordered: Dict[str, List[Dict[str, Any]]] = {}
        for bucket in LEADERBOARD_PAST_RESULTS_BUCKET_KEYS:
            frag, frag_params = _leaderboard_bucket_filter_sql(bucket)
            query = (
                _LEADERBOARD_PAST_RESULTS_SELECT + REAL_TOURNAMENTS_WHERE_TH + frag + """
            ORDER BY th.date DESC NULLS LAST, th.tournament_id DESC
            LIMIT %s
            """
            )
            params = list(frag_params) + [limit_per_association]
            cur.execute(query, params)
            rows = _th_rows_to_dicts(cur, cur.fetchall())
            if not rows:
                continue
            ordered[bucket] = [
                {
                    "tournament_id": r.get("tournament_id"),
                    "tournament_name": r.get("tournament_name") or r.get("name"),
                    "tournament_date": str(r.get("tournament_date") or r.get("date") or ""),
                    "first_place_name": _name(r, "first_place_name"),
                    "second_place_name": _name(r, "second_place_name"),
                    "third_place_name": _name(r, "third_place_name"),
                }
                for r in rows
            ]
        return {"success": True, "by_association": ordered}
    except Exception as e:
        logger.error("test-center leaderboard-results-by-association: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@router.get("/tournament-history/players/{player_name}/history")
async def tc_player_history(player_name: str):
    conn = _tc_db().get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tr.id, tr.tournament_id, tr.player_name, tr.placement, tr.points,
                   th.name AS tournament_name, th.year, th.championship, th.date, th.association, th.location
            FROM tournament_results tr
            JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE LOWER(tr.player_name) = LOWER(%s)
            ORDER BY th.date DESC NULLS LAST, th.year DESC NULLS LAST, th.name ASC
            """,
            (player_name,),
        )
        results = _th_rows_to_dicts(cur, cur.fetchall())
        if not results:
            return {
                "success": True,
                "player_name": player_name,
                "tournament_results": [],
                "statistics": {
                    "total_tournaments": 0,
                    "first_place_finishes": 0,
                    "top_3_finishes": 0,
                    "average_placement": None,
                },
                "narrative": "No tournament history in Test Center for this player.",
                "narrative_unchanged": True,
            }
        first_place = sum(1 for r in results if r.get("placement") == 1)
        top_3 = sum(1 for r in results if r.get("placement") and r["placement"] <= 3)
        placements = [r["placement"] for r in results if r.get("placement")]
        avg_placement = sum(placements) / len(placements) if placements else None
        return {
            "success": True,
            "player_name": player_name,
            "tournament_results": results,
            "statistics": {
                "total_tournaments": len(results),
                "first_place_finishes": first_place,
                "top_3_finishes": top_3,
                "average_placement": round(avg_placement, 2) if avg_placement else None,
            },
            "narrative_unchanged": True,
        }
    except Exception as e:
        logger.error("test-center player history: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()
