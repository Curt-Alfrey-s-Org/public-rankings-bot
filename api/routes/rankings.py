"""
Rankings Routes
Provides endpoints for fetching and displaying rankings data
"""

# Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/WPA_RANKINGS_DATA_FLOW.md;
#   docs/WPBA_DATA_FLOW.md; docs/RANKINGS_TABLE_DESIGN.md; docs/HOW_DATA_IS_UPDATED.md

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse, StreamingResponse
from typing import AsyncGenerator
from contextlib import contextmanager
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import asyncio
import logging
import sys
import os
import threading
import time
import fcntl
from datetime import datetime

# Project root import
from project_root import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT))
TOURNAMENT_FILE = PROJECT_ROOT / "tournament_tools" / "final_results.txt"

from database import get_database_manager
from scrapers.wpba_scraper import WPBAScraper
from scrapers.wpa_scraper import WPAScraper
from scrapers.externalpool_scraper import ExternalPoolWomenScraper, ExternalPoolMenScraper
from scrapers.multi_type_rankings_scraper import MultiTypeRankingsScraper
from scrapers.org_metadata_scraper import OrgMetadataScraper
from api.auth import require_admin, require_director_or_admin, get_optional_user
from api.ranking_scope import (
    director_may_access_tournament_imports,
    director_may_modify_tournament_import_by_id,
    director_may_run_tournament_ranking_merge,
    director_may_write_ranking_systems,
    import_eligibility_payload,
    is_valid_ranking_system_for_import,
)
from api.notifications import process_ranking_change_notifications, post_refresh_webhook
from api.rate_limiter import check_rate_limit
from api.services.cache_store import invalidate_cache
from api.services.fargo_client import normalize_name, normalized_match_key
from api.services.live_log import (
    register_job,
    start_background_action,
    stream_log_response,
)
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed

# Live-log job IDs used by this module. Registered at import time so the GET stream
# handler always finds the job entry regardless of POST ordering across workers.
_LOAD_WPBA_PDF_JOB = "load_wpba_pdf"
register_job(_LOAD_WPBA_PDF_JOB, "Load WPBA PDF")

# Import dynamic tournament management
try:
    import sys
    sys.path.insert(0, '/home/ansible')
    from tournament_detector import TournamentDetector
    from unified_rankings_calculator import UnifiedRankingsCalculator
    from dynamic_ui_updater import DynamicUIUpdater
except ImportError as e:
    print(f"Warning: Could not import tournament management modules: {e}")
    TournamentDetector = None
    UnifiedRankingsCalculator = None
    DynamicUIUpdater = None


def run_rankings_refresh_impl(tournament_name: Optional[str] = None):
    """
    Synchronous version of rankings refresh for background jobs and startup.
    This is the internal implementation without authentication checks.
    """
    import asyncio
    from database import get_database_manager
    from api.services.cache_warmup import run_cache_warmup_impl

    # Run the async version in a new event loop
    async def _run_refresh():
        # Create a mock request object for the async function
        class MockRequest:
            pass

        # Import the scrapers inside the async function
        from scrapers.wpba_scraper import WPBAScraper
        from scrapers.wpa_scraper import WPAScraper
        from scrapers.org_metadata_scraper import OrgMetadataScraper

        db_manager = get_database_manager()

        results = {
            "timestamp": datetime.now().isoformat(),
            "wpba_women": {"success": False, "count": 0, "error": None},
            "wpa_women": {"success": False, "count": 0, "error": None},
            "wpa_men": {"success": False, "count": 0, "error": None},
            "cp_women": {"success": False, "count": 0, "error": None},  # Enrichment data collection
            "cp_men": {"success": False, "count": 0, "error": None},  # Enrichment data collection
            "metadata": {"success": False, "error": None},
            # Legacy fields for backwards compatibility
            "wpba": {"success": False, "count": 0, "error": None},
            "wpa": {"success": False, "count": 0, "error": None}
        }

        # Scrape WPBA data
        wpba_data = None
        wpba_err = None
        try:
            wpba_scraper = WPBAScraper()
            wpba_data = wpba_scraper.scrape_rankings()
        except Exception as e:
            wpba_err = str(e)
            logger.error(f"WPBA scrape failed: {e}")

        # Scrape WPA data (one HTML crawl for men + women; JSON archive under scraped_data/wpa)
        wpa_data_women = None
        wpa_data_men = None
        try:
            wpa_scraper = WPAScraper()
            bundle = wpa_scraper.scrape_all_html_divisions(persist=True)
            wpa_data_women = bundle.get("women") or None
            wpa_data_men = bundle.get("men") or None
        except Exception as e:
            logger.error(f"WPA scrape failed: {e}")

        # Scrape ExternalPool data for enrichment (CP)
        cp_data_women = None
        cp_data_men = None
        try:
            cp_women_scraper = ExternalPoolWomenScraper()
            cp_men_scraper = ExternalPoolMenScraper()
            cp_data_women = cp_women_scraper.scrape_rankings()
            cp_data_men = cp_men_scraper.scrape_rankings()
        except Exception as e:
            logger.error(f"ExternalPool (CP) enrichment data collection failed: {e}")

        # Save WPBA data
        if wpba_data:
            try:
                count = db_manager.save_wpba_rankings(wpba_data)
                results["wpba"]["success"] = True
                results["wpba"]["count"] = count
                results["wpba_women"]["success"] = True
                results["wpba_women"]["count"] = count
                logger.info(f"Refreshed {count} WPBA rankings")
            except Exception as e:
                results["wpba"]["error"] = str(e)
                results["wpba_women"]["error"] = str(e)
                logger.error(f"Error saving WPBA rankings: {e}")

        # Save WPA Women data
        if wpa_data_women:
            try:
                count = db_manager.save_wpa_rankings(wpa_data_women, ranking_type='WPA_Women')
                results["wpa_women"]["success"] = True
                results["wpa_women"]["count"] = count
                logger.info(f"Refreshed {count} WPA Women rankings")
                # Split WPA Women tournaments into individual systems
                try:
                    split_result = db_manager.split_wpa_women_to_column_buttons()
                    results["wpa_women"]["tournament_split"] = split_result
                    logger.info(f"WPA Women tournament split completed: {split_result}")
                except Exception as e:
                    logger.warning(f"WPA Women tournament split failed: {e}")
                    results["wpa_women"]["tournament_split_error"] = str(e)
            except Exception as e:
                results["wpa_women"]["error"] = str(e)
                logger.error(f"Error saving WPA Women rankings: {e}")

        # Save WPA Men data
        if wpa_data_men:
            try:
                count = db_manager.save_wpa_rankings(wpa_data_men, ranking_type='WPA_Men')
                results["wpa_men"]["success"] = True
                results["wpa_men"]["count"] = count
                logger.info(f"Refreshed {count} WPA Men rankings")
                # Split WPA Men tournaments into individual systems
                try:
                    split_result = db_manager.split_wpa_men_to_column_buttons()
                    results["wpa_men"]["tournament_split"] = split_result
                    logger.info(f"WPA Men tournament split completed: {split_result}")
                except Exception as e:
                    logger.warning(f"WPA Men tournament split failed: {e}")
                    results["wpa_men"]["tournament_split_error"] = str(e)
            except Exception as e:
                results["wpa_men"]["error"] = str(e)
                logger.error(f"Error saving WPA Men rankings: {e}")

        # CP data collected for enrichment only (not saved as rankings)
        if cp_data_women:
            logger.info(f"CP Women data collected: {len(cp_data_women)} players for enrichment")
            results["cp_women"]["success"] = True
            results["cp_women"]["count"] = len(cp_data_women)

        if cp_data_men:
            logger.info(f"CP Men data collected: {len(cp_data_men)} players for enrichment")
            results["cp_men"]["success"] = True
            results["cp_men"]["count"] = len(cp_data_men)

        # Run cross-system data enrichment to fill missing license/fargo data
        try:
            # db_manager comes from line ~96. A local "from database import get_database_manager"
            # here made the name local to _run_refresh, so the earlier call raised UnboundLocalError.
            # Prepare additional enrichment data (CP)
            additional_enrichment_data = {}
            if cp_data_women:
                additional_enrichment_data['Competitors_Pool_Women_9Ball'] = cp_data_women
            if cp_data_men:
                additional_enrichment_data['Competitors_Pool_Men_9Ball'] = cp_data_men

            enrichment_result = db_manager.enrich_player_data(additional_enrichment_data)
            logger.info(
                "Cross-system enrichment completed: %s players processed, %s records enriched, %s fields filled in %.2fs",
                enrichment_result.get('processed_players', 0),
                enrichment_result.get('enriched_records', 0),
                enrichment_result.get('fields_filled', 0),
                enrichment_result.get('duration_seconds', 0)
            )
        except Exception as e:
            logger.warning(f"Cross-system enrichment failed: {e}")

        any_rankings_saved = (
            results["wpba"]["success"]
            or results["wpba_women"]["success"]
            or results["wpa_women"]["success"]
            or results["wpa_men"]["success"]
        )
        if results["wpba"]["success"] or results["wpba_women"]["success"]:
            try:
                split_result = db_manager.split_wpba_women_to_column_buttons()
                logger.info(f"WPBA Women tournament split (background refresh): {split_result}")
            except Exception as e:
                logger.warning(f"WPBA Women tournament split failed (background refresh): {e}")
            try:
                wpba_evt_th = db_manager.fill_tournament_history_from_wpba_women_events()
                logger.info("WPBA per-event tournament history (background refresh): %s", wpba_evt_th)
            except Exception as e:
                logger.warning("WPBA per-event tournament history failed (background refresh): %s", e)
        if any_rankings_saved:
            try:
                db_manager.refresh_materialized_views()
                logger.info("Refreshed materialized views after background rankings refresh")
            except Exception as e:
                logger.warning("Materialized view refresh failed (background refresh): %s", e)
            try:
                notify_data_changed(
                    Topic.TOURNAMENT_HISTORY.value,
                    message="Background rankings refresh completed",
                )
                notify_data_changed(
                    Topic.RANKINGS.value,
                    message="Background rankings refresh completed",
                )
            except Exception as e:
                logger.warning("notify_data_changed failed (background refresh): %s", e)

        # Run cache warmup
        try:
            run_cache_warmup_impl()
            logger.info("Cache warmup completed")
        except Exception as e:
            logger.warning(f"Cache warmup failed: {e}")

        return results

    # Run the async function synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_refresh())
    finally:
        loop.close()


def get_all_rankings_from_db(org=None):
    """Get all rankings from PostgreSQL database, preferring association tables when populated."""
    from sqlalchemy import text
    from database import get_engine

    db_manager = get_db_manager()
    engine = get_engine()
    with engine.connect() as conn:
        if org:
            tbl, sys_col = db_manager._resolve_physical_rankings_read(conn, org)
            query = text(f"""
                SELECT
                    player_name as name,
                    rank,
                    points,
                    country,
                    license_number,
                    fargo_rating,
                    stops_played,
                    alfa_rating,
                    snapshot_date,
                    {sys_col} as ranking_system
                FROM {tbl}
                WHERE {sys_col} = :org
                AND snapshot_date = (
                    SELECT MAX(snapshot_date)
                    FROM {tbl}
                    WHERE {sys_col} = :org
                )
                ORDER BY position ASC NULLS LAST, rank ASC, id ASC
            """)
            rows = conn.execute(query, {"org": org}).fetchall()
        else:
            query = text("""
                SELECT
                    player_name as name,
                    rank,
                    points,
                    country,
                    license_number,
                    fargo_rating,
                    stops_played,
                    alfa_rating,
                    snapshot_date,
                    ranking_system
                FROM rankings r1
                WHERE snapshot_date = (
                    SELECT MAX(snapshot_date)
                    FROM rankings r2
                    WHERE r2.player_name = r1.player_name
                    AND r2.ranking_system = r1.ranking_system
                )
                ORDER BY ranking_system, position ASC NULLS LAST, rank ASC, id ASC
            """)
            rows = conn.execute(query).fetchall()

        result = []
        for row in rows:
            p = dict(row._mapping)
            if 'ranking_system' in p:
                p['organization'] = p['ranking_system']
            result.append(p)
        return result

router = APIRouter()


class NotifySubscribeRequest(BaseModel):
    email: str
    player_name: str
    system: str  # WPBA or WPA
logger = logging.getLogger(__name__)

_db_manager = None
_db_manager_lock = threading.Lock()


def _stale_after_hours() -> int:
    """Staleness threshold (hours) for API metadata."""
    try:
        value = int(os.getenv("RANKINGS_STALE_AFTER_HOURS", "48"))
        return max(1, value)
    except ValueError:
        return 48


def _ensure_director_ranking_write_allowed(user: dict, ranking_systems: List[str]) -> None:
    """Raise 403 if director cannot write all listed ranking_system values (admin/super_admin bypass)."""
    ok, msg = director_may_write_ranking_systems(user, list(ranking_systems))
    if not ok:
        raise HTTPException(status_code=403, detail=msg)


