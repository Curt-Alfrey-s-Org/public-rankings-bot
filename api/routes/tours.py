"""
Tour/Series API Routes.
Multi-stop tours with series points.
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from database import get_database_manager
from api.auth import require_director_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tours", tags=["tours"])


class TourCreate(BaseModel):
    name: str
    year: int
    description: Optional[str] = None


class TourStopCreate(BaseModel):
    tournament_id: Optional[str] = None
    stop_number: int
    points_multiplier: float = 1.0


@router.get("/{tour_id}/stops", response_model=List[dict])
async def list_tour_stops(tour_id: str):
    """List stops in a tour."""
    db = get_database_manager()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tournament_id, stop_number, points_multiplier
            FROM tour_stops WHERE tour_id = %s ORDER BY stop_number
        """, (tour_id,))
        rows = cur.fetchall()
        return [
            {"id": r[0], "tournament_id": r[1], "stop_number": r[2], "points_multiplier": r[3]}
            for r in rows
        ]
    except Exception as e:
        if "does not exist" in str(e).lower():
            return []
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{tour_id}/stops", status_code=201)
async def add_tour_stop(tour_id: str, stop: TourStopCreate, _=Depends(require_director_or_admin)):
    """Add a stop to a tour. Director/admin only."""
    db = get_database_manager()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tour_stops (tour_id, tournament_id, stop_number, points_multiplier)
            VALUES (%s, %s, %s, %s)
        """, (tour_id, stop.tournament_id, stop.stop_number, stop.points_multiplier))
        conn.commit()
        return {"message": "Stop added"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
