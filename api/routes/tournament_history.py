"""
Tournament History API Routes
Endpoints for accessing tournament history and rankings.
Uses Postgres (get_database_manager) per project standards.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Any, Dict, Tuple
from pathlib import Path
from datetime import datetime, date
import logging
import os
import asyncio
import json
import tarfile
import re
import hashlib
from html import unescape

import httpx

from api.auth import require_admin, require_super_admin
from database import get_database_manager, get_engine
from api.services.cache_store import (
    get_cached_json,
    invalidate_cache,
    make_cache_key,
    set_cached_json,
    DEFAULT_TTL_SECONDS,
    DEFAULT_STALE_TTL_SECONDS,
)
from api.services.live_log import (
    register_job,
    start_background_action,
    stream_log_response,
)
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed

# Lazy engine initialization
engine = get_engine()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tournament-history", tags=["tournament-history"])

# Live-log job IDs used by this module. Registered at import time so the GET stream
# handler always finds the job entry regardless of POST ordering across workers.
_REFRESH_UPCOMING_JOB = "refresh_upcoming_events"
_REFRESH_PAST_JOB = "refresh_past_tournaments"
register_job(_REFRESH_UPCOMING_JOB, "Refresh upcoming events")
register_job(_REFRESH_PAST_JOB, "Refresh past tournaments")

# Single source of truth: exclude rankings snapshots and news/events from "real" tournament list.
# Used by both Tournament History list and Leaderboard so they show the same set.
REAL_TOURNAMENTS_WHERE = (
    " AND (tournament_id IS NULL OR tournament_id NOT LIKE 'rankings_snapshot%%')"
    " AND EXISTS (SELECT 1 FROM tournament_results WHERE tournament_results.tournament_id = tournament_history.tournament_id)"
    " AND (name IS NULL OR ("
    " name NOT LIKE '%% Rankings (%%'"
    " AND name NOT ILIKE '%% News%%'"
    " AND name NOT ILIKE '%% Events'"
    " AND LOWER(TRIM(name)) NOT IN ('wpba events', 'latest wpa news', 'wpa news', 'wpba news')"
    " ))"
)
# Same filter with table alias for queries that use FROM tournament_history th
REAL_TOURNAMENTS_WHERE_TH = (
    " AND (th.tournament_id IS NULL OR th.tournament_id NOT LIKE 'rankings_snapshot%%')"
    " AND EXISTS (SELECT 1 FROM tournament_results WHERE tournament_results.tournament_id = th.tournament_id)"
    " AND (th.name IS NULL OR ("
    " th.name NOT LIKE '%% Rankings (%%'"
    " AND th.name NOT ILIKE '%% News%%'"
    " AND th.name NOT ILIKE '%% Events'"
    " AND LOWER(TRIM(th.name)) NOT IN ('wpba events', 'latest wpa news', 'wpa news', 'wpba news')"
    " ))"
)

# Future tournament data - now stored in PostgreSQL
# (previously in SQLite, migrated via database/migrate_*.py scripts)
from project_root import PROJECT_ROOT


def _get_conn():
    """Get database connection (Postgres)."""
    db = get_database_manager()
    return db.get_connection()


def _close_conn(conn) -> None:
    """Safely close connection: rollback any failed transaction, then close."""
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception as e:
        logger.debug("Rollback on close (non-fatal): %s", e)
    try:
        conn.close()
    except Exception as e:
        logger.warning("Failed to close DB connection: %s", e)


def _row_to_dict(cursor: Any, row: Any) -> Optional[Dict[str, Any]]:
    """Convert a DB-API row into a dict (handles tuple or mapping rows)."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _rows_to_dicts(cursor: Any, rows: List[Any]) -> List[Dict[str, Any]]:
    """Convert a list of DB-API rows into dicts."""
    return [_row_to_dict(cursor, row) for row in rows if row is not None]


# Match leaderboard / list filters: women's events in tournament title (Postgres ~* / Python re).
# Avoid POSIX \\b in the SQL branch — PostgreSQL POSIX regexes treat \\b differently than PCRE.
_TOURNAMENT_NAME_WOMEN_RE = (
    r"women|woman's|womens|wpa women's|women's|ladies|lady's|female"
)
_WOMEN_IN_TOURNAMENT_NAME_RE = re.compile(_TOURNAMENT_NAME_WOMEN_RE, re.IGNORECASE)


