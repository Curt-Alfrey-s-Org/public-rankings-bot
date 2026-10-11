"""
Alfa Rating API Routes.

Professional pool rating system that adjusts Fargo based on sustained
tournament performance patterns. Uses Model A (Conservative) weighting.

Key Principle:
    WPA/WPBA are professional non-handicapped tournaments. Variance in
    finish position is normal competitive variance, not sandbagging.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_database_manager
from api.auth import get_optional_user, require_director_or_admin
from api.rate_limiter import check_rate_limit
from api.services.alfa_engine import (
    compute_alfa_ratings,
    get_alfa_player,
    get_alfa_summary,
)
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alfa", tags=["alfa"])

# -----------------------------------------------------------------------------
# Pydantic Response Models
# -----------------------------------------------------------------------------


class AlfaRatingItem(BaseModel):
    """Single player in Alfa Rating list."""

    player_name: str
    rank: int
    points: float
    country: Optional[str] = None
    ranking_system: str
    fargo_rating: Optional[float] = None
    alfa_rating: Optional[float] = None  # Only populated for admin/super_admin
    deviation_from_fargo: Optional[float] = Field(
        None, description="Difference between Alfa and Fargo (±15 max)"
    )
    tournaments_analyzed: Optional[int] = Field(
        None, description="Number of tournaments used in pattern analysis"
    )


class AlfaRatingsResponse(BaseModel):
    """Response for GET /api/alfa/ratings."""

    total: int
    rankings: List[AlfaRatingItem]
    system: Optional[str] = None


class AlfaPlayerResponse(BaseModel):
    """Response for GET /api/alfa/player/{name}."""

    player_name: str
    rank: int
    points: float
    country: Optional[str] = None
    ranking_system: str
    fargo_rating: Optional[float] = None
    alfa_rating: Optional[float] = None  # Only populated for admin/super_admin
    deviation_from_fargo: Optional[float] = None
    tournaments_analyzed: Optional[int] = None


class AlfaSummaryResponse(BaseModel):
    """Response for GET /api/alfa/summary."""

    total_players: int
    systems: List[str]
    last_updated: Optional[str] = None


class AlfaRecomputeResponse(BaseModel):
    """Response for POST /api/alfa/recompute."""

    message: str
    total_computed: int


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _can_see_alfa_rating(user: Optional[dict]) -> bool:
    """Alfa rating visible only to admin and super_admin."""
    role = (user or {}).get("role") or ""
    return role in ("admin", "super_admin")


def _strip_alfa_from_list(items: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """Set alfa_rating to None for each item when user cannot see it."""
    return [{**p, "alfa_rating": None} for p in items]


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.get("/ratings", response_model=AlfaRatingsResponse)
async def get_alfa_ratings(
    system: Optional[str] = Query(None, description="Filter by ranking system (e.g. WPBA_Women)"),
    user: Optional[dict] = Depends(get_optional_user),
    db=Depends(get_db),
):
    """
    Get Alfa ratings for all players in the specified ranking system.
    
    Alfa rating is only visible to admin and super_admin users.
    """
    try:
        db_manager = get_database_manager()
        players = compute_alfa_ratings(db_manager, ranking_system=system)
        
        # Hide Alfa rating from non-admin users
        if not _can_see_alfa_rating(user):
            players = _strip_alfa_from_list(players)
        
        return AlfaRatingsResponse(
            total=len(players),
            rankings=[AlfaRatingItem(**p) for p in players],
            system=system,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Alfa ratings fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch Alfa ratings")


@router.get("/player/{player_name}", response_model=AlfaPlayerResponse)
async def get_alfa_player_route(
    player_name: str,
    user: Optional[dict] = Depends(get_optional_user),
    db=Depends(get_db),
):
    """
    Get Alfa rating data for a single player.
    
    Alfa rating is only visible to admin and super_admin users.
    """
    try:
        db_manager = get_database_manager()
        player = get_alfa_player(db_manager, player_name)
        
        if not player:
            raise HTTPException(
                status_code=404, 
                detail=f"Player '{player_name}' not found"
            )
        
        # Hide Alfa rating from non-admin users
        if not _can_see_alfa_rating(user):
            player = {**player, "alfa_rating": None}
        
        return AlfaPlayerResponse(**player)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Alfa player lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch player data")


@router.get("/summary", response_model=AlfaSummaryResponse)
async def get_alfa_summary_route(
    user: Optional[dict] = Depends(get_optional_user),
    db=Depends(get_db),
):
    """
    Get Alfa rating system summary statistics.
    
    Returns total players, ranking systems, and last update time.
    """
    try:
        db_manager = get_database_manager()
        summary = get_alfa_summary(db_manager)
        return AlfaSummaryResponse(**summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Alfa summary failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch Alfa summary")


@router.post("/recompute", response_model=AlfaRecomputeResponse)
async def post_alfa_recompute(
    _admin: dict = Depends(require_director_or_admin),
):
    """
    Trigger Alfa rating recomputation (director/admin only).
    
    Rate limited: 1 request per 5 minutes.
    """
    allowed, wait_time = check_rate_limit("alfa-recompute")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {int(wait_time)} seconds.",
        )
    
    try:
        db_manager = get_database_manager()
        players = compute_alfa_ratings(db_manager)
        return AlfaRecomputeResponse(
            message="Alfa ratings recomputed successfully",
            total_computed=len(players),
        )
    except Exception as e:
        logger.exception("Alfa recompute failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to recompute Alfa ratings")