def _ensure_tournament_imports_bucket_allowed(user: dict, system: str) -> None:
    """Raise 403 if director cannot access tournament imports for WPBA/WPA bucket."""
    ok, msg = director_may_access_tournament_imports(user, system)
    if not ok:
        raise HTTPException(status_code=403, detail=msg)


def _ensure_tournament_ranking_merge_allowed(user: dict, system: str) -> None:
    """Raise 403 if director cannot merge tournament imports into rankings for this bucket."""
    ok, msg = director_may_run_tournament_ranking_merge(user, system)
    if not ok:
        raise HTTPException(status_code=403, detail=msg)


def _ensure_tournament_import_row_allowed(user: dict, imp: dict) -> None:
    """Raise 403 if director cannot read or modify this tournament_import row (by its ranking_system)."""
    ok, msg = director_may_modify_tournament_import_by_id(user, imp.get("ranking_system"))
    if not ok:
        raise HTTPException(status_code=403, detail=msg)


def get_db_manager():
    """Get database manager instance (Postgres only)."""
    global _db_manager
    if _db_manager is not None:
        return _db_manager
    with _db_manager_lock:
        if _db_manager is not None:
            return _db_manager
        _db_manager = get_database_manager()
        return _db_manager


def _project_root():
    return Path(__file__).resolve().parent.parent.parent


def get_db_connection():
    """Get a DB connection (Postgres)."""
    return get_db_manager().get_connection()


_PAID_RATING_FIELDS = ("est_rating", "est_rating_confidence", "est_rating_robustness", "alfa_rating")