def _tournament_list_association_sql(association: Optional[str]) -> Tuple[str, List[Any]]:
    """SQL AND clauses for tournament list when UI sends display labels (WPA Men, …).

    ``tournament_history.association`` is usually only ``WPA`` or ``WPBA``; ILIKE
    ``WPA Men`` matches nothing. Map to name-based filters instead.
    """
    if not association or not association.strip():
        return "", []
    a = association.strip()
    # WPBA events are sometimes stored with association WPA but "WPBA" in the title.
    _wpba_in_name = "LOWER(COALESCE(th.name, '')) LIKE '%%wpba%%'"
    not_wpba_local = (
        " AND COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') NOT ILIKE 'WPBA'"
        " AND COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') NOT ILIKE 'LOCAL'"
        f" AND NOT ({_wpba_in_name})"
    )
    if a == "WPBA":
        return (
            " AND (th.association ILIKE %s OR " + _wpba_in_name + ")",
            ["WPBA"],
        )
    if a == "Local":
        return " AND 1=0", []
    if a == "WPA Men":
        return (
            not_wpba_local
            + " AND LOWER(th.name) NOT LIKE '%%heyball%%'"
            + " AND LOWER(th.name) NOT LIKE '%%artistic%%'"
            + " AND th.name !~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if a == "WPA Women":
        return (
            not_wpba_local
            + " AND LOWER(th.name) NOT LIKE '%%heyball%%'"
            + " AND LOWER(th.name) NOT LIKE '%%artistic%%'"
            + " AND th.name ~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if a == "Heyball":
        return (
            " AND (LOWER(th.name) LIKE '%%heyball%%' OR UPPER(TRIM(th.association)) = 'HEYBALL')",
            [],
        )
    if a == "WPA Artistic":
        return " AND LOWER(th.name) LIKE '%%artistic%%'", []
    return " AND th.association ILIKE %s", [a]


def _upcoming_event_natural_key(event: Dict[str, Any]) -> str:
    """
    Stable natural key for dedupe across archives/live/manual sources.
    DB uses this same key to enforce uniqueness.
    """
    event_date = event.get("event_date") or event.get("start_date") or event.get("end_date") or ""
    raw = "|".join([
        str(event.get("event_id") or "").strip().lower(),
        str(event.get("name") or "").strip().lower(),
        str(event_date),
        str(event.get("association") or "").strip().lower(),
        str(event.get("url") or "").strip(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _refresh_cache_sync(cache_key: str, fetch_fn, ttl_seconds: int, stale_ttl_seconds: int) -> None:
    """Refresh cache synchronously with fresh data."""
    data = fetch_fn()
    set_cached_json(cache_key, data, ttl_seconds=ttl_seconds, stale_ttl_seconds=stale_ttl_seconds)


async def _refresh_cache_async(cache_key: str, fetch_fn, ttl_seconds: int, stale_ttl_seconds: int) -> None:
    """Refresh cache in executor to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _refresh_cache_sync, cache_key, fetch_fn, ttl_seconds, stale_ttl_seconds)


def _schedule_cache_refresh(cache_key: str, fetch_fn, ttl_seconds: int, stale_ttl_seconds: int) -> None:
    """Schedule an async cache refresh when stale data was served."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_refresh_cache_async(cache_key, fetch_fn, ttl_seconds, stale_ttl_seconds))
    except RuntimeError:
        _refresh_cache_sync(cache_key, fetch_fn, ttl_seconds, stale_ttl_seconds)


def _fetch_tournaments_from_view(
    cursor: Any,
    year: Optional[int],
    association: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    """Fetch real tournaments only (excludes future, rankings snapshots, and news/events). Same filter as leaderboard."""
    # Use alias 'th' so REAL_TOURNAMENTS_WHERE_TH correlates EXISTS correctly
    query = (
        "SELECT th.id, th.tournament_id, th.name, th.year, th.date, th.location, th.association, th.championship, th.prize_pool, th.status "
        "FROM mv_tournament_history_recent th WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE"
        + REAL_TOURNAMENTS_WHERE_TH
    )
    params: List[Any] = []
    if year:
        query += " AND year = %s"
        params.append(year)
    if association:
        assoc_sql, assoc_params = _tournament_list_association_sql(association)
        query += assoc_sql
        params.extend(assoc_params)
    query += " ORDER BY date DESC NULLS LAST, year DESC NULLS LAST, id DESC NULLS LAST, name ASC LIMIT %s"
    params.append(limit)
    cursor.execute(query, params)
    return _rows_to_dicts(cursor, cursor.fetchall())


def _build_tournaments_payload(
    year: Optional[int],
    association: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    """Build tournaments payload for cache and endpoint responses. Excludes future tournaments."""
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        try:
            tournaments = _fetch_tournaments_from_view(cursor, year, association, limit)
        except Exception as e:
            logger.warning("Materialized view fetch failed; falling back to base table query: %s", e)
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.warning("Rollback failed after MV-to-base-table switch: %s", rollback_error)
            query = (
                "SELECT th.id, th.tournament_id, th.name, th.year, th.date, th.location, th.association, th.championship, th.prize_pool, th.status "
                "FROM tournament_history th WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE"
                + REAL_TOURNAMENTS_WHERE_TH
            )
            params: List[Any] = []
            if year:
                query += " AND th.year = %s"
                params.append(year)
            if association:
                assoc_sql, assoc_params = _tournament_list_association_sql(association)
                query += assoc_sql
                params.extend(assoc_params)
            query += " ORDER BY th.date DESC NULLS LAST, th.year DESC NULLS LAST, th.id DESC NULLS LAST, th.name ASC LIMIT %s"
            params.append(limit)
            cursor.execute(query, params)
            tournaments = _rows_to_dicts(cursor, cursor.fetchall())
        return {"success": True, "count": len(tournaments), "tournaments": tournaments}
    finally:
        _close_conn(conn)


def build_tournament_cache_payloads() -> Dict[str, Any]:
    """Warm tournament cache for common list views."""
    limits = [50, 100]
    summary: Dict[str, Any] = {"status": "ok", "entries": 0}
    for limit in limits:
        cache_key = make_cache_key("tournament-history", "tournaments", "year:all", "association:all", f"limit:{limit}")
        payload = _build_tournaments_payload(None, None, limit)
        set_cached_json(cache_key, payload)
        summary["entries"] += 1
    return summary


@router.get("/tournaments")
async def get_tournaments(
    year: Optional[int] = Query(None),
    association: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get tournament history
    - year: Filter by year (2022-2025)
    - association: Filter by WPBA, WPA, or Heyball (kept separate to avoid mixing data)
    """
    try:
        cache_key = make_cache_key(
            "tournament-history",
            "tournaments",
            f"year:{year or 'all'}",
            f"association:{association or 'all'}",
            f"limit:{limit}",
        )
        cached = get_cached_json(cache_key, allow_stale=True)
        if cached.hit:
            if cached.is_stale:
                _schedule_cache_refresh(
                    cache_key,
                    lambda: _build_tournaments_payload(year, association, limit),
                    DEFAULT_TTL_SECONDS,
                    DEFAULT_STALE_TTL_SECONDS,
                )
            return cached.data

        payload = _build_tournaments_payload(year, association, limit)
        set_cached_json(cache_key, payload)
        return payload
    except Exception as e:
        logger.error(f"Error fetching tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/points-by-name")
async def get_points_by_tournament_name(name: str = Query(..., min_length=1)):
    """
    Return points structure from the most recent same-named tournament in history.
    Used by Tournament Wizard Step 2 to prefill points (editable).
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tournament_id FROM tournament_history
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
            ORDER BY date DESC NULLS LAST, year DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (name.strip(),),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
        if not row:
            return {"success": True, "points_structure": {}, "source": None}

        tid = row["tournament_id"]
        cursor.execute(
            """
            SELECT placement, MAX(points) as points FROM tournament_results
            WHERE tournament_id = %s AND placement IS NOT NULL
            GROUP BY placement ORDER BY placement
            """,
            (tid,),
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        points_structure = {str(r["placement"]): int(r["points"]) if r["points"] is not None else 0 for r in rows}
        return {"success": True, "points_structure": points_structure, "source": tid}
    except Exception as e:
        logger.error(f"Error fetching points by name: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/tournaments/results-counts")
async def get_tournament_results_counts(
    tournament_ids: str = Query(..., description="Comma-separated tournament_ids"),
):
    """Bulk results-count lookup for tournament cards (avoids N+1)."""
    conn = None
    try:
        ids = [tid.strip() for tid in tournament_ids.split(",") if tid.strip()]
        if not ids:
            return {"counts": {}}
        conn = _get_conn()
        cursor = conn.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT tournament_id, COUNT(*) AS cnt "
            f"FROM tournament_results WHERE tournament_id IN ({placeholders}) "
            f"GROUP BY tournament_id",
            ids,
        )
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        return {"counts": counts}
    except Exception as e:
        logger.error("Error fetching results counts: %s", e)
        return {"counts": {}}
    finally:
        _close_conn(conn)


@router.get("/tournaments/{tournament_id}")
async def get_tournament_details(tournament_id: str):
    """
    Get details for a specific tournament
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        
        # Get tournament details
        cursor.execute("""
            SELECT * FROM tournament_history WHERE tournament_id = %s
        """, (tournament_id,))
        
        tournament = _row_to_dict(cursor, cursor.fetchone()) or {}
        
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Get tournament results/rankings (include DP-enriched fields when present)
        try:
            cursor.execute("""
                SELECT id, tournament_id, player_name, placement, points, notes,
                       seed, race_to, current_round, player_status, is_eliminated
                FROM tournament_results
                WHERE tournament_id = %s
                ORDER BY placement ASC NULLS LAST, player_name ASC
            """, (tournament_id,))
        except Exception:
            cursor.execute("""
                SELECT id, tournament_id, player_name, placement, points, notes
                FROM tournament_results
                WHERE tournament_id = %s
                ORDER BY placement ASC
            """, (tournament_id,))

        results = _rows_to_dicts(cursor, cursor.fetchall())

        return {
            "success": True,
            "tournament": tournament,
            "results": results,
            "total_participants": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tournament details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/tournaments/{tournament_id}/matches")
async def get_tournament_history_matches(
    tournament_id: str,
    limit: int = Query(500, ge=1, le=2000),
):
    """List harvested bracket/match rows for a history tournament (read-only drawer)."""
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM tournament_history WHERE tournament_id = %s",
            (tournament_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Tournament not found")
        cursor.execute(
            """
            SELECT id, tournament_id, operator_name, player2_name,
                   operator_score, player2_score, winner_name,
                   round_num, match_num, match_date, notes, created_at
            FROM tournament_history_matches
            WHERE tournament_id = %s
            ORDER BY match_num NULLS LAST, id ASC
            LIMIT %s
            """,
            (tournament_id, limit),
        )
        matches = _rows_to_dicts(cursor, cursor.fetchall())
        return {
            "success": True,
            "tournament_id": tournament_id,
            "matches": matches,
            "total": len(matches),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching history matches for %s: %s", tournament_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/leaderboard-results")
async def get_leaderboard_results(limit: int = Query(15, ge=1, le=100)):
    """
    Get recent tournament history with 1st, 2nd, 3rd place names for leaderboard display.
    From tournament_results: placement 1 = first, 2 = second, 3 = third.
    Returns at most one row per tournament event (name+date); when multiple divisions exist
    (e.g. WPA, WPA Women, WPA Men), keeps one per PostgreSQL DISTINCT ON.
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        # Same real-tournaments filter as Tournament History list (single hierarchy).
        # DISTINCT ON (LOWER(TRIM(name)), date) deduplicates multi-division events per PostgreSQL docs.
        # ORDER BY must match DISTINCT ON columns first; subquery reorders by date DESC and applies LIMIT.
        cursor.execute(
            """
            SELECT tournament_id, tournament_name, tournament_date, association,
                   first_place_name, second_place_name, third_place_name
            FROM (
                SELECT DISTINCT ON (LOWER(TRIM(th.name)), th.date)
                    th.tournament_id,
                    th.name AS tournament_name,
                    th.date AS tournament_date,
                    th.association,
                    (SELECT tr1.player_name FROM tournament_results tr1
                     WHERE tr1.tournament_id = th.tournament_id AND tr1.placement = 1
                     LIMIT 1) AS first_place_name,
                    (SELECT tr2.player_name FROM tournament_results tr2
                     WHERE tr2.tournament_id = th.tournament_id AND tr2.placement = 2
                     LIMIT 1) AS second_place_name,
                    (SELECT tr3.player_name FROM tournament_results tr3
                     WHERE tr3.tournament_id = th.tournament_id AND tr3.placement = 3
                     LIMIT 1) AS third_place_name
                FROM tournament_history th
                WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE
                """
            + REAL_TOURNAMENTS_WHERE_TH
            + """
                ORDER BY LOWER(TRIM(th.name)), th.date DESC, th.association NULLS LAST
            ) sub
            ORDER BY tournament_date DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        # Prefer explicit keys; PostgreSQL may return lowercase column names
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
        tournaments = []
        for r in rows:
            tournaments.append({
                "tournament_id": r.get("tournament_id"),
                "tournament_name": r.get("tournament_name") or r.get("name"),
                "tournament_date": str(r.get("tournament_date") or r.get("date") or ""),
                "association": r.get("association"),
                "first_place_name": _name(r, "first_place_name"),
                "second_place_name": _name(r, "second_place_name"),
                "third_place_name": _name(r, "third_place_name"),
            })
        return {"success": True, "tournaments": tournaments}
    except Exception as e:
        logger.error("Error fetching leaderboard results from tournament history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


# One SQL query per bucket (newest-first, LIMIT N each). Avoids starving sparse buckets when
# scanning only the latest M rows globally. "WPA Heyball" is a legacy UI key only (no query —
# Men/Women cover Heyball; a combined bucket would duplicate rows).
LEADERBOARD_PAST_RESULTS_BUCKET_KEYS = (
    "WPBA",
    "WPA Men",
    "WPA Women",
    "WPA Heyball Men",
    "WPA Heyball Women",
    "WPA Artistic",
)


def _leaderboard_bucket_filter_sql(bucket_key: str) -> Tuple[str, List[Any]]:
    """WHERE fragments for one Leaderboard section (must match tournament list filters)."""
    _wpba_in_name = "LOWER(COALESCE(th.name, '')) LIKE '%%wpba%%'"
    _heyball = (
        "(LOWER(COALESCE(th.name, '')) LIKE '%%heyball%%' "
        "OR UPPER(TRIM(COALESCE(th.association, ''))) = 'HEYBALL')"
    )
    not_wpba_local_no_wpba_name = (
        "COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') NOT ILIKE 'WPBA'"
        " AND COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') NOT ILIKE 'LOCAL'"
        f" AND NOT ({_wpba_in_name})"
    )

    if bucket_key == "WPBA":
        return (
            " AND (th.association ILIKE %s OR " + _wpba_in_name + ")",
            ["WPBA"],
        )
    if bucket_key == "WPA Men":
        return (
            " AND " + not_wpba_local_no_wpba_name
            + " AND LOWER(COALESCE(th.name, '')) NOT LIKE '%%heyball%%'"
            + " AND LOWER(COALESCE(th.name, '')) NOT LIKE '%%artistic%%'"
            + " AND th.name !~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if bucket_key == "WPA Women":
        return (
            " AND " + not_wpba_local_no_wpba_name
            + " AND LOWER(COALESCE(th.name, '')) NOT LIKE '%%heyball%%'"
            + " AND LOWER(COALESCE(th.name, '')) NOT LIKE '%%artistic%%'"
            + " AND th.name ~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if bucket_key == "WPA Heyball Men":
        return (
            " AND " + _heyball + " AND th.name !~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if bucket_key == "WPA Heyball Women":
        return (
            " AND " + _heyball + " AND th.name ~* %s",
            [_TOURNAMENT_NAME_WOMEN_RE],
        )
    if bucket_key == "WPA Artistic":
        return " AND LOWER(COALESCE(th.name, '')) LIKE '%%artistic%%'", []
    raise ValueError(f"unknown leaderboard bucket: {bucket_key}")


_LEADERBOARD_PAST_RESULTS_SELECT = """
            SELECT
                th.tournament_id,
                th.name AS tournament_name,
                th.date AS tournament_date,
                (SELECT tr1.player_name FROM tournament_results tr1
                 WHERE tr1.tournament_id = th.tournament_id AND tr1.placement = 1 LIMIT 1) AS first_place_name,
                (SELECT tr2.player_name FROM tournament_results tr2
                 WHERE tr2.tournament_id = th.tournament_id AND tr2.placement = 2 LIMIT 1) AS second_place_name,
                (SELECT tr3.player_name FROM tournament_results tr3
                 WHERE tr3.tournament_id = th.tournament_id AND tr3.placement = 3 LIMIT 1) AS third_place_name
            FROM tournament_history th
            WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE
"""


@router.get("/leaderboard-results-by-association")
async def get_leaderboard_results_by_association(limit_per_association: int = Query(3, ge=1, le=10)):
    """
    Get top N most recent tournaments per association for Leaderboard display.
    Single source: tournament_history + tournament_results.
    Returns { "by_association": { "WPBA": [...], "WPA Men": [...], ... } }.

    Uses one query per display bucket so sparse sections (e.g. WPA Women) are not
    starved when the latest 400 overall rows are mostly men's opens.
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()

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
            query = _LEADERBOARD_PAST_RESULTS_SELECT + REAL_TOURNAMENTS_WHERE_TH + frag + """
            ORDER BY th.date DESC NULLS LAST, th.tournament_id DESC
            LIMIT %s
            """
            params = list(frag_params) + [limit_per_association]
            cursor.execute(query, params)
            rows = _rows_to_dicts(cursor, cursor.fetchall())
            if not rows:
                continue
            ordered[bucket] = [
                {
                    "tournament_id": r.get("tournament_id"),
                    "tournament_name": r.get("tournament_name") or r.get("name"),
                    "tournament_date": str(r.get("tournament_date") or r.get("date") or ""),
                    "association": bucket,
                    "first_place_name": _name(r, "first_place_name"),
                    "second_place_name": _name(r, "second_place_name"),
                    "third_place_name": _name(r, "third_place_name"),
                }
                for r in rows
            ]

        return {"success": True, "by_association": ordered}
    except Exception as e:
        logger.error("Error fetching leaderboard results by association: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/players/{player_name}/history")
async def get_player_tournament_history(player_name: str):
    """
    Get tournament history for a specific player
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        
        # Get tournament results for player
        cursor.execute("""
            SELECT 
                tr.id,
                tr.tournament_id,
                tr.player_name, 
                tr.placement, 
                tr.points,
                th.name as tournament_name,
                th.year,
                th.championship,
                th.date,
                th.association,
                th.location
            FROM tournament_results tr
            JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE LOWER(tr.player_name) = LOWER(%s)
            ORDER BY th.date DESC NULLS LAST, th.year DESC NULLS LAST, th.name ASC
        """, (player_name,))
        
        results = _rows_to_dicts(cursor, cursor.fetchall())
        
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
                "narrative": "No tournament history found for this player in the archive.",
                "narrative_unchanged": False,
            }

        # Calculate statistics
        first_place = sum(1 for r in results if r["placement"] == 1)
        top_3 = sum(1 for r in results if r["placement"] and r["placement"] <= 3)
        avg_placement = sum(r["placement"] for r in results if r["placement"]) / len(
            [r for r in results if r["placement"]]
        )

        out: Dict[str, Any] = {
            "success": True,
            "player_name": player_name,
            "tournament_results": results,
            "statistics": {
                "total_tournaments": len(results),
                "first_place_finishes": first_place,
                "top_3_finishes": top_3,
                "average_placement": round(avg_placement, 2) if avg_placement else None,
            },
        }

        _FALLBACK_NARRATIVE = "AI summary is temporarily unavailable."
        try:
            from api.services.ollama_narratives import generate_tournament_history_narrative
            from api.services.ollama_client import is_ollama_enabled
            from api.services.player_narrative_cache import (
                get_cached_narrative,
                hash_overview_payload,
                remember_narrative,
                tournament_history_narrative_cache_key,
            )

            if is_ollama_enabled():
                canonical = (results[0].get("player_name") or player_name or "").strip()
                results_trim = results[:35]
                llm_payload: Dict[str, Any] = {
                    "player_name": canonical,
                    "statistics": out["statistics"],
                    "tournament_results": results_trim,
                }
                ckey = tournament_history_narrative_cache_key(canonical)
                payload_hash = hash_overview_payload(llm_payload)
                cached_text = get_cached_narrative(ckey, payload_hash)
                if cached_text is not None:
                    out["narrative"] = cached_text
                    out["narrative_unchanged"] = True
                else:
                    narrative = await generate_tournament_history_narrative(llm_payload)
                    if narrative and narrative.strip():
                        out["narrative"] = narrative.strip()
                        out["narrative_unchanged"] = False
                        remember_narrative(ckey, payload_hash, narrative.strip())
                    else:
                        out["narrative"] = _FALLBACK_NARRATIVE
                        out["narrative_unchanged"] = False
        except Exception as narr_err:
            logger.warning("Tournament history narrative skipped: %s", narr_err)
            try:
                from api.services.ollama_client import is_ollama_enabled as _ioe

                if _ioe():
                    out["narrative"] = _FALLBACK_NARRATIVE
                    out["narrative_unchanged"] = False
            except Exception:
                pass

        return out
    except Exception as e:
        logger.error(f"Error fetching player tournament history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/statistics")
async def get_tournament_statistics(year: Optional[int] = Query(None)):
    """
    Get overall tournament statistics (excludes future tournaments)
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        
        # Get tournament counts (excluding future tournaments)
        query = "SELECT association, COUNT(*) as count FROM tournament_history WHERE date IS NOT NULL AND date <= CURRENT_DATE"
        params = []
        
        if year:
            query += " AND year = %s"
            params.append(year)
        
        query += " GROUP BY association"
        cursor.execute(query, params)
        assoc_rows = _rows_to_dicts(cursor, cursor.fetchall())
        association_counts = {row["association"]: row["count"] for row in assoc_rows}
        
        # Get years covered (excluding future tournaments)
        cursor.execute("SELECT DISTINCT year FROM tournament_history WHERE date IS NOT NULL AND date <= CURRENT_DATE ORDER BY year DESC")
        years = [row[0] for row in cursor.fetchall()]
        
        # Get total players who participated in historical tournaments
        cursor.execute("""
            SELECT COUNT(DISTINCT player_name) as total_players FROM tournament_results tr
            INNER JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE th.date IS NOT NULL AND th.date <= CURRENT_DATE
        """)
        total_players = cursor.fetchone()[0]
        
        return {
            "success": True,
            "statistics": {
                "total_tournaments": sum(association_counts.values()),
                "by_association": association_counts,
                "years_covered": years,
                "total_players_in_history": total_players
            }
        }
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/search")
async def search_tournaments(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Search tournaments by name, location, or championship
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        
        search_pattern = f"%{q}%"
        cursor.execute("""
            SELECT tournament_id, name, year, date, location, association, championship
            FROM tournament_history
            WHERE 
                name LIKE %s OR 
                location LIKE %s OR 
                championship LIKE %s
            ORDER BY date DESC NULLS LAST, year DESC NULLS LAST, id DESC NULLS LAST, name ASC
            LIMIT %s
        """, (search_pattern, search_pattern, search_pattern, limit))
        
        results = _rows_to_dicts(cursor, cursor.fetchall())
        
        return {
            "success": True,
            "query": q,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


@router.get("/years")
async def get_available_years():
    """
    Get available years in tournament history
    """
    conn = None
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT year FROM tournament_history
            WHERE year IS NOT NULL
            ORDER BY year DESC
        """)
        
        years = [row[0] for row in cursor.fetchall()]
        
        return {
            "success": True,
            "years": years
        }
    except Exception as e:
        logger.error(f"Error fetching years: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _close_conn(conn)


# --- Upcoming / Future Events ---


def _parse_event_date(date_str: Optional[str]) -> Optional[date]:
    """Parse event date string to date. Returns None if unparseable."""
    if not date_str or not isinstance(date_str, str):
        return None
    s = date_str.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _is_future_event(evt: Dict[str, Any]) -> bool:
    """Return True if event is in the future (or has no parseable date / TBD)."""
    today = date.today()
    # Prefer end_date for multi-day events; then start_date, then event/date.
    candidates = [
        evt.get("end_date"),
        evt.get("start_date"),
        evt.get("event_date"),
        evt.get("date"),
    ]
    parsed_dates: List[date] = []
    for raw in candidates:
        if isinstance(raw, date):
            parsed_dates.append(raw)
            continue
        parsed = _parse_event_date(raw)
        if parsed is not None:
            parsed_dates.append(parsed)
    if not parsed_dates:
        return True  # TBD / no date - treat as future
    return max(parsed_dates) >= today


def _is_likely_tournament_name(name: str) -> bool:
    """Heuristic gate to exclude player/news/nav noise from archive payloads."""
    n = (name or "").strip()
    if not n:
        return False
    up = n.upper()

    # Known navigation/noise rows that can appear in scraped payloads
    blocked_exact = {
        "APPS",
        "UPGRADE",
        "LOGIN",
        "SIGN UP",
        "OVERVIEW",
        "SCHEDULE",
        "TOTAL POINTS",
        "TOURNAMENT NOT FOUND",
    }
    if up in blocked_exact:
        return False

    blocked_substrings = [
        "SUPPORT@",
        "DIGITAL POOL",
        "LATEST WPA NEWS",
        "WPA NEWS",
        "WPBA NEWS",
    ]
    if any(s in up for s in blocked_substrings):
        return False

    # Most tournaments include at least one strong marker
    tournament_markers = [
        "WPA",
        "WPBA",
        "OPEN",
        "CHAMPIONSHIP",
        "CLASSIC",
        "INVITATIONAL",
        "MASTERS",
        "CUP",
        "TOUR",
        "WORLD",
        "INTERNATIONAL",
        "HEYBALL",
        "ARTISTIC",
        "8-BALL",
        "9-BALL",
        "10-BALL",
    ]
    if any(m in up for m in tournament_markers):
        return True

    # Short plain names are usually player rows, not events.
    return False


def _normalize_upcoming_association(value: Optional[str], name: str = "") -> str:
    raw = (value or "").strip()
    raw_up = raw.upper()
    if raw:
        # Guard against upstream mislabels where WPBA titles are tagged as WPA*.
        if "WPBA" in name.upper() or "WPBA" in raw_up:
            return "WPBA"
        return raw
    upper_name = name.upper()
    if "WPBA" in upper_name:
        return "WPBA"
    if "WPA WOMEN" in upper_name:
        return "WPA Women"
    if "WPA MEN" in upper_name:
        return "WPA Men"
    if "WPA" in upper_name:
        return "WPA"
    return "WPA"


def _ensure_upcoming_events_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS upcoming_events (
            id SERIAL PRIMARY KEY,
            dedupe_key TEXT,
            event_id TEXT,
            name TEXT NOT NULL,
            event_date DATE,
            start_date DATE,
            end_date DATE,
            location TEXT,
            association TEXT,
            url TEXT,
            bracket_url TEXT,
            registration_url TEXT,
            prize_pool TEXT,
            format TEXT,
            max_players INTEGER,
            enrichment JSONB,
            status TEXT DEFAULT 'upcoming',
            source_file TEXT,
            scraped_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cursor.execute("ALTER TABLE upcoming_events ADD COLUMN IF NOT EXISTS max_players INTEGER")
    cursor.execute("ALTER TABLE upcoming_events ADD COLUMN IF NOT EXISTS enrichment JSONB")
    cursor.execute("ALTER TABLE upcoming_events ADD COLUMN IF NOT EXISTS dedupe_key TEXT")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_upcoming_events_dedupe_key ON upcoming_events (dedupe_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_upcoming_events_date ON upcoming_events (event_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_upcoming_events_association ON upcoming_events (association)")


def _extract_upcoming_events_from_payload(payload: Dict[str, Any], source_file: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if isinstance(payload.get("events"), list):
        items.extend([x for x in payload.get("events", []) if isinstance(x, dict)])
    if isinstance(payload.get("data"), list):
        items.extend([x for x in payload.get("data", []) if isinstance(x, dict)])
    if isinstance(payload.get("tournaments"), list):
        items.extend([x for x in payload.get("tournaments", []) if isinstance(x, dict)])

    payload_scraped_at = payload.get("scraped_at")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not payload_scraped_at:
        payload_scraped_at = metadata.get("archive_timestamp")

    events: List[Dict[str, Any]] = []
    for item in items:
        name = (item.get("name") or item.get("tournament_name") or "").strip()
        if not name:
            continue
        if not _is_likely_tournament_name(name):
            continue

        date_str = item.get("event_date") or item.get("date") or item.get("start_date")
        start_str = item.get("start_date") or date_str
        end_str = item.get("end_date") or date_str
        status = (item.get("status") or "upcoming").strip().lower() or "upcoming"
        association = _normalize_upcoming_association(item.get("association"), name)

        event = {
            "event_id": (item.get("event_id") or item.get("tournament_id") or "").strip() or None,
            "name": name,
            "event_date": _parse_event_date(date_str),
            "start_date": _parse_event_date(start_str),
            "end_date": _parse_event_date(end_str),
            "location": item.get("venue_address") or item.get("location"),
            "association": association,
            "url": item.get("url") or item.get("source_url"),
            "bracket_url": item.get("bracket_url"),
            "registration_url": item.get("registration_url"),
            "prize_pool": item.get("prize_pool"),
            "format": item.get("format"),
            "status": status,
            "source_file": source_file,
            "scraped_at": payload_scraped_at,
            # used by _is_future_event
            "date": date_str,
        }
        # Keep only strict future tournaments with required fields.
        if _has_required_future_tournament_fields(event):
            events.append(event)
    return events


def _collect_upcoming_events_from_archives() -> List[Dict[str, Any]]:
    data_dirs = [
        PROJECT_ROOT / "data" / "tournament_current_archive",
        PROJECT_ROOT / "data" / "tournament_history_archive",
        PROJECT_ROOT / "data" / "externalpool_archive",
        PROJECT_ROOT / "data" / "cp_archive",
    ]
    extra_dirs = [
        Path("/srv/scrape_archives"),
        Path("/srv/rankings-bot/scrape_archives"),
        Path("/home/ansible/archives/rankings-bot"),
    ]
    all_dirs = [d for d in data_dirs + extra_dirs if d.is_dir()]

    events: List[Dict[str, Any]] = []
    for base in all_dirs:
        for json_file in base.rglob("*.json"):
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    events.extend(_extract_upcoming_events_from_payload(payload, str(json_file)))
            except Exception as e:
                logger.debug("Skipping unreadable archive json %s: %s", json_file, e)

    # Parse backup tarballs in case JSON archives were packed there.
    backup_dir = PROJECT_ROOT / "backups" / "scrapes"
    if backup_dir.is_dir():
        for tar_path in backup_dir.glob("scrapes_*.tar.gz"):
            try:
                with tarfile.open(tar_path, "r:gz") as tar:
                    for member in tar.getmembers():
                        if not member.isfile() or not member.name.lower().endswith(".json"):
                            continue
                        extracted = tar.extractfile(member)
                        if extracted is None:
                            continue
                        payload = json.loads(extracted.read().decode("utf-8"))
                        if isinstance(payload, dict):
                            src = f"{tar_path}:{member.name}"
                            events.extend(_extract_upcoming_events_from_payload(payload, src))
            except Exception as e:
                logger.debug("Skipping unreadable backup archive %s: %s", tar_path, e)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for e in events:
        key = _upcoming_event_natural_key(e)
        if key in seen:
            continue
        seen.add(key)
        e = dict(e)
        e["dedupe_key"] = key
        deduped.append(e)
    return deduped


def _collect_upcoming_events_from_live_sources() -> List[Dict[str, Any]]:
    """
    Scrape fresh future events from WPBA/WPA discovery sources.
    Uses existing discovery module and maps to upcoming_events shape.
    """
    events: List[Dict[str, Any]] = []
    try:
        from scrapers.tournament_history_discovery import discover_past_events

        discovered = discover_past_events(wpba=True, wpa=True, include_future=True)
        for item in discovered:
            date_str = item.get("date") or item.get("end_date") or item.get("start_date")
            event = {
                "event_id": (item.get("tournament_id") or item.get("url") or item.get("name") or "").strip() or None,
                "name": (item.get("name") or "").strip(),
                "event_date": _parse_event_date(date_str),
                "start_date": _parse_event_date(item.get("start_date") or date_str),
                "end_date": _parse_event_date(item.get("end_date") or date_str),
                "location": item.get("location"),
                "association": _normalize_upcoming_association(item.get("association"), item.get("name") or ""),
                "url": item.get("url"),
                "bracket_url": item.get("bracket_url"),
                "registration_url": None,
                "prize_pool": item.get("prize_pool"),
                "format": item.get("format"),
                "status": "upcoming",
                "source_file": "live:wpba-wpa-discovery",
                "scraped_at": datetime.utcnow().isoformat(),
                "date": date_str,
            }
            if event["name"] and _is_likely_tournament_name(event["name"]) and _has_required_future_tournament_fields(event):
                events.append(event)
    except Exception as e:
        logger.warning("Live WPBA/WPA future scrape failed; continuing with archives: %s", e)

    # Also read WPA MEC event posts directly for accurate future WPA/Heyball/Artistic event dates.
    events.extend(_collect_wpa_mec_future_events())
    # WPA calendar backend (admin-ajax) source of truth for yearly entries.
    events.extend(_collect_wpa_calendar_ajax_future_events())
    # WPA calendar listing cards capture additional announcements (incl. Heyball) not always in /events JSON-LD.
    events.extend(_collect_wpa_calendar_listing_future_posts())
    # Targeted crawler for category-post links with Heyball/Artistic/Mixed/Team terms.
    events.extend(_collect_wpa_targeted_future_events())

    return events


def _collect_manual_future_events() -> List[Dict[str, Any]]:
    """
    Load manually curated future tournaments from data/future_tournaments_manual.json.
    Expected shape:
    {
      "events": [
        {
          "name": "...",
          "association": "WPA Heyball|WPA Artistic|WPA Mixed|WPA Men|WPA Women|WPBA",
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "location": "...",
          "url": "...",
          "registration_url": "...",
          "bracket_url": "...",
          "format": "...",
          "prize_pool": "..."
        }
      ]
    }
    """
    out: List[Dict[str, Any]] = []
    path = PROJECT_ROOT / "data" / "future_tournaments_manual.json"
    if not path.is_file():
        return out

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Manual future tournaments file is not valid JSON: %s", e)
        return out

    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return out

    for item in events:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        assoc = _normalize_upcoming_association(item.get("association"), name)
        date_str = item.get("event_date") or item.get("date") or item.get("start_date")
        event = {
            "event_id": (item.get("event_id") or item.get("url") or name).strip(),
            "name": name,
            "event_date": _parse_event_date(date_str),
            "start_date": _parse_event_date(item.get("start_date") or date_str),
            "end_date": _parse_event_date(item.get("end_date") or date_str),
            "location": item.get("location"),
            "association": assoc,
            "url": item.get("url"),
            "bracket_url": item.get("bracket_url"),
            "registration_url": item.get("registration_url"),
            "prize_pool": item.get("prize_pool"),
            "format": item.get("format"),
            "status": "upcoming",
            "source_file": str(path),
            "scraped_at": datetime.utcnow().isoformat(),
            "date": date_str,
        }
        if _has_required_future_tournament_fields(event):
            out.append(event)
    return out


def _clean_text(value: Optional[str]) -> str:
    raw = unescape(value or "")
    return re.sub(r"<[^>]+>", "", raw).strip()


def _association_from_wpa_text(text: str) -> str:
    up = (text or "").upper()
    if "WPBA" in up:
        return "WPBA"
    if "HEYBALL" in up:
        # Distinguish Heyball Men vs Women when event title/category indicates it
        if "WOMEN" in up or "LADIES" in up or "WOMAN" in up:
            return "WPA Heyball Women"
        return "WPA Heyball Men"
    if "ARTISTIC" in up:
        return "WPA Artistic"
    if "WOMEN" in up or "LADIES" in up or "WOMAN" in up:
        return "WPA Women"
    if "MIXED" in up or "TEAM" in up or "TEAMS" in up or "DOUBLES" in up or "SCOTCH" in up:
        return "WPA Mixed"
    return "WPA Men"


def _has_explicit_game_type(text: str) -> bool:
    up = (text or "").upper()
    # Keep only records that clearly state discipline/division in source text.
    return any(
        k in up
        for k in (
            "WPBA",
            "HEYBALL",
            "ARTISTIC",
            "WOMEN",
            "LADIES",
            "MIXED",
            "TEAM",
            "TEAMS",
            "DOUBLES",
            "SCOTCH",
            "8-BALL",
            "9-BALL",
            "10-BALL",
            "8BALL",
            "9BALL",
            "10BALL",
            "STRAIGHT POOL",
            "BLACKBALL",
            "SNOOKER",
        )
    )


def _has_required_future_tournament_fields(evt: Dict[str, Any]) -> bool:
    # Require concrete future dating (no undated records).
    if not _is_future_event(evt):
        return False

    # Require concrete location.
    location = (evt.get("location") or "").strip()
    if not location:
        return False

    # Require explicit game type/division in known fields.
    text = " ".join(
        [
            str(evt.get("name") or ""),
            str(evt.get("association") or ""),
            str(evt.get("format") or ""),
        ]
    )
    if not _has_explicit_game_type(text):
        return False
    return True


def _parse_ldjson_event_dates(html: str) -> tuple[Optional[date], Optional[date], Optional[str]]:
    script_re = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in script_re.finditer(html):
        blob = m.group(1).strip()
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("@type") or "").lower()
            if "event" not in node_type:
                continue
            start_raw = (node.get("startDate") or "")[:10]
            end_raw = (node.get("endDate") or start_raw)[:10]
            start_d = _parse_event_date(start_raw)
            end_d = _parse_event_date(end_raw)
            location = None
            loc = node.get("location")
            if isinstance(loc, dict):
                location = _clean_text((loc.get("name") or "")) or None
            return start_d, end_d, location
    return None, None, None


def _extract_location_from_page(html: str, title: str = "") -> Optional[str]:
    # 1) Explicit labels in page text
    text = _clean_text(html)
    label_patterns = [
        r"\bLocation\s*[:\-]\s*([A-Za-z0-9 ,.'\-]{3,80})",
        r"\bVenue\s*[:\-]\s*([A-Za-z0-9 ,.'\-]{3,80})",
        r"\bHost(?:ed)?\s+(?:in|at)\s+([A-Za-z0-9 ,.'\-]{3,80})",
    ]
    for p in label_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))[:80] or None

    # 2) Common title pattern: "... in Malaysia"
    m = re.search(r"\bin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\b", title or "")
    if m:
        return _clean_text(m.group(1))[:80] or None
    # 3) Title pattern: "China Open", "Qatar World Cup ..."
    open_matches = list(re.finditer(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+Open\b", title or ""))
    if open_matches:
        candidate = _clean_text(open_matches[-1].group(1))
        # Avoid discipline tokens accidentally captured with location (e.g., "Ball China").
        if "BALL" in candidate.upper():
            parts = candidate.split()
            candidate = parts[-1] if parts else candidate
        return candidate[:80] or None
    m = re.search(r"^\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+World\s+Cup\b", title or "")
    if m:
        return _clean_text(m.group(1))[:80] or None
    return None


def _collect_wpa_mec_future_events() -> List[Dict[str, Any]]:
    """
    Query WPA WordPress MEC posts and parse per-event ld+json dates from event pages.
    This improves accuracy for WPA future events, including Heyball/Artistic.
    """
    base = "https://wpapool.com"
    mec_events_url = f"{base}/wp-json/wp/v2/mec-events"
    mec_cat_url = f"{base}/wp-json/wp/v2/mec_category?per_page=100"
    out: List[Dict[str, Any]] = []
    today = date.today()

    try:
        with httpx.Client(
            headers={"User-Agent": "RankingsBot/1.0 (wpa-mec-events)"},
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            # Category lookup (best effort)
            cat_map: Dict[int, str] = {}
            try:
                cat_resp = client.get(mec_cat_url)
                if cat_resp.status_code == 200:
                    for c in cat_resp.json():
                        if isinstance(c, dict) and isinstance(c.get("id"), int):
                            cat_map[c["id"]] = _clean_text(c.get("name") or "")
            except Exception as e:
                logger.debug("WPA MEC category lookup failed: %s", e)

            # Pull MEC events with lightweight pagination to avoid missing future posts.
            posts: List[Dict[str, Any]] = []
            for page in (1, 2):
                resp = client.get(f"{mec_events_url}?per_page=100&page={page}")
                if resp.status_code != 200:
                    break
                chunk = resp.json()
                if not isinstance(chunk, list) or not chunk:
                    break
                posts.extend([p for p in chunk if isinstance(p, dict)])
                if len(chunk) < 100:
                    break

            current_year = date.today().year
            max_event_pages = 20
            checked_pages = 0
            for post in posts:
                if not isinstance(post, dict):
                    continue
                link = str(post.get("link") or "").strip()
                if not link:
                    continue

                title = _clean_text((post.get("title") or {}).get("rendered") if isinstance(post.get("title"), dict) else "")
                if not _is_likely_tournament_name(title):
                    continue

                title_up = title.upper()
                has_future_year_hint = any(str(y) in title for y in (current_year, current_year + 1, current_year + 2))
                has_focus_hint = any(k in title_up for k in ("WPA", "WPBA", "HEYBALL", "ARTISTIC", "MIXED", "TEAM", "DOUBLES"))
                if not has_future_year_hint and not has_focus_hint:
                    continue

                cats = post.get("mec_category") if isinstance(post.get("mec_category"), list) else []
                cat_names = " ".join([cat_map.get(c, "") for c in cats if isinstance(c, int)]).strip()
                assoc = _association_from_wpa_text(f"{title} {cat_names}")

                # Parse actual event dates from event page structured data.
                if checked_pages >= max_event_pages:
                    break
                try:
                    event_html = client.get(link).text
                except Exception:
                    continue
                checked_pages += 1
                start_d, end_d, loc = _parse_ldjson_event_dates(event_html)
                if end_d is None or end_d < today:
                    continue
                loc = loc or _extract_location_from_page(event_html, title)
                if not loc:
                    continue
                if not _has_explicit_game_type(f"{title} {cat_names}"):
                    continue

                out.append(
                    {
                        "event_id": str(post.get("id") or "").strip() or None,
                        "name": title,
                        "event_date": end_d,
                        "start_date": start_d,
                        "end_date": end_d,
                        "location": loc,
                        "association": assoc,
                        "url": link,
                        "bracket_url": None,
                        "registration_url": None,
                        "prize_pool": None,
                        "format": None,
                        "status": "upcoming",
                        "source_file": "live:wpa-mec-events",
                        "scraped_at": datetime.utcnow().isoformat(),
                        "date": end_d.isoformat(),
                    }
                )
    except Exception as e:
        logger.warning("WPA MEC future events scrape failed: %s", e)

    return out


def _collect_wpa_targeted_future_events() -> List[Dict[str, Any]]:
    """
    Targeted WPA crawler for category pages where Heyball/Artistic/Mixed announcements appear.
    Walks post links and keeps only pages that expose Event JSON-LD dates in the future.
    """
    out: List[Dict[str, Any]] = []
    today = date.today()
    category_urls = [
        "https://wpapool.com/category/events/",
        "https://wpapool.com/category/news/",
        "https://wpapool.com/calendar-2/",
    ]
    focus_terms = ("HEYBALL", "ARTISTIC", "MIXED", "TEAM", "TEAMS", "DOUBLES", "SCOTCH")

    try:
        with httpx.Client(
            headers={"User-Agent": "RankingsBot/1.0 (wpa-targeted-events)"},
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            link_re = re.compile(
                r'<a\s+[^>]*href=["\'](https://wpapool\.com/[^"\']+)["\'][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )

            candidate_links: Dict[str, str] = {}
            for url in category_urls:
                try:
                    html = client.get(url).text
                except Exception:
                    continue
                for m in link_re.finditer(html):
                    link = (m.group(1) or "").strip()
                    if not link or "/category/" in link or "/tag/" in link:
                        continue
                    title = _clean_text(m.group(2) or "")
                    if not title:
                        continue
                    if any(t in title.upper() for t in focus_terms):
                        candidate_links[link] = title

            for link, title in list(candidate_links.items())[:80]:
                try:
                    event_html = client.get(link).text
                except Exception:
                    continue
                start_d, end_d, loc = _parse_ldjson_event_dates(event_html)
                if end_d is None or end_d < today:
                    continue
                loc = loc or _extract_location_from_page(event_html, title)
                if not loc:
                    continue
                if not _has_explicit_game_type(title):
                    continue

                assoc = _association_from_wpa_text(title)
                out.append(
                    {
                        "event_id": link,
                        "name": title,
                        "event_date": end_d,
                        "start_date": start_d,
                        "end_date": end_d,
                        "location": loc,
                        "association": assoc,
                        "url": link,
                        "bracket_url": None,
                        "registration_url": None,
                        "prize_pool": None,
                        "format": None,
                        "status": "upcoming",
                        "source_file": "live:wpa-targeted",
                        "scraped_at": datetime.utcnow().isoformat(),
                        "date": end_d.isoformat(),
                    }
                )
    except Exception as e:
        logger.warning("Targeted WPA future crawler failed: %s", e)

    return out


def _collect_wpa_calendar_ajax_future_events() -> List[Dict[str, Any]]:
    """
    Query WPA calendar backend action (admin-ajax) and extract event links for upcoming years.
    Then parse each event page JSON-LD for accurate start/end dates.
    """
    out: List[Dict[str, Any]] = []
    base = "https://wpapool.com"
    ajax_url = f"{base}/wp-admin/admin-ajax.php"
    today = date.today()
    current_year = today.year
    years_to_check = [current_year, current_year + 1, current_year + 2]

    try:
        with httpx.Client(
            headers={"User-Agent": "RankingsBot/1.0 (wpa-calendar-ajax)", "Referer": "https://wpapool.com/calendar-2/"},
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            event_links: set[str] = set()
            for y in years_to_check:
                try:
                    resp = client.post(
                        ajax_url,
                        data={
                            "action": "mec_yearly_view_load_year",
                            "mec_year": str(y),
                            "apply_sf_date": "1",
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                except Exception:
                    continue
                html = f"{data.get('year', '')}{data.get('navigator', '')}"
                links = re.findall(r'https://wpapool\.com/events/[^"\']+', html, re.IGNORECASE)
                for link in links:
                    event_links.add(link.strip())

            # Parse event pages for schema dates and retain only future entries.
            for link in sorted(event_links):
                try:
                    page_html = client.get(link).text
                except Exception:
                    continue

                # Derive title from URL slug.
                title_match = re.search(r"/events/([^/]+)/?$", link)
                slug_title = (title_match.group(1).replace("-", " ").title() if title_match else "WPA Event")
                title = slug_title
                h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.IGNORECASE | re.DOTALL)
                if h1:
                    parsed_title = _clean_text(h1.group(1))
                    if parsed_title:
                        title = parsed_title

                start_d, end_d, loc = _parse_ldjson_event_dates(page_html)
                if end_d is None or end_d < today:
                    continue
                loc = loc or _extract_location_from_page(page_html, title)
                if not loc:
                    continue
                if not _has_explicit_game_type(title):
                    continue

                assoc = _association_from_wpa_text(title)
                out.append(
                    {
                        "event_id": link,
                        "name": title,
                        "event_date": end_d,
                        "start_date": start_d,
                        "end_date": end_d,
                        "location": loc,
                        "association": assoc,
                        "url": link,
                        "bracket_url": None,
                        "registration_url": None,
                        "prize_pool": None,
                        "format": None,
                        "status": "upcoming",
                        "source_file": "live:wpa-calendar-ajax",
                        "scraped_at": datetime.utcnow().isoformat(),
                        "date": end_d.isoformat(),
                    }
                )
    except Exception as e:
        logger.warning("WPA calendar ajax future collector failed: %s", e)

    return out


def _collect_wpa_calendar_listing_future_posts() -> List[Dict[str, Any]]:
    """
    Parse the public WPA calendar listing page cards (not only /events/* detail pages).
    This captures posts like Heyball announcements that may not expose event JSON-LD.
    """
    out: List[Dict[str, Any]] = []
    url = "https://wpapool.com/calendar-2/"
    today = date.today()
    month_re = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    date_re = re.compile(rf"{month_re}\s+\d{{1,2}},\s+20\d{{2}}", re.IGNORECASE)

    try:
        with httpx.Client(
            headers={"User-Agent": "RankingsBot/1.0 (wpa-calendar-listing)"},
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            html = client.get(url).text
            link_re = re.compile(
                r'<a\s+[^>]*href=["\'](https://wpapool\.com/[^"\']+)["\'][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            seen: set[tuple[str, str]] = set()
            for m in link_re.finditer(html):
                link = (m.group(1) or "").strip()
                if not link:
                    continue
                # Skip nav/category links; keep content posts.
                if any(x in link for x in ("/category/", "/tag/", "/rules/", "/about/", "/contact", "/calendar-2/")):
                    continue
                title = _clean_text(m.group(2) or "")
                if not title or len(title) < 8:
                    continue
                if not _is_likely_tournament_name(title):
                    continue

                key = (link, title)
                if key in seen:
                    continue
                seen.add(key)

                # Date is usually rendered near the card title in calendar listing.
                window = html[m.end(): m.end() + 500]
                dm = date_re.search(window)
                listed_date = _parse_event_date(dm.group(0)) if dm else None
                if listed_date is None or listed_date < today:
                    continue
                if not _has_explicit_game_type(title):
                    continue

                # Enrich with event page schema for location; drop if no concrete location.
                try:
                    event_html = client.get(link).text
                    _, _, loc = _parse_ldjson_event_dates(event_html)
                    loc = loc or _extract_location_from_page(event_html, title)
                except Exception:
                    loc = None
                if not loc:
                    continue

                assoc = _association_from_wpa_text(title)
                out.append(
                    {
                        "event_id": link,
                        "name": title,
                        "event_date": listed_date,
                        "start_date": listed_date,
                        "end_date": listed_date,
                        "location": loc,
                        "association": assoc,
                        "url": link,
                        "bracket_url": None,
                        "registration_url": None,
                        "prize_pool": None,
                        "format": None,
                        "status": "upcoming",
                        "source_file": "live:wpa-calendar-listing",
                        "scraped_at": datetime.utcnow().isoformat(),
                        "date": listed_date.isoformat(),
                    }
                )
    except Exception as e:
        logger.warning("WPA calendar listing collector failed: %s", e)

    return out


@router.get("/upcoming")
async def get_upcoming_events(
    association: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    """
    Get upcoming/future events (scraped from WPBA and WPA).
    Reads from SQLite database from PostgreSQL.
    Data is populated via migration scripts from legacy SQLite database.
    """
    conn = None
    try:
        conn = _get_conn()
        # Query upcoming events from PostgreSQL archive-backed table.
        query = """
            SELECT
                id,
                event_id,
                name,
                event_date::text AS date,
                start_date::text AS start_date,
                end_date::text AS end_date,
                location,
                association,
                url,
                bracket_url,
                registration_url,
                prize_pool,
                format,
                max_players,
                enrichment,
                status,
                scraped_at
            FROM upcoming_events
            WHERE 1=1
              AND COALESCE(end_date, start_date, event_date) >= CURRENT_DATE
        """
        params: list = []

        if association:
            assoc = association.strip()
            if assoc.upper() == "WPA":
                query += " AND association ILIKE %s"
                params.append("WPA%")
            elif assoc.upper() == "WPBA":
                query += " AND association ILIKE %s"
                params.append("WPBA%")
            else:
                query += " AND association ILIKE %s"
                params.append(assoc)

        query += " ORDER BY COALESCE(event_date, start_date, end_date) ASC NULLS LAST, name ASC LIMIT %s"
        params.append(limit)

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            events = _rows_to_dicts(cursor, rows) if rows else []
        return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        logger.warning(f"Could not fetch upcoming events: {e}")
        # Gracefully return empty if table doesn't exist yet
        return {"success": True, "events": [], "count": 0}
    finally:
        _close_conn(conn)


def _collect_upcoming_events_from_tournament_history() -> List[Dict[str, Any]]:
    """
    Upcoming rows already canonical in tournament_history (WPBA calendar imports, etc.).
    Future Tournaments reads upcoming_events, not tournament_history directly — bridge
    the SSOT here so refresh-upcoming surfaces events we already track.
    """
    conn = _get_conn()
    events: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT tournament_id, name, date, location, association, source_url, bracket_url, prize_pool, status
                FROM tournament_history
                WHERE LOWER(COALESCE(status, '')) = 'upcoming'
                ORDER BY date ASC NULLS LAST, name ASC
                """
            )
            rows = cursor.fetchall()
            if not rows:
                return events
            cols = [d[0] for d in cursor.description]
            for row in rows:
                rec = dict(zip(cols, row))
                name = (rec.get("name") or "").strip()
                if not name or not _is_likely_tournament_name(name):
                    continue
                assoc_raw = (rec.get("association") or "").strip()
                association = _normalize_upcoming_association(assoc_raw, name)
                event_date = rec.get("date")
                location = (rec.get("location") or "").strip() or "TBD"
                fmt = "9-BALL" if "WPBA" in (association + name).upper() else None
                event = {
                    "event_id": rec.get("tournament_id"),
                    "name": name,
                    "event_date": event_date,
                    "start_date": event_date,
                    "end_date": event_date,
                    "location": location,
                    "association": association,
                    "url": rec.get("source_url"),
                    "bracket_url": rec.get("bracket_url"),
                    "prize_pool": rec.get("prize_pool"),
                    "format": fmt,
                    "status": "upcoming",
                    "source_file": "tournament_history:ssot",
                    "scraped_at": datetime.utcnow().isoformat(),
                    "date": event_date.isoformat() if event_date else None,
                }
                if _has_required_future_tournament_fields(event):
                    events.append(event)
    except Exception as e:
        logger.warning("Could not load upcoming events from tournament_history: %s", e)
    finally:
        _close_conn(conn)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for e in events:
        key = _upcoming_event_natural_key(e)
        if key in seen:
            continue
        seen.add(key)
        e = dict(e)
        e["dedupe_key"] = key
        deduped.append(e)
    return deduped


def _run_upcoming_refresh_sync() -> dict:
    """Populate upcoming events from archive/backups (blocking)."""
    archive_events = _collect_upcoming_events_from_archives()
    live_events = _collect_upcoming_events_from_live_sources()
    manual_events = _collect_manual_future_events()
    history_events = _collect_upcoming_events_from_tournament_history()
    events = archive_events + live_events + manual_events + history_events

    # Final guardrail: enforce strict required fields across all sources.
    events = [e for e in events if _has_required_future_tournament_fields(e)]

    # Final dedupe across archive + live
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for e in events:
        key = e.get("dedupe_key") or _upcoming_event_natural_key(e)
        if key in seen:
            continue
        seen.add(key)
        e = dict(e)
        e["dedupe_key"] = key
        deduped.append(e)
    events = deduped

    from api.services.upcoming_event_enrichment import enrich_upcoming_events, enrichment_to_json

    try:
        events = enrich_upcoming_events(events)
    except Exception as e:
        logger.warning("Upcoming event news enrichment skipped: %s", e)

    by_association: Dict[str, int] = {}
    for e in events:
        assoc = (e.get("association") or "Unknown").strip()
        by_association[assoc] = by_association.get(assoc, 0) + 1

    conn = _get_conn()
    try:
        with conn.cursor() as cursor:
            _ensure_upcoming_events_table(cursor)
            cursor.execute("TRUNCATE TABLE upcoming_events RESTART IDENTITY")
            if events:
                cursor.executemany(
                    """
                    INSERT INTO upcoming_events
                    (dedupe_key, event_id, name, event_date, start_date, end_date, location, association, url, bracket_url,
                     registration_url, prize_pool, format, max_players, enrichment, status, source_file, scraped_at, updated_at)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, COALESCE(%s::timestamptz, NOW()), NOW())
                    ON CONFLICT (dedupe_key)
                    DO UPDATE SET
                        event_id = EXCLUDED.event_id,
                        name = EXCLUDED.name,
                        event_date = EXCLUDED.event_date,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        location = EXCLUDED.location,
                        association = EXCLUDED.association,
                        url = EXCLUDED.url,
                        bracket_url = EXCLUDED.bracket_url,
                        registration_url = EXCLUDED.registration_url,
                        prize_pool = EXCLUDED.prize_pool,
                        format = EXCLUDED.format,
                        max_players = EXCLUDED.max_players,
                        enrichment = EXCLUDED.enrichment,
                        status = EXCLUDED.status,
                        source_file = EXCLUDED.source_file,
                        scraped_at = COALESCE(EXCLUDED.scraped_at, upcoming_events.scraped_at),
                        updated_at = NOW()
                    """,
                    [
                        (
                            e.get("dedupe_key") or _upcoming_event_natural_key(e),
                            e.get("event_id"),
                            e.get("name"),
                            e.get("event_date"),
                            e.get("start_date"),
                            e.get("end_date"),
                            e.get("location"),
                            e.get("association"),
                            e.get("url"),
                            e.get("bracket_url"),
                            e.get("registration_url"),
                            e.get("prize_pool"),
                            e.get("format"),
                            e.get("max_players"),
                            enrichment_to_json(e.get("enrichment")) if enrichment_to_json else None,
                            e.get("status") or "upcoming",
                            e.get("source_file"),
                            e.get("scraped_at"),
                        )
                        for e in events
                    ],
                )
        conn.commit()
    finally:
        _close_conn(conn)

    return {
        "success": True,
        "message": "Upcoming events loaded from archives/backups + live WPBA/WPA scrape",
        "events_scraped": len(events),
        "count": len(events),
        "archive_count": len(archive_events),
        "live_count": len(live_events),
        "manual_count": len(manual_events),
        "by_association": by_association,
    }


@router.post("/refresh-upcoming")
def refresh_upcoming_events(_admin: dict = Depends(require_admin)):
    """
    Load and save upcoming events from scraper archives and backups (admin only).

    Fire-and-forget: returns immediately after spawning a background runner.
    Watch progress via GET /api/tournament-history/refresh-upcoming/log.
    """
    def _runner() -> None:
        result = _run_upcoming_refresh_sync()
        if not result.get("success"):
            raise RuntimeError(result.get("message") or "refresh-upcoming failed")
        logger.info(
            "Refreshed %s upcoming events (%s)",
            result.get("count"),
            result.get("by_association", {}),
        )
        # Single helper: bust server cache + push SSE to all connected browsers.
        notify_data_changed(
            Topic.UPCOMING_EVENTS.value,
            rows_updated=int(result.get("count", 0) or 0),
            message="Upcoming events refreshed",
        )

    return start_background_action(_REFRESH_UPCOMING_JOB, _runner)


@router.get("/refresh-upcoming/log")
async def stream_refresh_upcoming_log(_admin: dict = Depends(require_admin)):
    """Stream the live log for the most recent Refresh upcoming events run."""
    return stream_log_response(_REFRESH_UPCOMING_JOB)


@router.post("/refresh-past")
def refresh_past_tournaments(_user: dict = Depends(require_super_admin)):
    """
    Rebuild past tournament history from data already produced by the live rankings
    scrapers and related DB pipelines (super admin only — matches Settings UI).

    **No external HTTP scraping.** Reads only the ``rankings`` table (everything the
    WPBA / WPA / ExternalPool scrapers and Admin Refresh have already written) and
    the WPBA Women per-event path derived from the latest PDF-backed snapshot.

    Steps:

    1. ``fill_tournament_history_from_rankings_snapshots`` — each
       ``(ranking_system, snapshot_date)`` in ``rankings`` becomes a snapshot-style
       ``tournament_history`` row plus ``tournament_results``.
    2. ``fill_tournament_history_from_wpba_women_events`` — upserts real WPBA
       per-event tournaments from ``WPBA_Women`` column / per-system rows (same data
       the PDF + split pipeline uses).

    To ingest JSON from disk archives (CP / ExternalPool exports), use
    ``POST /api/tournament-history/fill-from-cp-archives`` separately.

    Fire-and-forget: returns immediately after spawning a background runner.
    Watch progress via GET /api/tournament-history/refresh-past/log.
    """
    def _runner() -> None:
        db = get_database_manager()
        logger.info(
            "Step 1/2: fill tournament_history from rankings snapshots "
            "(live scraper data in `rankings` -> tournament_history / tournament_results)",
        )
        snap_stats = db.fill_tournament_history_from_rankings_snapshots()
        logger.info("Rankings snapshots pipeline: %s", snap_stats)

        logger.info(
            "Step 2/2: fill WPBA Women per-event tournament_history from latest PDF snapshot columns",
        )
        wpba_evt_stats = db.fill_tournament_history_from_wpba_women_events()
        logger.info("WPBA per-event pipeline: %s", wpba_evt_stats)

        try:
            db.refresh_materialized_views()
        except Exception as e:
            logger.warning("refresh_materialized_views after refresh-past: %s", e)

        # Single helper: bust server cache + push SSE so connected browsers refetch
        # immediately. See docs/LIVE_UI_FRESHNESS_PLAN.md.
        rows = 0
        try:
            rows = int(snap_stats.get("rows", 0) or 0) + int(wpba_evt_stats.get("rows", 0) or 0)
        except (TypeError, ValueError, AttributeError):
            rows = 0
        notify_data_changed(
            Topic.TOURNAMENT_HISTORY.value,
            rows_updated=rows,
            message="Past tournament history sync complete",
        )

        logger.info(
            "Past tournament history sync complete (from existing scraped rankings only): "
            "rankings_snapshots=%s wpba_events=%s",
            snap_stats,
            wpba_evt_stats,
        )

    return start_background_action(_REFRESH_PAST_JOB, _runner)


@router.get("/refresh-past/log")
async def stream_refresh_past_log(_user: dict = Depends(require_super_admin)):
    """Stream the live log for the most recent Refresh past tournaments run."""
    return stream_log_response(_REFRESH_PAST_JOB)


@router.post("/fill-from-rankings")
async def fill_tournament_history_from_rankings(
    _admin: dict = Depends(require_admin),
    ranking_systems: Optional[List[str]] = Query(None, description="Only these systems, e.g. WPBA_Women, WPA_Women"),
    limit_per_system: Optional[int] = Query(None, description="Max snapshots per system (e.g. 12 = last 12 dates)"),
):
    """
    Fill tournament history from already-scraped rankings data (admin only).
    No new scraping: reads rankings table and creates/updates tournament_history
    and tournament_results so each (ranking_system, snapshot_date) becomes one
    "Rankings (date)" event with placements and points from that snapshot.
    """
    try:
        db = get_database_manager()
        stats = db.fill_tournament_history_from_rankings_snapshots(
            ranking_systems=ranking_systems,
            limit_snapshots_per_system=limit_per_system,
        )
        notify_data_changed(
            Topic.TOURNAMENT_HISTORY.value,
            rows_updated=int((stats or {}).get("rows", 0) or 0),
            message="Tournament history filled from rankings snapshots",
        )
        return {
            "success": True,
            "message": "Tournament history filled from rankings snapshots",
            "stats": stats,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Fill tournament history from rankings failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-news")
async def delete_news_from_tournament_history(_admin: dict = Depends(require_admin)):
    """
    Delete news/events and rankings-snapshot rows from tournament_history (admin only).
    So Tournament History list and Leaderboard show only real tournaments. Refreshes MV.
    """
    try:
        db = get_database_manager()
        result = db.delete_news_from_tournament_history()
        notify_data_changed(
            Topic.TOURNAMENT_HISTORY.value,
            rows_updated=int(result.get("deleted", 0) or 0),
            message="News/events removed from tournament history",
        )
        return {
            "success": True,
            "message": "News/events removed from tournament history",
            "deleted": result["deleted"],
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Delete news from tournament history failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill-from-cp-archives")
async def fill_tournament_history_from_cp_archives(
    _admin: dict = Depends(require_admin),
):
    """
    Fill tournament history from CP / External Pool scrape archives (admin only).
    Reads JSON files in data/externalpool_archive and data/cp_archive (or scrape
    archives on the server). Each archive may contain a "tournaments" array with
    tournament_name, players, and/or standings; these are upserted into tournament_history
    and tournament_results.
    """
    try:
        # Default: project data dirs + tournament_history archive; on server add scrape-archives path
        archive_dirs = [
            PROJECT_ROOT / "data" / "externalpool_archive",
            PROJECT_ROOT / "data" / "cp_archive",
            PROJECT_ROOT / "data" / "tournament_history_archive",
            PROJECT_ROOT / "data" / "tournament_current_archive",
        ]
        for extra in ("/srv/scrape_archives", "/srv/rankings-bot/scrape_archives"):
            p = Path(extra)
            if p.is_dir():
                archive_dirs.append(p)
        db = get_database_manager()
        stats = db.fill_tournament_history_from_cp_archives(archive_dirs)
        notify_data_changed(
            Topic.TOURNAMENT_HISTORY.value,
            rows_updated=int((stats or {}).get("rows", 0) or 0),
            message="Tournament history filled from CP archives",
        )
        return {
            "success": True,
            "message": "Tournament history filled from CP archives",
            "stats": stats,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Fill tournament history from CP archives failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
