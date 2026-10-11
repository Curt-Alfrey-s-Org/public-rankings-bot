"""
FARGO ratings API routes. Postgres only (get_database_manager).
Import from CSV/Excel via the /import endpoint.
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from database import get_database_manager
from api.auth import require_director_or_admin
from api.services import fargo_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fargo", tags=["fargo"])


class FargoRatingRow(BaseModel):
    player_name: str
    fargo_rating: float


class FargoImportRequest(BaseModel):
    system: str  # WPBA or WPA
    ratings: List[FargoRatingRow]


def _get_rankings_conn():
    """Shared rankings connection (DATABASE_URL)."""
    db = get_database_manager()
    return db.get_connection()


@router.get("/player/{player_id}")
async def get_player_fargo(player_id: str):
    """Return {player_id, fargo_rating, last_updated} for a player. Look up by player_name or by numeric id."""
    try:
        conn = _get_rankings_conn()
    except Exception as e:
        logger.warning("Rankings DB unavailable for Fargo player lookup: %s", e)
        raise HTTPException(status_code=503, detail="Rankings database temporarily unavailable")
    try:
        cursor = conn.cursor()
        # Postgres: id is integer; only use id lookup when player_id is numeric
        if player_id.isdigit():
            cursor.execute(
                """
                SELECT player_name, fargo_rating, fargo_last_updated
                FROM rankings
                WHERE id = %s
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (int(player_id),),
            )
        else:
            cursor.execute(
                """
                SELECT player_name, fargo_rating, fargo_last_updated
                FROM rankings
                WHERE player_name = %s
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (player_id,),
            )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Determine column structure to map properly
        cols = [desc[0] for desc in cursor.description]
        if isinstance(row, tuple):
            row_dict = dict(zip(cols, row))
        else:
            row_dict = dict(row)
            
        return {
            "player_id": row_dict["player_name"],
            "fargo_rating": row_dict["fargo_rating"],
            "last_updated": row_dict["fargo_last_updated"],
        }
    finally:
        conn.close()


@router.get("/org/{org_code}")
async def get_org_top_fargo(org_code: str):
    """Return top 100 players by FARGO rating for org."""
    conn = _get_rankings_conn()
    try:
        cursor = conn.cursor()
        
        systems = {
            "WPBA": "WPBA_Women",
            "WPA": "WPA_Women",
            "WPA_Men": "WPA_Men",
            "WPA_Heyball_Men": "WPA_Heyball_Men",
            "WPA_Heyball_Women": "WPA_Heyball_Women"
        }
        system = systems.get(org_code.upper(), org_code)

        cursor.execute(
            """
            SELECT player_name, fargo_rating, fargo_last_updated, rank, points
            FROM rankings
            WHERE ranking_system = %s
            AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = %s)
            AND fargo_rating IS NOT NULL
            ORDER BY fargo_rating DESC
            LIMIT 100
            """,
            (system, system),
        )
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        
        players = []
        for row in rows:
            r = dict(zip(cols, row)) if isinstance(row, tuple) else dict(row)
            players.append({
                "player_id": r["player_name"],
                "fargo_rating": r["fargo_rating"],
                "last_updated": r["fargo_last_updated"],
                "rank": r["rank"],
                "points": r["points"],
            })
            
        return {
            "org_code": org_code,
            "players": players,
        }
    finally:
        conn.close()


@router.post("/import")
async def import_fargo_manual(
    body: FargoImportRequest,
    _user: dict = Depends(require_director_or_admin),
):
    """
    Manually import Fargo ratings (e.g. from scraped CSV). Director or Admin only.
    Body: { "system": "WPBA" | "WPA", "ratings": [ {"player_name": "...", "fargo_rating": 650}, ... ] }.
    """
    system = (body.system or "WPBA").strip().upper()
    if system not in ("WPBA", "WPA"):
        raise HTTPException(status_code=400, detail="system must be WPBA or WPA")
    rows = [{"player_name": r.player_name.strip(), "fargo_rating": r.fargo_rating} for r in body.ratings if r.player_name.strip()]
    if not rows:
        raise HTTPException(status_code=400, detail="No valid ratings (player_name and fargo_rating required)")
    conn = get_database_manager().get_connection()
    try:
        updated, err = fargo_client.import_fargo_ratings_manual(conn, system, rows)
        if err:
            raise HTTPException(status_code=500, detail=err)
            
        # Invalidate rankings API cache after Fargo updates
        try:
            from api.routes.rankings import _write_cache_version
            _write_cache_version()
            logger.info("Rankings API cache invalidated after Fargo manual import")
        except Exception as e:
            logger.warning(f"Failed to invalidate rankings cache: {e}")
            
        return {"message": f"Imported {updated} Fargo ratings for {system}", "updated": updated, "system": system}
    finally:
        conn.close()


# --- Disabled scraping stubs (policy: CSV import only) ---

@router.post("/sync")
async def fargo_sync_disabled(
    org_code: str = "WPBA",
    wait: bool = False,
    full_refresh: bool = False,
    _user: dict = Depends(require_director_or_admin),
):
    """Fargo scraping/sync is disabled. Use the CSV import endpoint or scripts/import_fargo_csv.py."""
    raise HTTPException(
        status_code=410,
        detail="Fargo scraping is disabled. Use the CSV import feature for Fargo-aligned ratings. See POST /api/fargo/import or scripts/import_fargo_csv.py.",
    )


@router.get("/search")
async def fargo_search_disabled(name: str):
    """Fargo player search via external scraper is disabled. Returns empty (graceful)."""
    # Return empty list so callers (e.g. Dashboard disambig) degrade cleanly.
    # Real data comes from CSV import into the rankings/players tables.
    return {"players": []}


@router.get("/lookup")
async def fargo_lookup_disabled(name: str = ""):
    """Legacy lookup disabled."""
    raise HTTPException(
        status_code=410,
        detail="Fargo lookup is disabled. Import ratings via CSV or use stored values from /player/{id} or /org/{code}.",
    )