def _get_user_tier(username: str) -> Optional[str]:
    """Return subscription tier for a username from ai_coach_usage."""
    if not username:
        return None
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tier
            FROM ai_coach_usage
            WHERE user_id = %s
            LIMIT 1
            """,
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return (row.get("tier") or "").strip().upper() or None
        return (row[0] or "").strip().upper() or None
    except Exception:
        return None
    finally:
        conn.close()


def _can_view_paid_ratings(user: dict | None) -> bool:
    """
    Paid ratings gate:
    - Admin/director/super_admin always allowed.
    - Authenticated users require PRO tier.
    - Anonymous users are not allowed.
    """
    if not user:
        return False
    role = str(user.get("role") or "").strip().lower()
    if role in {"admin", "director", "super_admin"}:
        return True
    username = str(user.get("sub") or "").strip()
    if not username:
        return False
    return _get_user_tier(username) == "PRO"


def _sanitize_paid_rating_fields(rows: List[dict]) -> List[dict]:
    sanitized: List[dict] = []
    for row in rows or []:
        out = dict(row)
        for field in _PAID_RATING_FIELDS:
            if field in out:
                out[field] = None
        sanitized.append(out)
    return sanitized


def _apply_paid_rating_gate(payload: dict, user: dict | None) -> dict:
    """Redact paid rating fields when user is not allowed."""
    can_view = _can_view_paid_ratings(user)
    out = dict(payload)
    rows = out.get("rankings")
    if isinstance(rows, list) and not can_view:
        out["rankings"] = _sanitize_paid_rating_fields(rows)
    out["paid_features"] = {
        "est_rating": "PRO",
        "alfa_rating": "PRO",
        "can_view": can_view,
    }
    return out

# --- In-memory cache for read-heavy endpoints; invalidated on POST /refresh ---
_rankings_cache: dict = {}  # key -> (data, version, timestamp)
_rankings_cache_lock = threading.Lock()
_CACHE_MAX_SIZE = 50  # Maximum cache entries
_CACHE_TTL_SECONDS = int(os.environ.get("RANKINGS_CACHE_TTL_SECONDS", "60"))  # Live-update default

def _cache_version_file():
    return _project_root() / "rankings_cache_version.txt"

def _read_cache_version():
    try:
        p = _cache_version_file()
        if p.exists():
            return float(p.read_text().strip() or "0")
    except Exception as e:
        logger.warning("Could not read cache version file: %s", e)
    return 0.0

def _write_cache_version():
    try:
        _cache_version_file().write_text(str(time.time()))
    except Exception as e:
        logger.warning("Could not write cache version file: %s", e)

def _cleanup_expired_cache():
    """Remove expired cache entries and enforce size limits."""
    current_time = time.time()
    expired_keys = []

    with _rankings_cache_lock:
        # Find expired entries
        for key, (data, version, timestamp) in _rankings_cache.items():
            if current_time - timestamp > _CACHE_TTL_SECONDS:
                expired_keys.append(key)

        # Remove expired entries
        for key in expired_keys:
            del _rankings_cache[key]

        # If still too large, remove oldest entries
        if len(_rankings_cache) > _CACHE_MAX_SIZE:
            # Sort by timestamp (oldest first) and keep only the newest entries
            sorted_entries = sorted(_rankings_cache.items(), key=lambda x: x[1][2])
            keys_to_remove = [key for key, _ in sorted_entries[:len(_rankings_cache) - _CACHE_MAX_SIZE]]
            for key in keys_to_remove:
                del _rankings_cache[key]

def _get_cached(key: str, fetch_fn):
    """Return cached data for key if version matches and not expired; else fetch, cache, and return."""
    current_time = time.time()
    current_version = _read_cache_version()

    with _rankings_cache_lock:
        # Check if we have valid cached data
        if key in _rankings_cache:
            data, cached_version, timestamp = _rankings_cache[key]
            # Check if cache is still valid (version matches and not expired)
            if cached_version >= current_version and (current_time - timestamp) <= _CACHE_TTL_SECONDS:
                return data

    # Clean up expired entries periodically (every 100 calls roughly)
    if hash(key) % 100 == 0:
        _cleanup_expired_cache()

    # Fetch fresh data
    data = fetch_fn()

    # Cache the result
    with _rankings_cache_lock:
        _rankings_cache[key] = (data, current_version, current_time)

    return data

def _fetch_all_rankings():
    """Return one row per player per system: latest snapshot only (no duplicate players)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.player_name AS name, r.rank, r.points, r.country, r.snapshot_date, r.ranking_system
            FROM rankings r
            WHERE r.snapshot_date = (
                SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = r.ranking_system
            )
            ORDER BY r.ranking_system, r.rank ASC
        """)
        players = [dict(zip([col.name for col in cursor.description], row)) for row in cursor.fetchall()]
        return {"total": len(players), "players": players}
    finally:
        conn.close()

def _fetch_wpba_list():
    return get_db_manager().get_wpba_rankings()

def _fetch_wpa_list():
    return get_db_manager().get_wpa_rankings()

@router.get("")
async def get_all_rankings():
    """Get all rankings data"""
    try:
        cached = _get_cached("all", _fetch_all_rankings)
        data = dict(cached)
        stale_after_hours = _stale_after_hours()
        db_manager = get_db_manager()
        data["staleness"] = {
            "threshold_hours": stale_after_hours,
            "wpba": db_manager.get_staleness_info("WPBA_Women", stale_after_hours),
            "wpa": db_manager.get_staleness_info("WPA_Women", stale_after_hours),
        }
        return data
    except Exception as e:
        logger.error(f"Error fetching rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpba")
async def get_wpba_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPBA Women rankings with pagination (legacy - redirects to wpba-women)"""
    try:
        all_rankings = get_all_rankings_from_db("WPBA_Women")
        
        # Apply pagination
        total = len(all_rankings)
        rankings = all_rankings[offset:offset + limit]
        stale_after_hours = _stale_after_hours()
        payload = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(rankings),
            "rankings": rankings,
            "association": "WPBA",
            "staleness": get_db_manager().get_staleness_info("WPBA_Women", stale_after_hours),
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPBA rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpba-women")
async def get_wpba_women_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPBA Women rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("WPBA_Women", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPBA",
            "division": "Women",
            "ranking_type": "WPBA_Women"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPBA Women rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpa")
async def get_wpa_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA Women rankings with pagination (legacy - redirects to wpa-women)"""
    try:
        all_rankings = get_all_rankings_from_db("WPA_Women")
        
        total = len(all_rankings)
        rankings = all_rankings[offset:offset + limit]
        stale_after_hours = _stale_after_hours()
        payload = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(rankings),
            "rankings": rankings,
            "association": "WPA",
            "staleness": get_db_manager().get_staleness_info("WPA_Women", stale_after_hours),
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpa-women")
async def get_wpa_women_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA Women rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("WPA_Women", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPA",
            "division": "Women",
            "ranking_type": "WPA_Women"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA Women rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpa-men")
async def get_wpa_men_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA Men rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("WPA_Men", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPA",
            "division": "Men",
            "ranking_type": "WPA_Men"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA Men rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpa-heyball-men")
async def get_wpa_heyball_men_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA HeyBall Men rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("WPA_Heyball_Men", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPA",
            "division": "HeyBall Men",
            "ranking_type": "WPA_Heyball_Men"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA HeyBall Men rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wpa-heyball-women")
async def get_wpa_heyball_women_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA HeyBall Women rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("WPA_Heyball_Women", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPA",
            "division": "HeyBall Women",
            "ranking_type": "WPA_Heyball_Women"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA HeyBall Women rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fargo-global")
async def get_fargo_global_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Global Fargo leaderboard from dedicated `fargo_rankings` table (FARGO_GLOBAL variant)."""
    try:
        result = _fetch_paginated_rankings("FARGO_GLOBAL", limit, offset, search=search)
        payload = {
            **result,
            "association": "Fargo",
            "division": "Global",
            "ranking_type": "FARGO_GLOBAL",
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching Fargo global rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wpa-artistic")
async def get_wpa_artistic_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get WPA Artistic Pool Professional rankings with pagination (from previous-ranking page)."""
    try:
        result = _fetch_paginated_rankings("WPA_Artistic", limit, offset, search=search)

        payload = {
            **result,
            "association": "WPA",
            "division": "Artistic Pool Professional",
            "ranking_type": "WPA_Artistic"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching WPA Artistic rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cp-9ball")
async def get_cp_9ball_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get CP 9-Ball Overall rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("Competitors_Pool_9Ball", limit, offset, search=search)

        payload = {
            **result,
            "association": "CP",
            "division": "9-Ball Overall",
            "ranking_type": "Competitors_Pool_9Ball"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching CP 9-Ball rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cp-10ball")
async def get_cp_10ball_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get CP 10-Ball Overall rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("Competitors_Pool_10Ball", limit, offset, search=search)

        payload = {
            **result,
            "association": "CP",
            "division": "10-Ball Overall",
            "ranking_type": "Competitors_Pool_10Ball"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching CP 10-Ball rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cp-8ball")
async def get_cp_8ball_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    search: Optional[str] = Query(None, min_length=1, max_length=120, description="Filter by player name substring"),
    user: dict | None = Depends(get_optional_user),
):
    """Get CP 8-Ball Overall rankings with pagination"""
    try:
        result = _fetch_paginated_rankings("Competitors_Pool_8Ball", limit, offset, search=search)

        payload = {
            **result,
            "association": "CP",
            "division": "8-Ball Overall",
            "ranking_type": "Competitors_Pool_8Ball"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching CP 8-Ball rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cp-women-9ball")
async def get_cp_women_9ball_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    user: dict | None = Depends(get_optional_user),
):
    """Get CP 9-Ball Women rankings with pagination"""
    try:
        db_manager = get_db_manager()
        result = db_manager.get_rankings_paginated("Competitors_Pool_Women_9Ball", limit, offset)

        payload = {
            **result,
            "association": "CP",
            "division": "9-Ball Women",
            "ranking_type": "Competitors_Pool_Women_9Ball"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching CP 9-Ball Women rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cp-men-9ball")
async def get_cp_men_9ball_rankings(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    user: dict | None = Depends(get_optional_user),
):
    """Get CP 9-Ball Men rankings with pagination"""
    try:
        db_manager = get_db_manager()
        result = db_manager.get_rankings_paginated("Competitors_Pool_Men_9Ball", limit, offset)

        payload = {
            **result,
            "association": "CP",
            "division": "9-Ball Men",
            "ranking_type": "Competitors_Pool_Men_9Ball"
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching CP 9-Ball Men rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-system/{ranking_system:path}")
async def get_rankings_by_system(
    ranking_system: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of rankings to return"),
    offset: int = Query(0, ge=0, description="Number of rankings to skip"),
    user: dict | None = Depends(get_optional_user),
):
    """Get rankings for a given ranking_system with pagination (e.g. WPA_Men_Yalin_8Ball, one per column)."""
    try:
        db_manager = get_db_manager()
        result = db_manager.get_rankings_paginated(ranking_system, limit, offset)
        association = "WPA"
        division = "Men"
        if ranking_system.startswith("WPBA_Women"):
            association = "WPBA"
            division = "Women"
        elif ranking_system.startswith("WPA_Women"):
            division = "Women"
        elif ranking_system.startswith("WPA_Men"):
            division = "Men"
        elif ranking_system.startswith("WPA_Heyball_Women"):
            division = "Heyball Women"
        elif ranking_system.startswith("WPA_Heyball_Men"):
            division = "Heyball Men"
        elif ranking_system.startswith("WPA_Artistic"):
            division = "Artistic"
        elif ranking_system.startswith("InsideSpin_"):
            association = "Inside Spin"
            division = ranking_system.split("_", 1)[1] if "_" in ranking_system else "Overall"
        elif ranking_system.startswith("DigitalPool_"):
            # Historical pro_world_rankings snapshots (2021-2023); rank-only.
            association = "Digital Pool"
            division = ranking_system.split("_", 1)[1] if "_" in ranking_system else "World"
        payload = {
            **result,
            "association": association,
            "division": division,
            "ranking_type": ranking_system,
        }
        return _apply_paid_rating_gate(payload, user)
    except Exception as e:
        logger.error(f"Error fetching rankings for {ranking_system}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wpa-men-tournament-systems")
async def get_wpa_men_tournament_systems():
    """WPA Men per-tournament buttons for Rankings UI: 10 most recent active events, newest-first."""
    try:
        db_manager = get_db_manager()
        systems = db_manager.get_wpa_men_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("Error fetching WPA Men tournament systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


@router.get("/wpa-women-tournament-systems")
async def get_wpa_women_tournament_systems():
    """WPA Women per-tournament buttons for Rankings UI: 10 most recent active events, newest-first."""
    try:
        db_manager = get_db_manager()
        systems = db_manager.get_wpa_women_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("Error fetching WPA Women tournament systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


@router.get("/wpba-tournament-systems")
async def get_wpba_tournament_systems():
    """Get dynamic WPBA tournament systems (one button per tournament) for Rankings UI.

    Returns the 10 most recent active events from the latest WPBA_Women snapshot, newest-first
    (hardcoded + PDF-discovered columns). No auth required.
    On DB/startup failure returns 200 with empty systems so the UI does not break.
    """
    try:
        db_manager = get_db_manager()
        systems = db_manager.get_wpba_tournament_systems()
        return {"systems": systems}
    except Exception as e:
        logger.error("Error fetching WPBA tournament systems: %s", e, exc_info=True)
        return {"systems": [], "degraded": True, "error": str(e)[:200]}


class RankingRowUpdate(BaseModel):
    """Fields that directors/admins can edit on a ranking row."""
    name: Optional[str] = None
    rank: Optional[int] = None
    points: Optional[float] = None
    country: Optional[str] = None
    license_number: Optional[str] = None
    stops_played: Optional[int] = None


@router.patch("/rows/{row_id:int}")
async def update_ranking_row(
    row_id: int,
    body: RankingRowUpdate = Body(...),
    user: dict = Depends(require_admin),
):
    """Update a single ranking row (fix name, points, country, etc.). Admin only."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one field to update (name, rank, points, stops_played).")
    if "license_number" in updates:
        raise HTTPException(
            status_code=400,
            detail="license_number is immutable and locked to WPA authoritative data.",
        )
    if "country" in updates:
        raise HTTPException(
            status_code=400,
            detail="country is immutable and locked to WPA authoritative data.",
        )
    try:
        db_manager = get_db_manager()
        ok = db_manager.update_ranking_row(row_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail="Ranking row not found or no valid fields to update.")
        try:
            db_manager.append_audit(
                actor_role=user.get("role", "unknown"),
                actor_subject=user.get("sub", "unknown"),
                action="update_ranking_row",
                details={"row_id": row_id, "updates": list(updates.keys())},
            )
        except Exception as e:
            logger.warning("Audit log write failed: %s", e)
        return {"message": "Ranking row updated.", "row_id": row_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating ranking row %s: %s", row_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def get_ranking_types():
    """Get all available ranking types and their metadata"""
    try:
        from sqlalchemy import text
        from database import get_engine
        
        engine = get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    rt.code,
                    rt.display_name,
                    rt.org_code,
                    rt.division,
                    rt.is_active,
                    om.org_name,
                    om.url,
                    om.logo_url,
                    om.primary_color,
                    om.theme
                FROM ranking_types rt
                LEFT JOIN org_metadata om ON rt.org_code = om.org_code
                WHERE rt.is_active = true
                ORDER BY rt.code
            """)
            rows = conn.execute(query).fetchall()
        
        ranking_types = []
        for row in rows:
            ranking_types.append({
                'code': row[0],
                'display_name': row[1],
                'org_code': row[2],
                'division': row[3],
                'is_active': bool(row[4]),
                'org_name': row[5],
                'url': row[6],
                'logo_url': row[7],
                'primary_color': row[8],
                'theme': row[9]
            })
        
        return {
            'ranking_types': ranking_types,
            'count': len(ranking_types)
        }
    except Exception as e:
        logger.error(f"Error fetching ranking types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Ranking systems that contain actual player names (excludes CP imports, event columns, etc.)
_PLAYER_NAMES_SYSTEMS = (
    "WPBA_Women", "WPA_Women", "WPA_Men",
    "WPA_Heyball_Men", "WPA_Heyball_Women",
    "FARGO_GLOBAL", "WPA_Artistic",
    "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
    "WPBA", "WPA", "LOCAL",
)

# Public cross-system player profile (USPBF + head-to-head lookups).
_PUBLIC_PLAYER_PROFILE_SYSTEMS = (
    ("wpba_women", "WPBA_Women"),
    ("wpa_women", "WPA_Women"),
    ("wpa_men", "WPA_Men"),
    ("wpa_heyball_men", "WPA_Heyball_Men"),
    ("wpa_heyball_women", "WPA_Heyball_Women"),
    ("fargo_global", "FARGO_GLOBAL"),
    ("wpa_artistic", "WPA_Artistic"),
    ("cp_9ball", "Competitors_Pool_9Ball"),
    ("cp_10ball", "Competitors_Pool_10Ball"),
    ("cp_8ball", "Competitors_Pool_8Ball"),
)


def _player_profile_block(history: list) -> dict:
    return {
        "current": history[0] if history else None,
        "history": history,
    }


def _get_player_system_snapshot(db_manager, player_name: str, system: str) -> list:
    """Ranking history for one player/system using the same stores as paginated reads."""
    history = db_manager.get_ranking_history(player_name, system) or []
    if history:
        return history
    if system not in ("FARGO_GLOBAL", "FARGO", "fargo_global"):
        return []
    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT snapshot_date, rank, points
            FROM fargo_rankings
            WHERE LOWER(TRIM(player_name)) = LOWER(TRIM(%s))
            ORDER BY snapshot_date DESC
            LIMIT 20
            """,
            (player_name,),
        )
        return [
            {"date": str(row[0]), "rank": row[1], "points": row[2]}
            for row in cursor.fetchall()
            if row
        ]
    finally:
        conn.close()


def _fetch_paginated_rankings(
    system: str,
    limit: int,
    offset: int,
    search: Optional[str] = None,
) -> dict:
    return get_db_manager().get_rankings_paginated(system, limit, offset, search=search)

# Non-player patterns: headers, placeholders, event names that can appear in rankings
_NON_PLAYER_PATTERNS = frozenset((
    "rank", "player", "points", "country", "name", "position", "#",
    "tbd", "n/a", "na", "bye", "—", "–",
    "rankings", "news", "events", "snapshot",
))


def _is_likely_player(name: str) -> bool:
    """Filter out headers, placeholders, and event names."""
    if not name or len(name.strip()) < 2:
        return False
    s = name.strip()
    if s.isdigit():
        return False
    lower = s.lower()
    if lower in _NON_PLAYER_PATTERNS:
        return False
    if any(p in lower for p in (" rankings (", " rankings(", " news", " events")):
        return False
    # Exclude single-word table headers
    if len(s.split()) == 1 and lower in ("rank", "player", "points", "country", "name", "position"):
        return False
    return True


def _order_independent_key(name: str) -> str:
    """
    Dedup key that treats "Adams Max" and "Adams, Max" the same: strip punctuation,
    lowercase, split into tokens, sort, join.
    """
    import unicodedata as _ud
    ascii_name = _ud.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    alpha = "".join(ch if ch.isalnum() or ch == " " else " " for ch in ascii_name.lower())
    tokens = sorted(alpha.split())
    return "".join(tokens)


def _dedupe_player_names_by_identity(names: list) -> list:
    """
    Collapse display-name variants (spacing, Last/First order, punctuation, commas) into one
    representative name per person.  Uses order-independent alpha token key so
    "Adams Max" == "Adams, Max" == "Max Adams".
    """
    buckets: dict = {}
    order_keys: list = []

    for n in names:
        nn = normalize_name(n)
        if not nn:
            continue
        key = _order_independent_key(nn)
        bucket_id = key if key else f"__raw__:{nn.lower()}"
        if bucket_id not in buckets:
            buckets[bucket_id] = []
            order_keys.append(bucket_id)
        buckets[bucket_id].append(nn)

    out: list = []
    for bid in order_keys:
        variants = list(dict.fromkeys(buckets[bid]))
        # Keep a string that exists in rankings (not a synthetic title-case form) so
        # /player/{name} matches without a full-table scan. Prefer "First Last" over "Last, First".
        if len(variants) == 1:
            display = variants[0]
        else:
            display = sorted(
                variants,
                key=lambda s: ("," in s, len(s), s.lower()),
            )[0]
        out.append(display)

    out.sort(key=lambda s: s.lower())
    return out


def _resolve_rankings_player_name(db_manager, player_name: str) -> str:
    """
    Map URL/display name to a player_name string that exists in rankings (exact match first,
    then same identity key as normalized_match_key).
    """
    from urllib.parse import unquote

    pn = normalize_name(unquote(player_name))
    if not pn:
        return player_name

    history_systems = tuple(dict.fromkeys(
        sys for _, sys in _PUBLIC_PLAYER_PROFILE_SYSTEMS
    )) + ("WPBA", "WPA")
    for sys in history_systems:
        if db_manager.get_ranking_history(pn, sys):
            return pn

    req_key = _order_independent_key(pn)
    if not req_key:
        return pn

    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ", ".join("%s" for _ in _PLAYER_NAMES_SYSTEMS)
        cursor.execute(
            """
            SELECT DISTINCT player_name
            FROM rankings
            WHERE player_name IS NOT NULL AND TRIM(player_name) != ''
              AND ranking_system IN (""" + placeholders + """)
              AND rank IS NOT NULL AND rank > 0
            """,
            tuple(_PLAYER_NAMES_SYSTEMS),
        )
        for row in cursor.fetchall():
            name_row = row[0] if row else None
            if not name_row:
                continue
            if _order_independent_key(name_row) == req_key:
                return name_row
    finally:
        conn.close()

    return pn


@router.get("/player-names")
async def get_player_names(
    limit: int = Query(2000, ge=1, le=5000, description="Maximum number of player names to return"),
):
    """Get distinct player names from rankings (for Head-to-Head and Player Performance dropdowns).
    Restricted to known player ranking systems; filters out headers, placeholders, and event names."""
    try:
        db_manager = get_db_manager()
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ", ".join("%s" for _ in _PLAYER_NAMES_SYSTEMS)
            fetch_cap = min(max(limit * 4, limit), 15000)
            cursor.execute(
                """
                SELECT DISTINCT player_name
                FROM rankings
                WHERE player_name IS NOT NULL AND TRIM(player_name) != ''
                  AND ranking_system IN (""" + placeholders + """)
                  AND rank IS NOT NULL AND rank > 0
                ORDER BY player_name
                LIMIT %s
                """,
                tuple(_PLAYER_NAMES_SYSTEMS) + (fetch_cap,),
            )
            raw = [row[0] for row in cursor.fetchall() if row and row[0]]
            filtered = [n for n in raw if _is_likely_player(n)]
            deduped = _dedupe_player_names_by_identity(filtered)
            return {"names": deduped[:limit]}
        finally:
            conn.close()
    except Exception as e:
        logger.error("Error fetching player names: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player/{player_name}")
async def get_player_rankings(player_name: str):
    """Get player data from all public ranking sources (cross-association snapshot)."""
    try:
        db_manager = get_db_manager()
        resolved = _resolve_rankings_player_name(db_manager, player_name)

        result = {"player_name": resolved}
        has_any = False
        for key, system in _PUBLIC_PLAYER_PROFILE_SYSTEMS:
            history = _get_player_system_snapshot(db_manager, resolved, system)
            block = _player_profile_block(history)
            result[key] = block
            if block["current"]:
                has_any = True

        # Legacy aliases for backwards compatibility
        result["wpba"] = result.get("wpba_women") or _player_profile_block([])
        result["wpa"] = result.get("wpa_women") or _player_profile_block([])

        if not has_any:
            raise HTTPException(status_code=404, detail=f"Player '{player_name}' not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching player {player_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _scrape_wpba_sync():
    """Run WPBA scrape (returns data, error, meta with source_url for logging/UI)."""
    meta: dict = {"source_url": None}
    try:
        scraper = WPBAScraper()
        data = scraper.scrape_rankings()
        meta["source_url"] = getattr(scraper, "pdf_url", None)
        if data:
            return (data, None, meta)
        return (
            None,
            "WPBA scrape returned no data: no PDF link on wpba.com/rankings, or scrape disabled.",
            meta,
        )
    except Exception as e:
        return (None, str(e), meta)


def _scrape_wpa_sync():
    """Run WPA scrape. One HTML crawl + optional Artistic PDF; archives JSON like WPBA. Returns (dict, error)."""
    try:
        scraper = WPAScraper()
        out = scraper.scrape_all_divisions(include_artistic=True, persist=True)
        if not out or not any(out.values()):
            return (None, "No data")
        return (out, None)
    except Exception as e:
        return (None, str(e))


def _refresh_lock_file():
    return _project_root() / "rankings_refresh.lock"

class _RefreshLock:
    """File-based lock so only one /refresh runs at a time."""
    def __init__(self):
        self._fd = None
    def acquire(self, blocking: bool = False) -> bool:
        path = _refresh_lock_file()
        path.touch(exist_ok=True)
        self._fd = open(path, "w")
        try:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            return True
        except (BlockingIOError, OSError):
            self._fd.close()
            self._fd = None
            return False
    def release(self):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            except Exception as e:
                logger.warning("Failed to release rankings refresh lock cleanly: %s", e)
            self._fd.close()
            self._fd = None

@router.post("/refresh")
async def trigger_rankings_refresh(
    _admin: dict = Depends(require_admin),
    tournament_name: Optional[str] = Query(None, description="Apply this tournament definition's points when loading final_results.txt"),
):
    """Trigger manual refresh of rankings data for all ranking types (admin only).
    Supports WPBA_Women, WPA_Men, and WPA_Women rankings with deduplication.
    When loading from final_results.txt, optional tournament_name applies that definition's point values.

    The API does not schedule ranking scrapes; this endpoint (and super-admin scraper routes) are explicit triggers.
    Do not run cron or the monitoring daemon against this URL if you want purely manual updates.
    """
    # Rate limit check: max 1 refresh per 5 minutes
    is_allowed, wait_time = check_rate_limit("refresh")
    if not is_allowed:
        logger.warning(f"Refresh rate limit exceeded. Wait {wait_time:.0f} seconds before retry.")
        raise HTTPException(
            status_code=429,
            detail=f"Refresh endpoint rate limited. Please wait {wait_time:.0f} seconds before retrying."
        )

    try:
        logger.info("Rankings refresh requested for all ranking types")
        
        db_manager = get_db_manager()
        wpba_pdf_saved_early = False
        wpba_data, wpba_err, _wpba_meta = _scrape_wpba_sync()

        results = {
            "timestamp": datetime.now().isoformat(),
            "wpba_women": {"success": False, "count": 0, "error": None},
            "wpa_women": {"success": False, "count": 0, "error": None},
            "wpa_men": {"success": False, "count": 0, "error": None},
            "metadata": {"success": False, "error": None},
            # Legacy fields for backwards compatibility
            "wpba": {"success": False, "count": 0, "error": None},
            "wpa": {"success": False, "count": 0, "error": None}
        }
        
        # Fetch and update organization metadata
        try:
            metadata_scraper = OrgMetadataScraper()
            metadata = metadata_scraper.get_all_metadata()
            if metadata:
                # Record success (metadata DB update not yet implemented)
                results["metadata"]["success"] = True
                logger.info(f"Updated organization metadata for {len(metadata)} organizations")
        except Exception as e:
            results["metadata"]["error"] = str(e)
            logger.warning(f"Organization metadata update failed: {e}")
        
        # Save WPBA (sequential)
        if wpba_data:
            t_save = time.perf_counter()
            try:
                count = db_manager.save_wpba_rankings(wpba_data)
                results["wpba"]["success"] = True
                results["wpba"]["count"] = count
                results["wpba"]["save_ms"] = round((time.perf_counter() - t_save) * 1000, 0)
                wpba_pdf_saved_early = True
                logger.info(f"Refreshed {count} WPBA rankings")
            except Exception as e:
                results["wpba"]["error"] = str(e)
                logger.error(f"Error saving WPBA rankings: {e}")
        else:
            results["wpba"]["error"] = wpba_err
            if wpba_err:
                logger.error(f"WPBA scrape failed: {wpba_err}")
        
        # Scrape WPA Women + Men (single /rankings/ crawl; snapshot saved under scraped_data/wpa)
        wpa_html_bundle: dict = {}
        try:
            wpa_scraper = WPAScraper()
            wpa_html_bundle = wpa_scraper.scrape_all_html_divisions(persist=True)
        except Exception as e:
            logger.error("WPA HTML scrape failed: %s", e)

        try:
            wpa_women_rankings = wpa_html_bundle.get("women") or []
            if wpa_women_rankings:
                count = db_manager.save_wpa_rankings(wpa_women_rankings, ranking_type='WPA_Women')
                results["wpa_women"]["success"] = True
                results["wpa_women"]["count"] = count
                logger.info(f"Refreshed {count} WPA Women rankings")
                # Split WPA Women tournaments into individual systems
                try:
                    split_result = db_manager.split_wpa_women_to_column_buttons()
                    results["wpa_women"]["tournament_split"] = split_result
                    logger.info(f"WPA Women tournament split completed: {split_result}")

                    # NOTE: Tournament detection DISABLED - only manual scraping allowed
                    # Tournament detection and processing will only happen via manual "test scrape" button

                except Exception as e:
                    logger.warning(f"WPA Women tournament split failed: {e}")
                    results["wpa_women"]["tournament_split_error"] = str(e)
            else:
                logger.warning("WPA Women scraper returned empty results")
        except Exception as e:
            results["wpa_women"]["error"] = str(e)
            logger.error(f"Error refreshing WPA Women rankings: {e}")
        
        # Scrape WPA Men (same bundle as women — no second website crawl)
        try:
            wpa_men_rankings = wpa_html_bundle.get("men") or []
            if wpa_men_rankings:
                count = db_manager.save_wpa_rankings(wpa_men_rankings, ranking_type='WPA_Men')
                results["wpa_men"]["success"] = True
                results["wpa_men"]["count"] = count
                logger.info(f"Refreshed {count} WPA Men rankings")
                # Split WPA Men tournaments into individual systems
                try:
                    split_result = db_manager.split_wpa_men_to_column_buttons()
                    results["wpa_men"]["tournament_split"] = split_result
                    logger.info(f"WPA Men tournament split completed: {split_result}")
                except Exception as e:
                    logger.warning(f"WPA Men tournament split failed: {e}")
                    results["wpa_men"]["tournament_split_error"] = str(e)
            else:
                logger.warning("WPA Men scraper returned empty results")
        except Exception as e:
            results["wpa_men"]["error"] = str(e)
            logger.error(f"Error refreshing WPA Men rankings: {e}")
        
        # WPBA Women: if tournament file exists, ingest into tournament_imports; else scrape
        try:
            tournament_file_ingested = False
            if TOURNAMENT_FILE.exists():
                from tournament_tools.load_final_results import parse_final_results, parse_final_results_multi
                blocks = parse_final_results_multi(TOURNAMENT_FILE)
                if not blocks:
                    single = parse_final_results(TOURNAMENT_FILE)
                    if single:
                        blocks = [single]
                if blocks:
                    for idx, raw_results in enumerate(blocks):
                        name = f"Tournament {idx + 1}" if len(blocks) > 1 else "Tournament from file"
                        db_manager.create_tournament_import(name, raw_results, "WPBA")
                    results["wpba_women"]["success"] = True
                    results["wpba_women"]["count"] = 0
                    results["wpba_women"]["tournament_imports_created"] = len(blocks)
                    results["wpba_women"]["message"] = (
                        f"Added {len(blocks)} tournament(s) to Data input. Confirm them, then click Update rankings (points-based calculation)."
                    )
                    tournament_file_ingested = True
                    try:
                        TOURNAMENT_FILE.unlink()
                        logger.info("Deleted tournament file after ingesting to tournament imports")
                    except OSError as e:
                        logger.warning("Could not delete tournament file after ingest: %s", e)
                    logger.info("Ingested %d tournament(s) from file into tournament_imports (incomplete)", len(blocks))
            if not results["wpba_women"]["success"] and not tournament_file_ingested:
                wpba_scraper = WPBAScraper()
                wpba_rankings = wpba_scraper.scrape_rankings()
                if wpba_rankings:
                    count = db_manager.save_wpba_rankings(wpba_rankings, ranking_type='WPBA_Women')
                    results["wpba_women"]["success"] = True
                    results["wpba_women"]["count"] = count
                    logger.info(f"Refreshed {count} WPBA Women rankings (scraped)")
                    # NEW: Split WPBA Women tournaments into individual systems
                    try:
                        split_result = db_manager.split_wpba_women_to_column_buttons()
                        results["wpba_women"]["tournament_split"] = split_result
                        logger.info(f"WPBA Women tournament split completed: {split_result}")
                    except Exception as e:
                        logger.warning(f"WPBA Women tournament split failed: {e}")
                        results["wpba_women"]["tournament_split_error"] = str(e)
        except Exception as e:
            results["wpba_women"]["error"] = str(e)
            logger.error(f"Error refreshing WPBA Women rankings: {e}")
        
        # Legacy field population for backwards compatibility
        results["wpba"] = results["wpba_women"]
        results["wpa"] = results["wpa_women"]

        # Run cross-system data enrichment to fill missing license/fargo data
        try:
            # Scrape ExternalPool data for enrichment
            externalpool_data_women = None
            externalpool_data_men = None
            try:
                from scrapers.externalpool_scraper import ExternalPoolWomenScraper, ExternalPoolMenScraper
                externalpool_women_scraper = ExternalPoolWomenScraper()
                externalpool_men_scraper = ExternalPoolMenScraper()
                externalpool_data_women = externalpool_women_scraper.scrape_rankings()
                externalpool_data_men = externalpool_men_scraper.scrape_rankings()
                logger.info(f"ExternalPool data collected: {len(externalpool_data_women or [])} women, {len(externalpool_data_men or [])} men for enrichment")
            except Exception as e:
                logger.error(f"ExternalPool enrichment data collection failed: {e}")

            # Prepare additional enrichment data
            additional_enrichment_data = {}
            if externalpool_data_women:
                additional_enrichment_data['Competitors_Pool_Women_9Ball'] = externalpool_data_women
            if externalpool_data_men:
                additional_enrichment_data['Competitors_Pool_Men_9Ball'] = externalpool_data_men

            enrichment_result = db_manager.enrich_player_data(additional_enrichment_data)
            logger.info(
                "Cross-system enrichment completed: %s players processed, %s records enriched, %s fields filled in %.2fs",
                enrichment_result.get('processed_players', 0),
                enrichment_result.get('enriched_records', 0),
                enrichment_result.get('fields_filled', 0),
                enrichment_result.get('duration_seconds', 0)
            )
        except Exception as e:
            logger.warning(f"Cross-system enrichment failed: {e}")

        # Notify subscribers of ranking changes (after new snapshots and movement are saved)
        try:
            base_url = os.getenv("NOTIFY_UNSUBSCRIBE_BASE_URL", "").strip()
            process_ranking_change_notifications(db_manager, base_url or None)
        except Exception as e:
            logger.warning(f"Ranking change notifications failed: {e}")
        
        # Optional webhook: POST refresh summary to WEBHOOK_URL
        try:
            post_refresh_webhook(results)
        except Exception as e:
            logger.warning(f"Webhook post failed: {e}")

        # Broadcast live ranking updates
        try:
            from api.notifications import broadcast_ranking_update
            import asyncio

            # Broadcast general ranking refresh notification
            asyncio.create_task(broadcast_ranking_update(
                "all_players", "all_systems", {"refreshed": True, "timestamp": results["timestamp"]}
            ))
        except Exception as e:
            logger.warning(f"Live ranking update broadcast failed: {e}")

        # Tournament History / leaderboard MVs: same pipeline as /refresh-wpba and scrapers/wpba/run
        any_rankings_saved = (
            wpba_pdf_saved_early
            or results["wpba_women"]["success"]
            or results["wpa_women"]["success"]
            or results["wpa_men"]["success"]
        )
        if wpba_pdf_saved_early or results["wpba_women"]["success"]:
            if wpba_pdf_saved_early and not results["wpba_women"]["success"]:
                try:
                    split_result = db_manager.split_wpba_women_to_column_buttons()
                    logger.info(
                        "WPBA Women tournament split (early PDF save path): %s",
                        split_result,
                    )
                except Exception as e:
                    logger.warning("WPBA Women tournament split failed (early PDF path): %s", e)
            try:
                wpba_evt_th = db_manager.fill_tournament_history_from_wpba_women_events()
                logger.info("WPBA per-event tournament history (full refresh): %s", wpba_evt_th)
                results["wpba_women"]["tournament_history"] = wpba_evt_th
            except Exception as e:
                logger.warning("WPBA per-event tournament history failed (full refresh): %s", e)
                results["wpba_women"]["tournament_history_error"] = str(e)
        if any_rankings_saved:
            try:
                db_manager.refresh_materialized_views()
                logger.info("Refreshed materialized views after full rankings refresh")
            except Exception as e:
                logger.warning("Materialized view refresh failed (full refresh): %s", e)
            try:
                notify_data_changed(
                    Topic.TOURNAMENT_HISTORY.value,
                    message="Full rankings refresh completed",
                )
                notify_data_changed(
                    Topic.RANKINGS.value,
                    message="Full rankings refresh completed",
                )
            except Exception as e:
                logger.warning("notify_data_changed failed (full refresh): %s", e)

        return results

    except Exception as e:
        logger.error(f"Error refreshing rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-wpba")
async def trigger_wpba_pdf_load(_user: dict = Depends(require_director_or_admin)):
    """Kick off a Load WPBA PDF run in the background and return immediately.

    Auth, scope, and rate-limit checks run inline (HTTP 403 / 429). The actual fetch
    + import work runs in a daemon thread; clients should follow up with
    `GET /api/rankings/refresh-wpba/log` to stream progress (mirrors the rebuild-website
    and scraper-run buttons).
    """
    _ensure_director_ranking_write_allowed(_user, ["WPBA_Women"])
    is_allowed, wait_time = check_rate_limit("refresh_wpba")
    if not is_allowed:
        logger.warning(f"Refresh WPBA rate limit exceeded. Wait {wait_time:.0f} seconds before retry.")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited. Please wait {wait_time:.0f} seconds before retrying."
        )

    requester = _user.get("user") or _user.get("sub") or "?"
    role = _user.get("role")

    def _runner() -> None:
        logger.info("WPBA PDF load requested by %s (%s)", requester, role)
        wpba_data, wpba_err, wpba_meta = _scrape_wpba_sync()
        if not wpba_data:
            raise RuntimeError(wpba_err or "Failed to fetch or parse WPBA PDF")
        source_url = (wpba_meta or {}).get("source_url") or ""
        db_manager = get_db_manager()
        count = db_manager.save_wpba_rankings(wpba_data, ranking_type="WPBA_Women")
        try:
            split_result = db_manager.split_wpba_women_to_column_buttons()
            logger.info("WPBA Women tournament split completed: %s", split_result)
        except Exception as e:
            logger.warning("WPBA Women tournament split failed: %s", e)
        # Real per-event WPBA tournaments for Tournament History / Leaderboard / Hot Streak
        try:
            wpba_evt_th = db_manager.fill_tournament_history_from_wpba_women_events()
            logger.info("WPBA per-event tournament history: %s", wpba_evt_th)
        except Exception as e:
            logger.warning("WPBA per-event tournament history failed: %s", e)
        # Refresh materialized views affected by WPBA data changes
        try:
            db_manager.refresh_materialized_views()
            logger.info("Refreshed materialized views after WPBA data load")
        except Exception as e:
            logger.warning("Materialized view refresh failed: %s", e)
        try:
            notify_data_changed(
                Topic.TOURNAMENT_HISTORY.value,
                rows_updated=int(count or 0),
                message="WPBA PDF load completed",
            )
            notify_data_changed(
                Topic.RANKINGS.value,
                rows_updated=int(count or 0),
                message="WPBA PDF load completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (WPBA PDF load): %s", e)
        by_rank = sorted(
            [r for r in wpba_data if isinstance(r.get("rank"), int) and 1 <= r["rank"] <= 500],
            key=lambda x: x["rank"],
        )
        sample_top = [
            {"rank": r.get("rank"), "name": r.get("name"), "points": r.get("points")}
            for r in by_rank[:8]
        ]
        logger.info(
            "WPBA PDF load complete: saved_rows=%s pdf=%s top1=%s parsed_rows=%s",
            count,
            (source_url[:100] + "…") if len(source_url) > 100 else source_url,
            sample_top[0] if sample_top else None,
            len(wpba_data),
        )

    return start_background_action(_LOAD_WPBA_PDF_JOB, _runner)


@router.get("/refresh-wpba/log")
async def stream_wpba_pdf_log(_user: dict = Depends(require_director_or_admin)):
    """Stream the live log for the most recent Load WPBA PDF run."""
    return stream_log_response(_LOAD_WPBA_PDF_JOB)


_SCRAPER_REGISTRY = {
    "wpba": ("WPBA Women", _scrape_wpba_sync),
    "wpa": ("WPA", _scrape_wpa_sync),
    # _scrape_externalpool_sync / _scrape_insidesp_sync are defined below; we look
    # them up lazily in the runner to avoid forward-reference issues at import time.
    "externalpool": ("External Pool", None),
    "insidesp": ("Inside Spin", None),
    "insidesp_tier2": ("Inside Spin Tier-2 (history)", None),
}

_SCRAPER_LOCKS: dict = {name: threading.Lock() for name in _SCRAPER_REGISTRY}


def _scraper_log_file_path(name: str) -> Path:
    """
    Per-scraper log path. Default: PROJECT_ROOT/logs/scraper_<name>.log so production
    compose bind-mount (../logs:/app/logs) makes the file visible to all uvicorn workers
    and to the streaming GET handler regardless of which worker accepted the POST.
    """
    template = os.getenv("SCRAPER_LOG_FILE_TEMPLATE", "").strip()
    if template:
        try:
            return Path(template.format(name=name))
        except (KeyError, IndexError):
            logger.warning("Invalid SCRAPER_LOG_FILE_TEMPLATE=%r; using default", template)
    return PROJECT_ROOT / "logs" / f"scraper_{name}.log"


@contextmanager
def _attach_scraper_log_file(file_path: Path):
    """
    Attach a FileHandler to the scrapers + this module's loggers for the duration of a
    single scraper run so all logger.info / logger.warning calls inside the scrape land
    in the per-scraper log file. Per Python logging cookbook: add handler in the running
    thread, remove + close on exit so we don't leak handlers across runs.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(file_path), mode="a", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    targets = [
        logging.getLogger("scrapers"),
        logging.getLogger("api.routes.rankings"),
        logging.getLogger("api.services"),
        logging.getLogger("database"),
    ]
    for lg in targets:
        lg.addHandler(handler)
        if lg.level == logging.NOTSET or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        try:
            handler.flush()
            handler.close()
        finally:
            for lg in targets:
                lg.removeHandler(handler)


def _append_log_line(file_path: Path, line: str) -> None:
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")
    except OSError as e:
        logger.warning("Failed to append to scraper log %s: %s", file_path, e)


def _run_scraper_pipeline(scraper_name: str) -> tuple[bool, int, str]:
    """
    Synchronous scrape + save pipeline for a single scraper. Returns (success, count, message).
    All log output flows through the standard logging module (captured by the FileHandler
    attached via _attach_scraper_log_file when run from the background runner).
    """
    if scraper_name == "externalpool":
        scraper_display, scraper_func = "External Pool", _scrape_externalpool_sync
    elif scraper_name == "insidesp":
        scraper_display, scraper_func = "Inside Spin", _scrape_insidesp_sync
    elif scraper_name == "insidesp_tier2":
        scraper_display, scraper_func = "Inside Spin Tier-2", _scrape_insidesp_tier2_sync
    else:
        scraper_display, scraper_func = _SCRAPER_REGISTRY[scraper_name]

    logger.info("Running %s scraper", scraper_display)
    raw = scraper_func()

    if scraper_name == "wpba":
        data, error, _ = raw
    else:
        data, error = raw

    if not data:
        msg = error or f"Failed to run {scraper_display} scraper"
        logger.error("%s scraper returned no data: %s", scraper_display, msg)
        return (False, 0, msg)

    db_manager = get_db_manager()
    count = 0
    blocked: List[str] = []
    if scraper_name == "wpba":
        count = db_manager.save_wpba_rankings(data, ranking_type="WPBA_Women")
        logger.info("Saved %s WPBA rankings", count)
        try:
            split_result = db_manager.split_wpba_women_to_column_buttons()
            logger.info("WPBA Women tournament split completed: %s", split_result)
        except Exception as e:
            logger.warning("WPBA Women tournament split failed: %s", e)
        try:
            wpba_evt_th = db_manager.fill_tournament_history_from_wpba_women_events()
            logger.info("WPBA per-event tournament history: %s", wpba_evt_th)
        except Exception as e:
            logger.warning("WPBA per-event tournament history failed: %s", e)
        try:
            db_manager.refresh_materialized_views()
            logger.info("Refreshed materialized views after WPBA scraper run")
        except Exception as e:
            logger.warning("Materialized view refresh failed: %s", e)
        try:
            notify_data_changed(
                Topic.TOURNAMENT_HISTORY.value,
                message="WPBA scraper run completed",
            )
            notify_data_changed(
                Topic.RANKINGS.value,
                message="WPBA scraper run completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (WPBA scraper): %s", e)
    elif scraper_name == "wpa":
        # Resilience: each division is saved independently so a single blocked
        # division (e.g. the save_rankings anti-data-loss drop guard tripping on
        # one division) does not abort the others. Blocked/failed divisions are
        # collected and surfaced; the rest still save, split, and refresh.
        for division, rankings in data.items():
            if not rankings:
                continue
            ranking_type = f"WPA_{division.title()}"
            if division == "heyball_men":
                ranking_type = "WPA_Heyball_Men"
            elif division == "heyball_women":
                ranking_type = "WPA_Heyball_Women"
            elif division == "artistic":
                ranking_type = "WPA_Artistic"

            try:
                db_count = db_manager.save_wpa_rankings(rankings, ranking_type=ranking_type)
            except Exception as save_exc:
                blocked.append(f"{ranking_type}: {save_exc}")
                logger.warning(
                    "WPA division %s not saved (other divisions continue): %s",
                    ranking_type, save_exc,
                )
                continue
            count += db_count
            logger.info("Saved %s %s rankings", db_count, division)
            try:
                if ranking_type == "WPA_Women":
                    db_manager.split_wpa_women_to_column_buttons()
                elif ranking_type == "WPA_Men":
                    db_manager.split_wpa_men_to_column_buttons()
                elif ranking_type == "WPA_Heyball_Men":
                    db_manager.split_wpa_heyball_men_to_column_buttons()
                elif ranking_type == "WPA_Heyball_Women":
                    db_manager.split_wpa_heyball_women_to_column_buttons()
                elif ranking_type == "WPA_Artistic":
                    db_manager.split_wpa_artistic_to_column_buttons()
            except Exception as split_exc:
                logger.warning("WPA tournament split after %s failed: %s", ranking_type, split_exc)
        if blocked:
            logger.warning(
                "WPA scraper: %d division(s) not saved: %s",
                len(blocked), "; ".join(blocked),
            )
        try:
            db_manager.refresh_materialized_views()
            logger.info("Refreshed materialized views after WPA scraper run")
        except Exception as e:
            logger.warning("Materialized view refresh after WPA failed: %s", e)
        try:
            notify_data_changed(
                Topic.TOURNAMENT_HISTORY.value,
                message="WPA scraper run completed",
            )
            notify_data_changed(
                Topic.RANKINGS.value,
                message="WPA scraper run completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (WPA scraper): %s", e)
    elif scraper_name == "externalpool":
        count = db_manager.save_cp_rankings(data, ranking_type="Competitors_Pool_9Ball")
        logger.info("Saved %s External Pool rankings", count)
        try:
            notify_data_changed(
                Topic.RANKINGS.value,
                rows_updated=int(count or 0),
                message="External Pool scraper run completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (externalpool): %s", e)
    elif scraper_name == "insidesp":
        # data = {"ratings": {<suffix>: [rows]}, "events": [event dicts]}.
        # Ratings -> rankings as InsideSpin_<suffix> (Alembic 056). Each discipline
        # saves independently so one failure doesn't abort the rest.
        ratings = (data or {}).get("ratings") or {}
        for suffix, rows in ratings.items():
            if not rows:
                continue
            system = f"InsideSpin_{suffix}"
            try:
                db_count = db_manager.save_rankings(rows, system)
            except Exception as save_exc:
                blocked.append(f"{system}: {save_exc}")
                logger.warning(
                    "Inside Spin %s not saved (other disciplines continue): %s",
                    system, save_exc,
                )
                continue
            count += db_count
            logger.info("Saved %s %s ratings", db_count, system)
        # Events -> de-dup against tournament_history via the crosswalk (no silent
        # merge; new tournaments are NOT created here). See MULTI_SOURCE plan §3a.
        events = (data or {}).get("events") or []
        if events:
            try:
                from api.services.event_crosswalk import (
                    EventCrosswalkResolver,
                    SOURCE_INSIDESP,
                )
                resolver = EventCrosswalkResolver(db=db_manager)
                resolver.ensure_table()
                matched = unmatched = no_date = 0
                for ev in events:
                    if not ev.get("start_date"):
                        no_date += 1
                        continue
                    res = resolver.resolve(
                        source=SOURCE_INSIDESP,
                        source_event_id=ev.get("slug") or ev.get("url") or ev.get("name"),
                        name=ev.get("name") or "",
                        event_date=ev.get("start_date"),
                        location=ev.get("location"),
                        source_url=ev.get("url"),
                    )
                    if res.matched:
                        matched += 1
                    else:
                        unmatched += 1
                logger.info(
                    "Inside Spin events crosswalk: matched=%s unmatched(IS-only)=%s no_date=%s",
                    matched, unmatched, no_date,
                )
            except Exception as e:
                logger.warning("Inside Spin event crosswalk failed: %s", e)
        if blocked:
            logger.warning(
                "Inside Spin: %d discipline(s) not saved: %s",
                len(blocked), "; ".join(blocked),
            )
        try:
            notify_data_changed(
                Topic.RANKINGS.value,
                rows_updated=int(count or 0),
                message="Inside Spin scraper run completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (insidesp): %s", e)
    elif scraper_name == "insidesp_tier2":
        stats = data if isinstance(data, dict) else {}
        count = int(stats.get("results_written") or 0)
        logger.info(
            "Inside Spin Tier-2: scanned=%s gap_filled=%s inserted_history=%s results=%s errors=%s",
            stats.get("scanned"), stats.get("gap_filled"),
            stats.get("inserted_history"), count, stats.get("errors"),
        )
        try:
            db_manager.refresh_materialized_views()
        except Exception as e:
            logger.warning("Materialized view refresh failed after Tier-2: %s", e)

    if blocked:
        # Partial success: some divisions saved, some were blocked (e.g. drop guard).
        msg = (
            f"Ran {scraper_display} scraper, saved {count} rankings; "
            f"{len(blocked)} division(s) NOT saved: {'; '.join(blocked)}"
        )
        return (count > 0, count, msg)
    if scraper_name == "insidesp_tier2":
        return (True, count, f"Inside Spin Tier-2 ingest completed: {count} tournament_results rows written.")
    return (True, count, f"Successfully ran {scraper_display} scraper, saved {count} rankings.")


def _run_scraper_in_background(scraper_name: str) -> None:
    """
    Runner for the per-scraper background thread. Acquires the scraper's lock (drops the
    run if already taken), redirects logger output into the per-scraper log file, and
    writes a 'Done in Xs' footer so the streaming UI can detect completion (same marker
    as scripts/rebuild_website_now.sh — keeps the shared log-stream UX consistent).
    """
    scraper_display = _SCRAPER_REGISTRY[scraper_name][0]
    log_path = _scraper_log_file_path(scraper_name)
    lock = _SCRAPER_LOCKS[scraper_name]
    if not lock.acquire(blocking=False):
        _append_log_line(log_path, f"[Skipped] {scraper_display} scraper is already running in another worker.")
        return
    started = time.time()
    try:
        with _attach_scraper_log_file(log_path):
            try:
                success, count, msg = _run_scraper_pipeline(scraper_name)
                elapsed = int(time.time() - started)
                if success:
                    _append_log_line(log_path, f"\n[OK] {msg}")
                else:
                    _append_log_line(log_path, f"\n[ERROR] {msg}")
                _append_log_line(log_path, f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Done in {elapsed}s.")
            except Exception as exc:
                logger.exception("scraper %s crashed: %s", scraper_name, exc)
                _append_log_line(log_path, f"\n[CRASH] {exc!s}")
                _append_log_line(
                    log_path,
                    f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Done in {int(time.time() - started)}s (with errors).",
                )
    finally:
        lock.release()


@router.post("/scrapers/{scraper_name}/run")
async def run_individual_scraper(
    scraper_name: str,
    _admin: dict = Depends(require_admin)
):
    """
    Trigger an individual scraper in the background and stream live progress via
    GET /api/rankings/scrapers/{scraper_name}/log (mirrors Admin 'Update website').

    Super admin only. Available scrapers: wpba, wpa, externalpool, insidesp, insidesp_tier2.
    """
    if _admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required for individual scraper control")

    if scraper_name not in _SCRAPER_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scraper: {scraper_name}. Valid: {', '.join(_SCRAPER_REGISTRY.keys())}",
        )

    scraper_display = _SCRAPER_REGISTRY[scraper_name][0]
    log_path = _scraper_log_file_path(scraper_name)

    # If already running in this worker, don't start a second run; tell the caller
    # to watch the existing log instead. (Cross-worker contention is also caught by
    # the lock inside the background thread.)
    if _SCRAPER_LOCKS[scraper_name].locked():
        return {
            "success": True,
            "scraper": scraper_name,
            "status": "already_running",
            "log_file": str(log_path),
            "message": f"{scraper_display} scraper is already running. Watch the live log.",
        }

    # Truncate so the streaming view shows a fresh run (same pattern as rebuild-website).
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("")
    except OSError as e:
        logger.exception("Could not create/truncate scraper log at %s", log_path)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Cannot write scraper log at {log_path} ({e}). "
                "Ensure the API user can write the project logs directory "
                "(production: host ./logs mounted at /app/logs)."
            ),
        ) from e

    _append_log_line(log_path, "==========================================")
    _append_log_line(log_path, f"  Rankings Bot — {scraper_display} scraper")
    _append_log_line(log_path, f"  Started at {datetime.utcnow().isoformat()}Z")
    _append_log_line(log_path, "==========================================")

    threading.Thread(
        target=_run_scraper_in_background,
        args=(scraper_name,),
        name=f"scraper-{scraper_name}",
        daemon=True,
    ).start()
    logger.info("Scraper %s started in background; log=%s", scraper_name, log_path)

    return {
        "success": True,
        "scraper": scraper_name,
        "status": "started",
        "log_file": str(log_path),
        "message": f"{scraper_display} scraper started. Watch the live log for progress.",
    }


def _scraper_log_stream_max_sec() -> int:
    """Seconds to keep GET /scrapers/.../log open. Long-running scrapers can take 10–15 min."""
    raw = os.getenv("SCRAPER_LOG_STREAM_MAX_SEC", "1200").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        logger.warning("Invalid SCRAPER_LOG_STREAM_MAX_SEC=%r; using 1200", raw)
        n = 1200
    return max(60, n)


async def _stream_scraper_log(scraper_name: str) -> AsyncGenerator[bytes, None]:
    """Yield the per-scraper log file as it grows, until 'Done in' or max wait."""
    log_path = _scraper_log_file_path(scraper_name)
    yield f"[Connected - streaming {log_path.name} from {log_path.parent}/]\n".encode("utf-8")
    last_size = 0
    empty_file_notice_sent = False
    file_missing_ticks = 0
    max_wait_sec = _scraper_log_stream_max_sec()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait_sec
    while loop.time() < deadline:
        try:
            if log_path.is_file():
                with open(log_path, "rb") as f:
                    f.seek(last_size)
                    chunk = f.read()
                    if chunk:
                        last_size = f.tell()
                        yield chunk
                        if b"Done in" in chunk:
                            return
                    elif (
                        last_size == 0
                        and log_path.stat().st_size == 0
                        and not empty_file_notice_sent
                    ):
                        yield b"[Log file is empty - waiting for scraper output...]\n"
                        empty_file_notice_sent = True
            else:
                file_missing_ticks += 1
                if file_missing_ticks == 1:
                    yield (
                        f"[Waiting for scraper log file at {log_path}... if this repeats, "
                        "click Run first or check API write access to logs/ "
                        "(production: ./logs is bind-mounted to /app/logs).]\n"
                    ).encode("utf-8")
                elif file_missing_ticks % 40 == 0:
                    yield b"[Still waiting for scraper log file...]\n"
        except (OSError, IOError) as e:
            logger.warning("Error reading scraper log: %s", e)
            yield f"\n[Log read error: {e!s}]\n".encode("utf-8", errors="replace")
            return
        await asyncio.sleep(0.5)
    yield (
        f"\n[Stream stopped after {max_wait_sec}s timeout - scraper may still be running on the server; "
        f"check {log_path} or click Run again.]\n"
    ).encode("utf-8")


@router.get("/scrapers/{scraper_name}/log")
async def scraper_log_stream(
    scraper_name: str,
    _admin: dict = Depends(require_admin),
):
    """Stream the per-scraper live log. Super admin only (matches POST .../run authz)."""
    if _admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    if scraper_name not in _SCRAPER_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scraper: {scraper_name}. Valid: {', '.join(_SCRAPER_REGISTRY.keys())}",
        )
    return StreamingResponse(
        _stream_scraper_log(scraper_name),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            # Defense in depth: nginx already sets proxy_buffering off for /api/, but X-Accel-Buffering: no
            # is the explicit per-response disable per nginx docs.
            "X-Accel-Buffering": "no",
        },
    )


def _scrape_externalpool_sync():
    """Return (rankings, error_message)."""
    try:
        from scrapers.externalpool_scraper import CpScraper
        scraper = CpScraper()
        data = scraper.scrape_rankings()
        if not data:
            return None, "No External Pool rankings returned"
        return data, None
    except Exception as exc:
        return None, str(exc)


def _scrape_insidesp_sync():
    """Return ({"ratings": {<suffix>: [rows]}, "events": [...]}, error_message).

    Tier-1 Inside Spin scrape: per-discipline ratings + latest events listing.
    Truthy `data` requires at least one ratings discipline (events alone are not
    enough to consider the run successful, matching the other scrapers' contract).
    """
    try:
        from scrapers.insidesp_scraper import InsideSpinScraper
        scraper = InsideSpinScraper()
        ratings = scraper.scrape_all_ratings()
        try:
            events = scraper.scrape_events()
        except Exception as ev_exc:  # events are best-effort; ratings are the gate
            logger.warning("Inside Spin events scrape failed: %s", ev_exc)
            events = []
        if not ratings:
            return None, "No Inside Spin ratings returned"
        return {"ratings": ratings, "events": events}, None
    except Exception as exc:
        return None, str(exc)


def _scrape_insidesp_tier2_sync():
    """Run Tier-2 historical ingest (API catalog + RSC placements). Returns (stats_dict, error)."""
    try:
        from api.services.insidesp_tier2_importer import InsideSpinTier2Importer
        stats = InsideSpinTier2Importer().ingest(
            begin_year=int(os.getenv("INSIDESP_TIER2_BEGIN_YEAR", "2020")),
            only_pro=os.getenv("INSIDESP_TIER2_ALL_EVENTS", "0") != "1",
            gap_fill_only=os.getenv("INSIDESP_TIER2_GAP_FILL_ONLY", "0") == "1",
        )
        if stats.get("errors") and not stats.get("results_written"):
            return None, f"Tier-2 ingest failed with {stats.get('errors')} errors"
        return stats, None
    except Exception as exc:
        return None, str(exc)


class ManualEntryRow(BaseModel):
    rank: int
    name: str
    points: Optional[float] = 0.0
    country: Optional[str] = None


class ManualImportRequest(BaseModel):
    system: str  # WPBA or WPA
    rows: List[ManualEntryRow]


class TournamentDefinitionCreate(BaseModel):
    name: str
    points_by_place: List[float]  # [pts_1st, pts_2nd, pts_3rd, ...]
    is_default_for_import: Optional[bool] = False


class TournamentDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    points_by_place: Optional[List[float]] = None
    is_default_for_import: Optional[bool] = None


class TournamentImportUpdate(BaseModel):
    name: Optional[str] = None
    points_by_place: Optional[List[float]] = None


@router.get("/import/eligibility")
async def get_rankings_import_eligibility(user: dict = Depends(require_director_or_admin)):
    """Systems and scopes the current user may import (Data input UI). Director list is filtered by user_associations."""
    return import_eligibility_payload(user)


@router.post("/import")
async def import_rankings_file(
    user: dict = Depends(require_director_or_admin),
    file: UploadFile = File(...),
    system: str = Query("WPBA", description="WPBA, WPA, WPA_Women, WPA_Men, WPA_Artistic, WPA_Heyball_*, or Competitors_Pool_*"),
):
    """Import rankings from a file (PDF, DOCX, XLSX, XML, CSV, TXT). Director or Admin only.
    Supports WPBA, WPA, WPBA_Women, WPA_Women, WPA_Men, WPA_Artistic, WPA_Heyball_Men, WPA_Heyball_Women, and CP types."""
    if not is_valid_ranking_system_for_import(system):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or unsupported ranking system: {system}. Use GET /rankings/import/eligibility for allowed values.",
        )
    ext = (file.filename or "").split(".")[-1].lower()
    allowed = {"pdf", "docx", "xlsx", "xml", "csv", "txt"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed. Use: {', '.join(sorted(allowed))}")
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    from api.parsers.rankings_import import parse_file, parse_file_multi_columns

    db_manager = get_db_manager()

    # WPA Men/Women files often have one column per tournament (8-ball, 10-ball, 9-ball, Heyball, Artistic, etc.)
    # Map each column to the corresponding ranking button and save separately.
    if system in ("WPA_Men", "WPA_Women") and ext in ("xlsx", "csv", "txt"):
        multi = parse_file_multi_columns(content, file.filename or "", system)
        if multi:
            multi_keys = list(multi.keys())
            for rk in multi_keys:
                if not is_valid_ranking_system_for_import(rk):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parsed unsupported ranking system from file: {rk}",
                    )
            _ensure_director_ranking_write_allowed(user, multi_keys)
            counts = {}
            for ranking_system, rows in multi.items():
                ranking_list = [
                    {
                        "rank": r["rank"],
                        "name": r["name"],
                        "points": r["points"],
                        "country": r.get("country"),
                        "license_number": r.get("license_number"),
                        "stops_played": r.get("stops_played"),
                    }
                    for r in rows
                ]
                if ranking_system.startswith("Competitors_Pool_"):
                    counts[ranking_system] = db_manager.save_cp_rankings(ranking_list, ranking_type=ranking_system)
                else:
                    counts[ranking_system] = db_manager.save_wpa_rankings(ranking_list, ranking_type=ranking_system)
            if "WPA_Men" in counts:
                try:
                    split_result = db_manager.split_wpa_men_to_column_buttons()
                    logger.info("Post-import WPA Men (multi-column) column split: %s", split_result)
                except Exception as e:
                    logger.warning("Post-import WPA Men split failed: %s", e)
            if "WPA_Women" in counts:
                try:
                    split_result = db_manager.split_wpa_women_to_column_buttons()
                    logger.info("Post-import WPA Women (multi-column) column split: %s", split_result)
                except Exception as e:
                    logger.warning("Post-import WPA Women split failed: %s", e)
            try:
                db_manager.append_audit(
                    actor_role=user.get("role", "unknown"),
                    actor_subject=user.get("sub", "unknown"),
                    action="import_file",
                    details={"filename": file.filename, "system": system, "multi_column": True, "counts": counts},
                )
            except Exception as e:
                logger.warning(f"Audit log write failed: {e}")
            total = sum(counts.values())
            return {
                "message": f"Imported multi-column file into {len(counts)} ranking(s): {total} total rows.",
                "count": total,
                "system": system,
                "counts_by_ranking": counts,
            }

    _ensure_director_ranking_write_allowed(user, [system])

    rows = parse_file(content, file.filename or "")
    if not rows:
        try:
            db_manager.append_audit(
                actor_role=user.get("role", "unknown"),
                actor_subject=user.get("sub", "unknown"),
                action="import_file",
                details={"filename": file.filename, "system": system, "parsed": 0, "error": "No rows parsed"},
            )
        except Exception as e:
            logger.warning("Audit log write failed for empty import payload: %s", e)
        raise HTTPException(status_code=400, detail="No ranking rows could be parsed from the file. Check format (e.g. Position/Rank, Name, Points, Country).")

    # Pass through all parsed columns so imports (PDF/CSV/XLSX) persist license_number, stops_played, etc.
    ranking_list = [
        {
            "rank": r["rank"],
            "name": r["name"],
            "points": r["points"],
            "country": r.get("country"),
            "license_number": r.get("license_number"),
            "stops_played": r.get("stops_played"),
        }
        for r in rows
    ]

    # Map legacy systems to new ranking types
    ranking_type = system
    if system == "WPBA":
        ranking_type = "WPBA_Women"
    elif system == "WPA":
        ranking_type = "WPA_Women"

    # Save rankings with appropriate type
    if system in ("WPBA", "WPBA_Women"):
        count = db_manager.save_wpba_rankings(ranking_list, ranking_type=ranking_type)
    elif system.startswith("Competitors_Pool_"):
        count = db_manager.save_cp_rankings(ranking_list, ranking_type=ranking_type)
    else:  # WPA, WPA_Women, WPA_Men, WPA_Artistic, WPA_Heyball_Men, WPA_Heyball_Women
        count = db_manager.save_wpa_rankings(ranking_list, ranking_type=ranking_type)
        # After updating WPA Men/Women, re-split into per-column buttons (one button per event column)
        if system == "WPA_Men" or ranking_type == "WPA_Men":
            try:
                split_result = db_manager.split_wpa_men_to_column_buttons()
                logger.info("Post-import WPA Men column split: %s", split_result)
            except Exception as e:
                logger.warning("Post-import WPA Men split failed (overall WPA Men still saved): %s", e)
        if system == "WPA_Women" or ranking_type == "WPA_Women":
            try:
                split_result = db_manager.split_wpa_women_to_column_buttons()
                logger.info("Post-import WPA Women column split: %s", split_result)
            except Exception as e:
                logger.warning("Post-import WPA Women split failed (overall WPA Women still saved): %s", e)

    try:
        db_manager.append_audit(
            actor_role=user.get("role", "unknown"),
            actor_subject=user.get("sub", "unknown"),
            action="import_file",
            details={"filename": file.filename, "system": system, "count": count},
        )
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")
    return {"message": f"Imported {count} {system} rankings.", "count": count, "system": system}


class CopyFromImportRequest(BaseModel):
    """Request to copy latest snapshot from one ranking system to others (populate buttons from imported data)."""
    source: str  # e.g. WPA_Women, WPA_Men, WPBA_Women
    targets: List[str]  # e.g. [Competitors_Pool_9Ball, Competitors_Pool_10Ball, Competitors_Pool_8Ball]


@router.post("/copy-from-import")
async def copy_rankings_from_import(
    body: CopyFromImportRequest = Body(...),
    user: dict = Depends(require_director_or_admin),
):
    """Copy the latest snapshot from an imported ranking system to target systems. Director or Admin only.
    Use to populate CP (and other) ranking buttons from existing WPA_Women / WPA_Men / WPBA_Women data."""
    allowed_sources = ("WPBA_Women", "WPA_Women", "WPA_Men")
    allowed_targets = (
        "Competitors_Pool_9Ball", "Competitors_Pool_10Ball", "Competitors_Pool_8Ball",
        "Competitors_Pool_Mixed_9Ball", "WPA_Artistic",
        "WPA_Heyball_Women", "WPA_Heyball_Men",
    )
    if body.source not in allowed_sources:
        raise HTTPException(status_code=400, detail=f"source must be one of: {', '.join(allowed_sources)}")
    for t in body.targets:
        if t not in allowed_targets:
            raise HTTPException(status_code=400, detail=f"target not allowed: {t}")
    _ensure_director_ranking_write_allowed(user, [body.source] + list(body.targets))
    db_manager = get_db_manager()
    result = db_manager.copy_rankings_from_source_to_targets(body.source, body.targets)
    total = sum(result.values())
    return {
        "message": f"Copied {total} rankings from {body.source} to {len(body.targets)} system(s).",
        "source": body.source,
        "targets": result,
        "total": total,
    }


@router.post("/import/manual")
async def import_rankings_manual(
    body: ManualImportRequest = Body(...),
    user: dict = Depends(require_director_or_admin),
):
    """Import rankings from manually entered rows. Director or Admin only.
    Supports all ranking types: WPBA, WPA Men/Women, Heyball, Artistic, 8-Ball, 9-Ball, 10-Ball, etc."""
    if not is_valid_ranking_system_for_import(body.system):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or unsupported system: {body.system}. Use GET /rankings/import/eligibility.",
        )
    _ensure_director_ranking_write_allowed(user, [body.system])
    if not body.rows:
        raise HTTPException(status_code=400, detail="rows cannot be empty")
    ranking_list = [
        {
            "rank": r.rank,
            "name": r.name.strip(),
            "points": r.points or 0.0,
            "country": (r.country or "").strip() or None,
        }
        for r in body.rows
    ]
    db_manager = get_db_manager()

    ranking_type = body.system
    if body.system == "WPBA":
        ranking_type = "WPBA_Women"
    elif body.system == "WPA":
        ranking_type = "WPA_Women"

    if body.system in ("WPBA", "WPBA_Women"):
        count = db_manager.save_wpba_rankings(ranking_list, ranking_type=ranking_type)
    elif body.system.startswith("Competitors_Pool_"):
        count = db_manager.save_cp_rankings(ranking_list, ranking_type=ranking_type)
    else:
        count = db_manager.save_wpa_rankings(ranking_list, ranking_type=ranking_type)
        # After updating WPA Men/Women, re-split into per-column buttons (one button per event column)
        if body.system == "WPA_Men":
            try:
                split_result = db_manager.split_wpa_men_to_column_buttons()
                logger.info("Post-manual-import WPA Men column split: %s", split_result)
            except Exception as e:
                logger.warning("Post-manual-import WPA Men split failed (overall WPA Men still saved): %s", e)
        if body.system == "WPA_Women":
            try:
                split_result = db_manager.split_wpa_women_to_column_buttons()
                logger.info("Post-manual-import WPA Women column split: %s", split_result)
            except Exception as e:
                logger.warning("Post-manual-import WPA Women split failed (overall WPA Women still saved): %s", e)

    try:
        db_manager.append_audit(
            actor_role=user.get("role", "unknown"),
            actor_subject=user.get("sub", "unknown"),
            action="import_manual",
            details={"system": body.system, "count": count},
        )
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")
    return {"message": f"Imported {count} {body.system} rankings.", "count": count, "system": body.system}


@router.post("/notify-subscribe")
async def notify_subscribe(body: NotifySubscribeRequest = Body(...)):
    """Subscribe to email notifications when a player's ranking changes. No auth required."""
    email = (body.email or "").strip().lower()
    player_name = (body.player_name or "").strip()
    system = (body.system or "").upper()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if not player_name:
        raise HTTPException(status_code=400, detail="Player name required")
    if system not in ("WPBA", "WPA"):
        raise HTTPException(status_code=400, detail="system must be WPBA or WPA")
    try:
        db_manager = get_db_manager()
        token = db_manager.add_notify_subscription(email, player_name, system)
        return {"ok": True, "message": "Subscribed. You'll get an email when this player's ranking changes."}
    except Exception as e:
        logger.error(f"Notify subscribe failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notify-unsubscribe")
async def notify_unsubscribe(request: Request, token: str = Query(..., description="Unsubscribe token from notification email")):
    """Unsubscribe from ranking change emails. No auth. Returns HTML for browser or JSON if Accept: application/json."""
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    try:
        db_manager = get_db_manager()
        removed = db_manager.unsubscribe_notify_by_token(token)
        if removed:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                html = "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Unsubscribed</title></head><body><p>You have been unsubscribed from ranking change notifications.</p></body></html>"
                return HTMLResponse(html)
            return JSONResponse(content={"ok": True, "message": "Unsubscribed"})
        raise HTTPException(status_code=404, detail="Invalid or already used unsubscribe link")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notify unsubscribe failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# SQLite backup endpoint removed - using PostgreSQL only


@router.get("/movement")
async def get_movement(
    system: str = Query(..., description="WPBA or WPA"),
    limit: int = Query(50, ge=1, le=200, description="Max movement entries to return"),
):
    """Get recent ranking changes (movement) for a system. Newest first."""
    if system.upper() not in ("WPBA", "WPA"):
        raise HTTPException(status_code=400, detail="system must be WPBA or WPA")
    try:
        from sqlalchemy import text
        from database import get_engine
        
        engine = get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    player_name, 
                    ranking_system, 
                    old_rank, 
                    new_rank, 
                    old_points, 
                    new_points, 
                    change_date, 
                    change_type
                FROM ranking_changes
                WHERE ranking_system = :system
                ORDER BY change_date DESC, id DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"system": system.upper(), "limit": limit}).fetchall()
            
            entries = [
                {
                    "player_name": r[0],
                    "ranking_system": r[1],
                    "old_rank": r[2],
                    "new_rank": r[3],
                    "old_points": r[4],
                    "new_points": r[5],
                    "change_date": str(r[6]),
                    "change_type": r[7],
                }
                for r in rows
            ]
        return {"system": system.upper(), "movement": entries}
    except Exception as e:
        logger.error(f"Error fetching movement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def get_snapshot_dates(
    system: str = Query(..., description="WPBA or WPA"),
    limit: int = Query(30, ge=1, le=365, description="Max number of snapshot dates to return"),
):
    """Get list of snapshot dates for a system (for trend views). Newest first."""
    if system.upper() not in ("WPBA", "WPA"):
        raise HTTPException(status_code=400, detail="system must be WPBA or WPA")
    try:
        from sqlalchemy import text
        from database import get_engine
        
        engine = get_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT DISTINCT snapshot_date
                FROM rankings
                WHERE ranking_system = :system
                ORDER BY snapshot_date DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"system": system.upper(), "limit": limit}).fetchall()
            dates = [str(r[0]) for r in rows]
        
        return {"system": system.upper(), "snapshot_dates": dates}
    except Exception as e:
        logger.error(f"Error fetching snapshot dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/last-update")
async def get_last_update():
    """Get timestamp of last successful scrape for each association.
    On DB/startup failure returns 200 with null dates so the UI does not break.
    """
    try:
        db_manager = get_db_manager()
        wpba_update = db_manager.get_last_snapshot_date("WPBA_Women")
        wpa_update = db_manager.get_last_snapshot_date("WPA_Women")
        stale_after_hours = _stale_after_hours()
        return {
            "wpba": wpba_update,
            "wpa": wpa_update,
            "staleness": {
                "threshold_hours": stale_after_hours,
                "wpba": db_manager.get_staleness_info("WPBA_Women", stale_after_hours),
                "wpa": db_manager.get_staleness_info("WPA_Women", stale_after_hours),
            },
        }
    except Exception as e:
        logger.error("Error fetching last update: %s", e, exc_info=True)
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

@router.get("/audit")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to return"),
    _user: dict = Depends(require_director_or_admin),
):
    """Get recent audit log (who submitted what). Director or Admin only."""
    try:
        db_manager = get_db_manager()
        entries = db_manager.get_audit_log(limit=limit)
        return {"entries": entries}
    except Exception as e:
        logger.error(f"Error fetching audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players-without-fargo/export")
async def export_players_without_fargo(_user: dict = Depends(require_admin)):
    """Plain-text list of player names with no Fargo rating (Admin only)."""
    try:
        db_manager = get_db_manager()
        data = db_manager.get_players_without_fargo()
        names = [p["name"] for p in data.get("players", []) if p.get("name")]
        body = "\n".join(names) + ("\n" if names else "")
        return PlainTextResponse(body, media_type="text/plain; charset=utf-8")
    except Exception as e:
        logger.error("Error exporting players without Fargo: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players-without-fargo")
async def list_players_without_fargo(_user: dict = Depends(require_admin)):
    """JSON: players without Fargo from `players` and latest `rankings` rows (Admin only)."""
    try:
        db_manager = get_db_manager()
        return db_manager.get_players_without_fargo()
    except Exception as e:
        logger.error("Error listing players without Fargo: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality")
async def get_data_quality(_user: dict = Depends(require_director_or_admin)):
    """Run data quality checks: duplicate players, missing/invalid fields, point consistency. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        result = db_manager.run_quality_checks()
        return result
    except Exception as e:
        logger.error(f"Error running quality checks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dedupe")
async def remove_duplicate_rankings(_user: dict = Depends(require_admin)):
    """Remove duplicate rankings rows (same player_name, ranking_system, snapshot_date); keep min(id). Admin only."""
    try:
        db_manager = get_db_manager()
        result = db_manager.remove_duplicate_rankings()
        return {"message": "Duplicate rankings removed", **result}
    except Exception as e:
        logger.error(f"Error removing duplicate rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Tournament definitions (Director/Admin): name + points per place ---

@router.get("/tournament-definitions")
async def list_tournament_definitions(_user: dict = Depends(require_director_or_admin)):
    """List all tournament definitions. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        definitions = db_manager.get_tournament_definitions()
        return {"definitions": definitions}
    except Exception as e:
        logger.error(f"Error listing tournament definitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament-definitions")
async def create_tournament_definition(
    body: TournamentDefinitionCreate = Body(...),
    _user: dict = Depends(require_director_or_admin),
):
    """Create a tournament definition (name + points for 1st, 2nd, 3rd, ...). Director or Admin only."""
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not body.points_by_place:
        raise HTTPException(status_code=400, detail="points_by_place must have at least one value")
    try:
        db_manager = get_db_manager()
        definition_id = db_manager.create_tournament_definition(
            name=body.name.strip(),
            points_by_place=body.points_by_place,
            is_default_for_import=body.is_default_for_import or False,
        )
        definitions = db_manager.get_tournament_definitions()
        created = next((d for d in definitions if d["id"] == definition_id), None)
        return {"id": definition_id, "definition": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tournament definition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tournament-definitions/{definition_id:int}")
async def update_tournament_definition(
    definition_id: int,
    body: TournamentDefinitionUpdate = Body(...),
    _user: dict = Depends(require_director_or_admin),
):
    """Update a tournament definition. Director or Admin only."""
    if body.name is not None and not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="name cannot be empty")
    try:
        db_manager = get_db_manager()
        ok = db_manager.update_tournament_definition(
            definition_id,
            name=body.name.strip() if (body.name and body.name.strip()) else None,
            points_by_place=body.points_by_place,
            is_default_for_import=body.is_default_for_import,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Tournament definition not found")
        definitions = db_manager.get_tournament_definitions()
        updated = next((d for d in definitions if d["id"] == definition_id), None)
        return {"definition": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tournament definition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament-definitions/{definition_id:int}/set-default")
async def set_default_tournament_definition(
    definition_id: int,
    _user: dict = Depends(require_director_or_admin),
):
    """Set this tournament definition as the default used when importing from final_results.txt. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        ok = db_manager.set_tournament_definition_default(definition_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Tournament definition not found")
        definitions = db_manager.get_tournament_definitions()
        updated = next((d for d in definitions if d["id"] == definition_id), None)
        return {"definition": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default tournament definition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tournament-definitions/{definition_id:int}")
async def delete_tournament_definition(
    definition_id: int,
    _user: dict = Depends(require_director_or_admin),
):
    """Delete a tournament definition. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        ok = db_manager.delete_tournament_definition(definition_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Tournament definition not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tournament definition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Tournament imports (from file; fill weights, confirm, then update rankings) ---

@router.get("/tournament-imports")
async def list_tournament_imports(
    system: str = Query("WPBA", description="WPBA or WPA"),
    user: dict = Depends(require_director_or_admin),
):
    """List all tournament imports. Director or Admin only."""
    try:
        _ensure_tournament_imports_bucket_allowed(user, system)
        db_manager = get_db_manager()
        imports = db_manager.get_tournament_imports(system.upper())
        return {"imports": imports}
    except Exception as e:
        logger.error(f"Error listing tournament imports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tournament-imports/{import_id:int}")
async def get_tournament_import(
    import_id: int,
    user: dict = Depends(require_director_or_admin),
):
    """Get one tournament import. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        imp = db_manager.get_tournament_import(import_id)
        if not imp:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        _ensure_tournament_import_row_allowed(user, imp)
        return imp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tournament import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tournament-imports/{import_id:int}")
async def update_tournament_import(
    import_id: int,
    body: TournamentImportUpdate = Body(...),
    user: dict = Depends(require_director_or_admin),
):
    """Update tournament import name and/or point weights. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        imp = db_manager.get_tournament_import(import_id)
        if not imp:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        _ensure_tournament_import_row_allowed(user, imp)
        ok = db_manager.update_tournament_import(
            import_id,
            name=body.name.strip() if (body.name and body.name.strip()) else None,
            points_by_place=body.points_by_place,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        imp = db_manager.get_tournament_import(import_id)
        return {"import": imp}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tournament import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament-imports/{import_id:int}/confirm")
async def confirm_tournament_import(
    import_id: int,
    user: dict = Depends(require_director_or_admin),
):
    """Mark tournament import as confirmed (must have weights). Director or Admin only."""
    try:
        db_manager = get_db_manager()
        imp = db_manager.get_tournament_import(import_id)
        if not imp:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        _ensure_tournament_import_row_allowed(user, imp)
        ok = db_manager.confirm_tournament_import(import_id)
        if not ok:
            raise HTTPException(
                status_code=400,
                detail="Cannot confirm: enter point weights (1st, 2nd, 3rd, ...) and save first.",
            )
        imp = db_manager.get_tournament_import(import_id)
        return {"import": imp}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming tournament import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament-imports/update-rankings")
async def update_rankings_from_tournament_imports(
    system: str = Query("WPBA", description="WPBA or WPA"),
    user: dict = Depends(require_director_or_admin),
):
    """Merge all confirmed tournament imports into rankings and save (points-based calculation). Director or Admin only."""
    if system.upper() not in ("WPBA", "WPA"):
        raise HTTPException(status_code=400, detail="system must be WPBA or WPA")
    _ensure_tournament_ranking_merge_allowed(user, system)
    try:
        from tournament_tools.load_final_results import merge_confirmed_imports_to_rankings

        db_manager = get_db_manager()
        confirmed = db_manager.get_confirmed_tournament_imports(system.upper())
        if not confirmed:
            raise HTTPException(
                status_code=400,
                detail="No confirmed tournaments. Add tournament results, confirm them, then click Update rankings.",
            )
        merged = merge_confirmed_imports_to_rankings(confirmed)
        if system.upper() == "WPBA":
            count = db_manager.save_wpba_rankings(merged)
        else:
            count = db_manager.save_wpa_rankings(merged)
        try:
            db_manager.append_audit(
                actor_role=user.get("role", "unknown"),
                actor_subject=user.get("sub", "unknown"),
                action="update_rankings_from_tournament_imports",
                details={"system": system.upper(), "count": count, "tournaments_merged": len(confirmed)},
            )
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")
        return {"message": f"Rankings updated from {len(confirmed)} tournament(s).", "count": count, "system": system.upper()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rankings from tournament imports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tournament-imports/{import_id:int}")
async def delete_tournament_import(
    import_id: int,
    user: dict = Depends(require_director_or_admin),
):
    """Delete a tournament import. Director or Admin only."""
    try:
        db_manager = get_db_manager()
        imp = db_manager.get_tournament_import(import_id)
        if not imp:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        _ensure_tournament_import_row_allowed(user, imp)
        ok = db_manager.delete_tournament_import(import_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Tournament import not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tournament import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backup", dependencies=[Depends(require_admin)])
async def get_rankings_backup():
    """Download rankings database backup (Admin only)"""
    try:
        from database import get_database_manager
        import os
        from pathlib import Path

        db_manager = get_database_manager()

        # Create backup using existing backup_postgres.sh script
        import subprocess
        result = subprocess.run(
            ["/home/ansible/rankings-bot/scripts/backup_postgres.sh"],
            capture_output=True,
            text=True,
            cwd="/home/ansible/rankings-bot",
            timeout=300,
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Backup failed: {result.stderr}")

        # Find the latest backup file
        backup_dir = Path("/home/ansible/rankings-bot/backups")
        backup_files = list(backup_dir.glob("rankings_*.dump"))
        if not backup_files:
            raise HTTPException(status_code=500, detail="Backup created but file not found")

        latest_backup = max(backup_files, key=lambda p: p.stat().st_mtime)

        # Return the backup file
        return FileResponse(
            path=str(latest_backup),
            filename=latest_backup.name,
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error(f"Error creating rankings backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-tournaments")
async def detect_current_tournaments(_user: dict = Depends(require_admin)):
    """Detect current tournaments from all data sources and update UI. Admin only."""
    if not TournamentDetector or not DynamicUIUpdater:
        raise HTTPException(status_code=500, detail="Tournament management modules not available")

    try:
        logger.info("Starting tournament detection and UI update...")

        # Detect current tournaments
        detector = TournamentDetector()
        current_tournaments = detector.get_all_current_tournaments()

        # Update UI configuration
        updater = DynamicUIUpdater()
        ui_update_file = updater.export_ui_update()

        # Log results
        total_tournaments = sum(len(tournaments) for tournaments in current_tournaments.values())

        result = {
            "message": f"Detected {total_tournaments} current tournaments across {len(current_tournaments)} systems",
            "current_tournaments": current_tournaments,
            "ui_update_file": ui_update_file,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Tournament detection completed: {result['message']}")
        return result

    except Exception as e:
        logger.error(f"Error in tournament detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current-tournaments")
async def get_current_tournaments():
    """Get currently detected tournaments for UI display"""
    if not TournamentDetector:
        raise HTTPException(status_code=500, detail="Tournament management modules not available")

    try:
        detector = TournamentDetector()
        current_tournaments = detector.get_all_current_tournaments()

        return {
            "current_tournaments": current_tournaments,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching current tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_rankings_summary():
    """Get rankings summary statistics"""
    try:
        from sqlalchemy import text
        from database import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            total_result = conn.execute(text("SELECT COUNT(*) FROM rankings")).fetchone()
            update_result = conn.execute(text("SELECT MAX(snapshot_date) FROM rankings")).fetchone()
            tables = [
                row[0]
                for row in conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                ).fetchall()
            ]

        return {
            "total_players": total_result[0] if total_result else 0,
            "last_updated": update_result[0] if update_result else None,
            "tables": tables or ["rankings", "ranking_types", "org_metadata"]
        }
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


