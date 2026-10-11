"""
Tournament Management API Routes
RESTful endpoints for players, tournaments, matches, and rankings
"""

from datetime import date
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List, Optional
import logging
import traceback
import json
import asyncio
from sqlalchemy import text

from api.models.tournament_models import (
    PlayerCreate, PlayerUpdate, PlayerResponse, PlayerStatsResponse,
    TournamentCreate, TournamentUpdate, TournamentResponse, TournamentDetailResponse,
    TournamentTemplateCreate, TournamentTemplateResponse,
    BracketTemplateCreate, BracketTemplateResponse,
    TournamentPlayerRegister, TournamentPlayerResponse,
    MatchCreate, MatchUpdate, MatchScoreUpdate, MatchOutcomeUpdate, MatchResponse,
    GameCreate, GameUpdate, GameResponse,
    CurrentRankingResponse, HotStreakPlayerResponse, TournamentPerformanceResponse, TournamentTabCoverageResponse, TournamentTabCoverageListResponse,
    BulkPlayerRegister, GenerateBracketRequest, Stage2StartRequest
)
from api.tournament_manager import TournamentManager, DuplicatePlayerError
from api.auth import require_director_or_admin, get_current_user
from project_root import PROJECT_ROOT


# Use shared Postgres engine (same as get_database_manager)
import os
from database import get_engine
engine = get_engine()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


class ImportCompetitorsBody(BaseModel):
    slug: str = Field(..., min_length=1, max_length=220)
    generate_bracket: bool = True
    race_to: int = Field(7, ge=1, le=25)

# Initialize tournament manager with shared engine
tm = TournamentManager(engine)

# Default association tags for admin tournament dropdown (merged with DB distinct values).
_KNOWN_ASSOCIATION_TAGS = (
    "WPA_Women",
    "WPA_Men",
    "WPBA_Women",
    "WPBA",
    "WPA_Heyball_Men",
    "WPA_Heyball_Women",
    "WPA_Artistic",
    "LOCAL",
)


def _fetch_user_association_tags(username: Optional[str]) -> List[str]:
    """Associations linked to this login (director scoping)."""
    if not username:
        return []
    uname = str(username).strip().lower()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT ua.association FROM user_associations ua
                JOIN users u ON u.id = ua.user_id
                WHERE LOWER(u.username) = :u
                ORDER BY ua.association
                """
            ),
            {"u": uname},
        ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _association_choices_for_admin() -> List[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT association FROM user_associations ORDER BY association")
        ).fetchall()
    from_db = [str(r[0]) for r in rows if r and r[0]]
    merged = sorted(set(from_db) | set(_KNOWN_ASSOCIATION_TAGS))
    return merged


def _resolve_user_id(username: Optional[str]) -> Optional[int]:
    if not username:
        return None
    uname = str(username).strip().lower()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE LOWER(username) = :u LIMIT 1"),
            {"u": uname},
        ).fetchone()
    return int(row[0]) if row else None


def _validate_tournament_association_and_game_type(
    current_user: dict,
    association: Optional[str],
    game_type: Optional[str],
) -> tuple[str, Optional[str]]:
    """
    Returns (normalized association, game_type after WPBA defaults).
    Raises HTTPException on policy violations.
    """
    role = str(current_user.get("role") or "").strip().lower()
    assoc = (association or "").strip() or None
    gtype = (game_type or "").strip() or None

    if not assoc:
        raise HTTPException(
            status_code=400,
            detail="association is required (e.g. WPA_Women, WPBA_Women).",
        )

    if role == "director":
        allowed = set(_fetch_user_association_tags(current_user.get("sub")))
        if assoc not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You can only create tournaments for associations assigned to your director account.",
            )
    elif role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Director or Admin only")

    au = assoc.upper()
    if au.startswith("WPBA") or "WPBA" in au.replace("_", ""):
        if not gtype:
            gtype = "9_ball"
        elif gtype != "9_ball" and role not in ("admin", "super_admin"):
            raise HTTPException(
                status_code=403,
                detail="WPBA events use 9-ball by default. Only an admin can select a different game type.",
            )

    return assoc, gtype


def _row_to_bracket_template(row: dict) -> BracketTemplateResponse:
    r = dict(row)
    if isinstance(r.get("rounds"), str):
        r["rounds"] = json.loads(r["rounds"])
    return BracketTemplateResponse(**r)


def _has_pro_rating_access(user: dict) -> bool:
    """Live EST/ALFA ratings are PRO features for players; staff roles are always allowed."""
    role = str(user.get("role") or "").strip().lower()
    if role in {"admin", "director", "super_admin"}:
        return True

    username = str(user.get("sub") or "").strip()
    if not username:
        return False

    conn = engine.connect()
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
        tier = None
        if row:
            tier = (row[0] if not isinstance(row, dict) else row.get("tier"))
        return str(tier or "").strip().upper() == "PRO"
    except Exception:
        return False
    finally:
        conn.close()


# ==========================================
# PLAYER ENDPOINTS
# ==========================================

@router.post("/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(
    player: PlayerCreate,
    current_user: dict = Depends(require_director_or_admin),
):
    """Create a new player (director or admin)."""
    try:
        player_id = tm.create_player(player.model_dump(exclude_unset=True))
        player_data = tm.get_player(player_id)
        if not player_data:
            raise HTTPException(status_code=500, detail="Player created but not found")
        enriched = _enrich_player_license_overdue(dict(player_data))
        return PlayerResponse(**enriched)
    except DuplicatePlayerError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating player: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _enrich_player_license_overdue(p: dict) -> dict:
    """Add license_overdue: True if license_expiry_date < today."""
    exp = p.get("license_expiry_date")
    if not exp:
        p["license_overdue"] = False
        return p
    try:
        exp_date = date.fromisoformat(exp) if isinstance(exp, str) else exp
        p["license_overdue"] = exp_date < date.today()
    except (ValueError, TypeError):
        p["license_overdue"] = False
    return p


@router.get("/players", response_model=List[PlayerResponse])
async def get_all_players(
    active_only: bool = True,
    association: Optional[str] = Query(
        None,
        description="If set, only players who played in director tournaments with this association",
    ),
):
    """Get all players, optionally scoped to an association."""
    try:
        if association and association.strip():
            players = tm.get_players_for_association(association.strip(), active_only=active_only)
        else:
            players = tm.get_all_players(active_only=active_only)
        enriched = [_enrich_player_license_overdue(p) for p in players]
        return [PlayerResponse(**p) for p in enriched]
    except Exception as e:
        logger.error(f"Error getting players: {e}")
        logger.error("Players fetch failed for association=%s", association)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players/from-history", response_model=List[PlayerResponse])
async def get_players_from_association_history(
    association: str = Query(..., min_length=1, max_length=64),
    active_only: bool = True,
):
    """Players from past director tournaments in this association, most frequent first."""
    try:
        players = tm.get_players_for_association_by_frequency(
            association.strip(), active_only=active_only
        )
        enriched = [_enrich_player_license_overdue(p) for p in players]
        return [PlayerResponse(**p) for p in enriched]
    except Exception as e:
        logger.error(f"Error getting players from history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players/{player_id}", response_model=PlayerResponse)
async def get_player(player_id: str):
    """Get player by ID"""
    player = tm.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    enriched = _enrich_player_license_overdue(dict(player))
    return PlayerResponse(**enriched)


@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(player_id: str, updates: PlayerUpdate):
    """Update player information"""
    success = tm.update_player(player_id, updates.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    player = tm.get_player(player_id)
    enriched = _enrich_player_license_overdue(dict(player))
    return PlayerResponse(**enriched)


@router.post("/players/{player_id}/sync-fargo", response_model=PlayerResponse)
async def sync_player_fargo(player_id: str):
    """Removed: FairMatch Fargo scraping is disabled. Use CSV import for Fargo data."""
    raise HTTPException(
        status_code=410,
        detail="Fargo sync via FairMatch is disabled. Import ratings via the CSV import feature.",
    )


@router.post("/sync-all-fargo")
async def sync_all_fargo():
    """Removed: bulk Fargo scraping is disabled."""
    raise HTTPException(
        status_code=410,
        detail="Fargo sync via FairMatch is disabled. Import ratings via the CSV import feature.",
    )


@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(player_id: str):
    """Soft delete player (set to inactive)"""
    success = tm.delete_player(player_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")


@router.get("/players/{player_id}/stats", response_model=PlayerStatsResponse)
async def get_player_stats(player_id: str):
    """Get player statistics"""
    conn = tm.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM player_statistics WHERE player_id = %s", (player_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Stats for player {player_id} not found")
    
    return PlayerStatsResponse(**dict(row))


# ==========================================
# PROCESS WARNINGS (must be before /{tournament_id} to avoid path conflict)
# ==========================================

@router.post("/process-warnings")
async def process_warnings():
    """Process due table-call warnings (20/15/10/5/1 min) and match reminders. Sends emails."""
    try:
        table_result = tm.process_table_call_warnings()
        reminder_min = int(os.getenv("MATCH_REMINDER_MINUTES", "15"))
        reminder_result = tm.process_match_reminders(reminder_minutes=reminder_min)
        return {
            "message": "Warnings processed",
            "sent": table_result.get("sent", 0) + reminder_result.get("sent", 0),
            "errors": table_result.get("errors", 0) + reminder_result.get("errors", 0),
        }
    except Exception as e:
        logger.error(f"Error processing warnings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# COMPLETED RESULTS (dashboard/leaderboard)
# ==========================================

@router.get("/completed-results")
async def get_completed_results(limit: int = 20):
    """Get completed tournaments with winner and runner-up for dashboard/leaderboard."""
    try:
        rows = tm.get_completed_results(limit=limit)
        tournaments = [
            {
                "tournament_id": r["tournament_id"],
                "tournament_name": r["tournament_name"],
                "tournament_date": str(r["tournament_date"]) if r.get("tournament_date") else "",
                "first_place_name": r.get("winner_name"),
                "second_place_name": r.get("runner_up_name"),
                "third_place_name": None,
            }
            for r in rows
        ]
        return {"tournaments": tournaments}
    except Exception as e:
        logger.error(f"Error fetching completed results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# RANKINGS ENDPOINTS
# (Must come before /{tournament_id} routes to avoid path conflicts)
# ==========================================

@router.get("/rankings/current", response_model=List[CurrentRankingResponse])
async def get_current_rankings(
    limit: Optional[int] = None,
    system: Optional[str] = Query(None, description="Filter by ranking system (e.g. WPBA_Women, WPA_Women)")
):
    """Get current player rankings from rankings table (SINGLE SOURCE OF TRUTH for leaderboard/menu points, same as Rankings page).
    
    When system is provided, returns points for that association only (not summed across associations).
    When system is None, returns combined totals across all associations (default behavior).
    """
    try:
        from database import get_database_manager
        db = get_database_manager()
        rankings = db.get_leaderboard_from_rankings(limit=limit, ranking_system=system)
        return [CurrentRankingResponse(**r) for r in rankings]
    except Exception as e:
        logger.error(f"Error getting rankings: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hot-streak", response_model=List[HotStreakPlayerResponse])
async def get_hot_streak_players(
    lookback: int = Query(3, ge=2, le=6, description="Tournaments to consider per player"),
    min_tournaments: int = Query(3, ge=2, le=6, description="Minimum tournaments to qualify"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Max players to return"),
    association: Optional[str] = Query(None, description="Filter by association (WPBA, WPA Men, WPA Women, etc.)"),
):
    """Get players who jumped the most within the past N tournaments (improved placement)."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        players = db.get_hot_streak_players(lookback=lookback, min_tournaments=min_tournaments, limit=limit, association=association)
        return [HotStreakPlayerResponse(**r) for r in players]
    except Exception as e:
        logger.error(f"Error getting hot streak players: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hot-streak/fargo", response_model=List[HotStreakPlayerResponse])
async def get_fargo_hot_streak_players(
    lookback: int = Query(3, ge=2, le=6, description="Fargo ratings to consider per player"),
    min_tournaments: int = Query(3, ge=2, le=6, description="Minimum Fargo ratings to qualify"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Max players to return"),
    association: Optional[str] = Query(None, description="Filter by association (WPBA, WPA Men, WPA Women, etc.)"),
):
    """Get players whose Fargo ratings improved across the past N ratings."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        players = db.get_fargo_hot_streak_players(
            lookback=lookback,
            min_tournaments=min_tournaments,
            limit=limit,
            association=association,
        )
        return [HotStreakPlayerResponse(**r) for r in players]
    except Exception as e:
        logger.error(f"Error getting Fargo hot streak players: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{tournament_id}/performance", response_model=TournamentPerformanceResponse)
async def get_tournament_performance(tournament_id: str):
    """Get normalized player performance stats for a tournament history entry."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        performance = db.get_tournament_performance(tournament_id=tournament_id)
        if not performance:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        return TournamentPerformanceResponse(**performance)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tournament performance for {tournament_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{tournament_id}/tab-coverage", response_model=TournamentTabCoverageResponse)
async def get_tournament_tab_coverage(
    tournament_id: str,
    include_payload: bool = Query(
        False,
        description="Include full archived tab data (overview, players, brackets, matches) for UI",
    ),
):
    """Get latest archived tournament-tab snapshot for one tournament (coverage flags + optional payloads)."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        coverage = db.get_tournament_tab_coverage(tournament_id, include_payload=include_payload)
        if not coverage:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        return TournamentTabCoverageResponse(**coverage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tournament tab coverage for {tournament_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/tab-coverage", response_model=TournamentTabCoverageListResponse)
async def get_tournament_tab_coverage_list(
    limit: int = Query(50, ge=1, le=300),
    association: Optional[str] = Query(None, description="Filter by association"),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    incomplete_only: bool = Query(True, description="Only tournaments missing at least one tab"),
):
    """Get tab-ingestion coverage list for recent tournaments."""
    try:
        from database import get_database_manager
        db = get_database_manager()
        data = db.get_tournament_tab_coverage_list(
            limit=limit,
            association=association,
            year=year,
            incomplete_only=incomplete_only,
        )
        return TournamentTabCoverageListResponse(**data)
    except Exception as e:
        logger.error(f"Error getting tournament tab coverage list: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rankings/recalculate")
async def recalculate_rankings():
    """
    Sync director tournaments to rankings (LOCAL), then sync players from merged rankings.
    Rankings remains sole source of truth. No data loss.
    """
    try:
        from database import get_database_manager
        db = get_database_manager()
        sync_stats = db.sync_director_tournaments_to_rankings()
        players_ranked = db.sync_players_from_rankings()
        return {
            "message": "Rankings synced successfully (director → rankings → players)",
            "players_ranked": players_ranked,
            "updated": players_ranked,  # backward compat for frontend
            "director_sync": sync_stats,
        }
    except Exception as e:
        logger.error(f"Error recalculating rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# BRACKET TEMPLATES (draw size / rounds presets)
# ==========================================


@router.get("/bracket-templates", response_model=List[BracketTemplateResponse])
async def list_bracket_templates(
    association: Optional[str] = Query(None, max_length=64),
    current_user: dict = Depends(require_director_or_admin),
):
    """List system presets and templates for an association."""
    try:
        assoc = (association or "").strip() or None
        with engine.connect() as conn:
            if assoc:
                rows = conn.execute(
                    text(
                        """
                        SELECT * FROM bracket_templates
                        WHERE is_system = true
                           OR association IS NULL
                           OR association = :a
                        ORDER BY is_system DESC, name
                        """
                    ),
                    {"a": assoc},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text("SELECT * FROM bracket_templates ORDER BY is_system DESC, name")
                ).mappings().all()
        return [_row_to_bracket_template(dict(r)) for r in rows]
    except Exception as e:
        logger.exception("list_bracket_templates failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bracket-templates", response_model=BracketTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_bracket_template(
    body: BracketTemplateCreate,
    current_user: dict = Depends(require_director_or_admin),
):
    """Save a custom bracket layout as a reusable template."""
    uid = _resolve_user_id(current_user.get("sub"))
    try:
        rounds_json = json.dumps(body.rounds)
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO bracket_templates (
                        name, player_count, bracket_draw_size, format, bye_strategy,
                        rounds, association, is_system, created_by
                    ) VALUES (
                        :name, :pc, :bds, :fmt, :bye,
                        CAST(:rounds AS jsonb), :assoc, false, :uid
                    )
                    RETURNING *
                    """
                ),
                {
                    "name": body.name.strip(),
                    "pc": body.player_count,
                    "bds": body.bracket_draw_size,
                    "fmt": body.format,
                    "bye": body.bye_strategy,
                    "rounds": rounds_json,
                    "assoc": (body.association or "").strip() or None,
                    "uid": uid,
                },
            ).mappings().first()
        if not row:
            raise HTTPException(status_code=500, detail="Template insert failed")
        return _row_to_bracket_template(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_bracket_template failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bracket-templates/{template_id}", response_model=BracketTemplateResponse)
async def get_bracket_template(
    template_id: int,
    current_user: dict = Depends(require_director_or_admin),
):
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM bracket_templates WHERE id = :id"),
                {"id": template_id},
            ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Bracket template not found")
        return _row_to_bracket_template(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_bracket_template failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bracket-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bracket_template(
    template_id: int,
    current_user: dict = Depends(require_director_or_admin),
):
    try:
        uid = _resolve_user_id(current_user.get("sub"))
        role = str(current_user.get("role") or "").lower()
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT is_system, created_by FROM bracket_templates WHERE id = :id"),
                {"id": template_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Bracket template not found")
            if row["is_system"]:
                raise HTTPException(status_code=400, detail="Cannot delete a system template")
            if role not in ("admin", "super_admin") and row["created_by"] != uid:
                raise HTTPException(status_code=403, detail="You can only delete templates you created")
            conn.execute(
                text("DELETE FROM bracket_templates WHERE id = :id"),
                {"id": template_id},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("delete_bracket_template failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TOURNAMENT TEMPLATES
# (Must come before /{tournament_id} routes to avoid path conflicts)
# ==========================================

@router.post("/templates", response_model=TournamentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_tournament_template(template: TournamentTemplateCreate):
    """Create a tournament template for reuse"""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO tournament_templates (
                        template_name, elimination_type, max_players, points_structure, description, created_by
                    ) VALUES (:template_name, :elimination_type, :max_players, :points_structure, :description, :created_by)
                    RETURNING id
                """),
                {
                    "template_name": template.template_name,
                    "elimination_type": template.elimination_type,
                    "max_players": template.max_players,
                    "points_structure": json.dumps(template.points_structure),
                    "description": template.description,
                    "created_by": template.created_by,
                },
            )
            template_id = result.scalar_one()
            row = conn.execute(
                text("SELECT * FROM tournament_templates WHERE id = :template_id"),
                {"template_id": template_id},
            ).mappings().first()

        if not row:
            raise HTTPException(status_code=500, detail="Template created but not found")

        template_data = dict(row)
        template_data['points_structure'] = json.loads(template_data['points_structure'])
        
        return TournamentTemplateResponse(**template_data)
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=List[TournamentTemplateResponse])
async def get_all_templates():
    """Get all tournament templates"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM tournament_templates ORDER BY times_used DESC, template_name")
            )
            rows = result.mappings().all()

        templates = []
        for row in rows:
            template = dict(row)
            template['points_structure'] = json.loads(template['points_structure'])
            templates.append(TournamentTemplateResponse(**template))

        return templates
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}", response_model=TournamentTemplateResponse)
async def get_template(template_id: int):
    """Get tournament template by ID"""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM tournament_templates WHERE id = :template_id"),
                {"template_id": template_id},
            ).mappings().first()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        template = dict(row)
        template['points_structure'] = json.loads(template['points_structure'])
        
        return TournamentTemplateResponse(**template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TOURNAMENT ENDPOINTS
# ==========================================

@router.post("/", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED)
async def create_tournament(
    tournament: TournamentCreate,
    current_user: dict = Depends(require_director_or_admin),
):
    """Create a new tournament (director or admin). Association is required; WPBA defaults to 9-ball."""
    try:
        data = tournament.model_dump(exclude_unset=True)
        assoc, gtype = _validate_tournament_association_and_game_type(
            current_user,
            data.get("association"),
            data.get("game_type"),
        )
        data["association"] = assoc
        data["game_type"] = gtype
        data["created_by"] = current_user.get("sub")

        if data.get("tournament_end_date") and data.get("tournament_date"):
            if data["tournament_end_date"] < data["tournament_date"]:
                raise HTTPException(
                    status_code=400,
                    detail="tournament_end_date must be on or after tournament_date",
                )

        tournament_id = tm.create_tournament(data)
        tournament_data = tm.get_tournament(tournament_id)
        if not tournament_data:
            raise HTTPException(status_code=500, detail="Tournament created but not found")

        # Broadcast live update for new tournament
        from api.notifications import broadcast_tournament_created
        import asyncio

        asyncio.create_task(
            broadcast_tournament_created(
                {
                    "tournament_id": tournament_id,
                    "name": tournament_data.get("name"),
                    "status": tournament_data.get("status"),
                    "created_at": tournament_data.get("created_at"),
                }
            )
        )

        return TournamentResponse(**tournament_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[TournamentResponse])
async def get_all_tournaments(
    request: Request,
    status_filter: Optional[str] = None,
    include_test: bool = False,
):
    """Get all tournaments, optionally filtered by status. Include test tournaments if requested."""
    try:
        tournaments = tm.get_all_tournaments(status=status_filter)
        # Debug: log role and count for super_admin vs director visibility investigation
        role = "unknown"
        auth = (request.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            try:
                import jwt
                from api import auth as auth_lib
                payload = jwt.decode(auth[7:].strip(), auth_lib.SECRET_KEY, algorithms=[auth_lib.ALGORITHM])
                role = payload.get("role", "?")
            except Exception as e:
                logger.debug("JWT decode for logging: %s", e)
        logger.info("GET /api/tournaments role=%s status_filter=%s count=%d", role, status_filter, len(tournaments))

        # Add test tournaments if requested
        if include_test:
            from api.routes.test_tournaments import test_manager
            test_tournament = test_manager.get_current_tournament()
            if test_tournament and test_tournament.get('tournament_id'):
                # Convert test tournament to the expected format
                test_tournament_formatted = {
                    'tournament_id': test_tournament['tournament_id'],
                    'tournament_name': test_tournament['name'],
                    'tournament_date': test_tournament['start_date'].date() if hasattr(test_tournament['start_date'], 'date') else test_tournament['start_date'],
                    'location': test_tournament['location'],
                    'elimination_type': test_tournament['format'].replace('_elimination', ''),
                    'max_players': test_tournament['max_players'],
                    'tables_available': test_tournament['tables'],
                    'entry_fee_cents': test_tournament['entry_fee'] * 100,  # Convert to cents
                    'status': test_tournament['status'],
                    'points_structure': {'1': 1000, '2': 750, '3': 500, '4': 250},  # Default points structure
                    'num_groups': None,
                    'players_per_group': None,
                    'group_advance_count': None,
                    'group_format': None,
                    'created_at': test_tournament['start_date'],
                    'updated_at': test_tournament['start_date']
                }
                tournaments.insert(0, test_tournament_formatted)  # Add at the beginning

        return [TournamentResponse(**tournament) for tournament in tournaments]
    except Exception as e:
        logger.error(f"Error getting tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}", response_model=TournamentDetailResponse)
async def get_tournament(tournament_id: str):
    """Get tournament by ID with player list and match count"""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    
    # Get players
    players = tm.get_tournament_players(tournament_id)
    
    # Get match stats
    matches = tm.get_tournament_matches(tournament_id)
    completed_matches = len([m for m in matches if m['status'] == 'completed'])
    
    response_data = {
        **tournament,
        "players": players,
        "matches_count": len(matches),
        "completed_matches": completed_matches
    }
    
    return TournamentDetailResponse(**response_data)


@router.put("/{tournament_id}", response_model=TournamentResponse)
async def update_tournament(tournament_id: str, updates: TournamentUpdate):
    """Update tournament information"""
    success = tm.update_tournament(tournament_id, updates.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    
    tournament = tm.get_tournament(tournament_id)
    return TournamentResponse(**tournament)


@router.delete("/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tournament(tournament_id: str, _user: dict = Depends(require_director_or_admin)):
    """Delete a tournament. Director or Admin only."""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    success = tm.delete_tournament(tournament_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")


# ==========================================
# TOURNAMENT PLAYER REGISTRATION
# ==========================================

@router.post("/{tournament_id}/players", status_code=status.HTTP_201_CREATED)
async def register_player(tournament_id: str, registration: TournamentPlayerRegister):
    """Register a player for a tournament. If payment required, use payment-intent first. If full, use waitlist."""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    players = tm.get_tournament_players(tournament_id)
    max_players = int(tournament.get("max_players") or 32)
    if len(players) >= max_players:
        raise HTTPException(
            status_code=400,
            detail="Tournament full. Use POST /waitlist to join the waitlist.",
        )
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import get_entry_fee_cents, has_paid
        fee = get_entry_fee_cents(tournament_id, conn)
        if fee > 0 and not has_paid(tournament_id, registration.player_id, conn):
            raise HTTPException(
                status_code=402,
                detail="Payment required. Call POST /payment-intent first, complete payment, then register.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Registration payment pre-check skipped (payment tables may be unavailable): %s", e)
    finally:
        conn.close()
    success = tm.register_player(
        tournament_id,
        registration.player_id,
        registration.seed_position
    )
    if not success:
        raise HTTPException(status_code=400, detail="Player already registered or invalid data")

    # Broadcast live update for player registration
    from api.notifications import broadcast_player_registration
    import asyncio

    # Get player name for the broadcast
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT first_name, last_name FROM players WHERE player_id = :player_id
        """), {"player_id": registration.player_id}).first()

        player_name = f"{result[0]} {result[1]}" if result else registration.player_id

        # Run broadcast in background to not block response
        asyncio.create_task(broadcast_player_registration(
            tournament_id, player_name, "registered"
        ))

    return {"message": "Player registered successfully", "tournament_id": tournament_id, "player_id": registration.player_id}


@router.post("/{tournament_id}/payment-intent")
async def create_registration_payment_intent(tournament_id: str, body: dict):
    """Create Stripe PaymentIntent for tournament entry fee. Body: {player_id}. Returns client_secret for Stripe Elements."""
    player_id = body.get("player_id")
    if not player_id:
        raise HTTPException(status_code=400, detail="player_id required")
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import (
            get_entry_fee_cents,
            create_tournament_registration_intent,
            has_paid,
        )
        fee = get_entry_fee_cents(tournament_id, conn)
        if fee <= 0:
            raise HTTPException(status_code=400, detail="Tournament has no entry fee")
        if has_paid(tournament_id, player_id, conn):
            raise HTTPException(status_code=400, detail="Player has already paid")
        result = create_tournament_registration_intent(tournament_id, player_id, fee, conn)
        if not result:
            raise HTTPException(status_code=503, detail="Payment service unavailable")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment intent error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{tournament_id}/payment-confirm")
async def confirm_registration_payment(tournament_id: str, body: dict):
    """Confirm tournament payment and optionally register player. Body: {payment_intent_id, register_player: bool}."""
    intent_id = body.get("payment_intent_id")
    if not intent_id:
        raise HTTPException(status_code=400, detail="payment_intent_id required")
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import confirm_tournament_payment
        result = confirm_tournament_payment(intent_id, conn)
        if not result or result.get("tournament_id") != tournament_id:
            raise HTTPException(status_code=400, detail="Payment confirmation failed or mismatch")
        if body.get("register_player"):
            tournament = tm.get_tournament(tournament_id)
            players = tm.get_tournament_players(tournament_id)
            max_players = int(tournament.get("max_players") or 32)
            if len(players) < max_players:
                tm.register_player(tournament_id, result["player_id"])
        return {"message": "Payment confirmed", **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment confirm error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{tournament_id}/registration-settings")
async def get_registration_settings(tournament_id: str):
    """Get registration settings (entry fee, payment required) for a tournament."""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import get_registration_settings as _get
        return _get(tournament_id, conn)
    except Exception as e:
        logger.error("Registration settings error: %s", e)
        return {"entry_fee_cents": 0, "payment_required": 0}
    finally:
        conn.close()


@router.put("/{tournament_id}/registration-settings")
async def update_registration_settings(tournament_id: str, body: dict):
    """Update registration settings (director/admin). Body: {entry_fee_cents, payment_required}."""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    entry_fee_cents = int(body.get("entry_fee_cents", 0) or 0)
    payment_required = bool(body.get("payment_required", False))
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import upsert_registration_settings
        upsert_registration_settings(tournament_id, entry_fee_cents, payment_required, conn)
        return {"message": "Settings updated", "entry_fee_cents": entry_fee_cents, "payment_required": payment_required}
    except Exception as e:
        logger.error("Update registration settings error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{tournament_id}/waitlist")
async def add_to_waitlist(tournament_id: str, body: dict):
    """Add player to waitlist when tournament is full. Body: {player_id}."""
    player_id = body.get("player_id")
    if not player_id:
        raise HTTPException(status_code=400, detail="player_id required")
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    players = tm.get_tournament_players(tournament_id)
    max_players = int(tournament.get("max_players") or 32)
    if len(players) < max_players:
        raise HTTPException(status_code=400, detail="Tournament has spots. Register directly.")
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import add_to_waitlist as _add
        position = _add(tournament_id, player_id, conn)
        return {"message": "Added to waitlist", "position": position, "tournament_id": tournament_id}
    except Exception as e:
        logger.error("Waitlist error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{tournament_id}/waitlist")
async def get_waitlist(tournament_id: str):
    """Get waitlist for tournament."""
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    conn = tm.get_connection()
    try:
        from api.services.tournament_payment import get_waitlist as _get
        return {"waitlist": _get(tournament_id, conn)}
    except Exception as e:
        logger.error("Waitlist error: %s", e)
        return {"waitlist": []}
    finally:
        conn.close()


@router.post("/{tournament_id}/players/bulk", status_code=status.HTTP_201_CREATED)
async def register_players_bulk(tournament_id: str, registration: BulkPlayerRegister):
    """Register multiple players for a tournament"""
    registered = []
    failed = []
    
    for player_id in registration.player_ids:
        success = tm.register_player(tournament_id, player_id)
        if success:
            registered.append(player_id)
        else:
            failed.append(player_id)
    
    return {
        "message": f"Registered {len(registered)} players",
        "registered": registered,
        "failed": failed
    }


@router.post("/{tournament_id}/import-competitors")
async def import_competitors_endpoint(
    tournament_id: str,
    body: ImportCompetitorsBody,
    current_user: dict = Depends(require_director_or_admin),
):
    """Import players and bracket data from a CP (external pool) tournament slug."""
    from api.services.competitors_import import import_competitors_tournament

    try:
        result = import_competitors_tournament(
            tournament_id,
            body.slug.strip(),
            generate_bracket=body.generate_bracket,
            race_to=body.race_to,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("import_competitors failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tournament_id}/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_player(tournament_id: str, player_id: str):
    """Unregister a player from a tournament"""
    success = tm.unregister_player(tournament_id, player_id)
    if not success:
        raise HTTPException(status_code=404, detail="Player registration not found")


@router.post("/{tournament_id}/players/auto-fill")
async def auto_fill_players_from_rankings(
    tournament_id: str,
    user: dict = Depends(require_director_or_admin),
):
    """
    Fill tournament registration from top players in the tournament's ranking system (mv_latest_rankings).
    Requires tournament to have ranking_system set (e.g. from wizard step 1). Creates players if missing.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT ranking_system, max_players, status
                FROM tournaments
                WHERE tournament_id = :tournament_id
            """),
            {"tournament_id": tournament_id},
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Tournament not found")
        ranking_system, max_players, status_val = row
        ranking_system = (ranking_system or "").strip()
        max_players = int(max_players or 32)

    if not ranking_system:
        raise HTTPException(
            status_code=400,
            detail="Tournament has no ranking system set. Set 'Tournament for' in wizard step 1 first.",
        )

    # Current registered count
    current_players = tm.get_tournament_players(tournament_id)
    existing_ids = {p["player_id"] for p in current_players}
    needed = max(0, max_players - len(existing_ids))
    if needed == 0:
        return {"success": True, "added": 0, "message": "Tournament is already full"}

    # Top players from mv_latest_rankings
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT name, rank, points, license_number, fargo_rating, country
                FROM mv_latest_rankings
                WHERE ranking_system = :ranking_system
                ORDER BY rank ASC NULLS LAST
                LIMIT :limit
            """),
            {"ranking_system": ranking_system, "limit": max(needed, 128)},
        ).fetchall()

    added = 0
    for r in rows:
        if added >= needed:
            break
        name = (r[0] or "").strip()
        if not name:
            continue
        license_number = (r[3] or "").strip() if len(r) > 3 else ""
        country = r[5] if len(r) > 5 else None
        fargo_rating = r[4] if len(r) > 4 else None
        parts = name.split(None, 1)
        first_name = parts[0] if parts else name
        last_name = parts[1] if len(parts) > 1 else ""

        player_id = None
        with engine.connect() as conn:
            if license_number:
                row2 = conn.execute(
                    text("SELECT player_id FROM players WHERE TRIM(license_number) = :lic"),
                    {"lic": license_number},
                ).first()
                if row2:
                    player_id = row2[0]
            if not player_id:
                row2 = conn.execute(
                    text(
                        "SELECT player_id FROM players WHERE first_name = :fn AND last_name = :ln LIMIT 1"
                    ),
                    {"fn": first_name, "ln": last_name},
                ).first()
                if row2:
                    player_id = row2[0]
            if not player_id:
                try:
                    player_id = tm.create_player({
                        "first_name": first_name,
                        "last_name": last_name,
                        "license_number": license_number or None,
                        "nationality": country,
                        "fargo_score": int(fargo_rating) if fargo_rating is not None else None,
                    })
                except Exception as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        continue
                    raise

        if player_id and player_id not in existing_ids:
            seed_position = len(current_players) + added + 1
            if tm.register_player(tournament_id, player_id, seed_position):
                added += 1
                existing_ids.add(player_id)
                current_players.append({"player_id": player_id})

    return {"success": True, "added": added, "message": f"Added {added} player(s)"}


@router.post("/{tournament_id}/players/clear-registration")
async def clear_tournament_registration(
    tournament_id: str,
    user: dict = Depends(require_director_or_admin),
):
    """Remove all registered players from the tournament (director/admin only)."""
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT 1 FROM tournaments WHERE tournament_id = :tid"),
            {"tid": tournament_id},
        ).first()
        if not r:
            raise HTTPException(status_code=404, detail="Tournament not found")
        deleted = conn.execute(
            text("DELETE FROM tournament_players WHERE tournament_id = :tid RETURNING 1"),
            {"tid": tournament_id},
        ).fetchall()
        conn.commit()
        removed = len(deleted)
    return {"success": True, "removed": removed, "message": f"Cleared {removed} player(s)"}


@router.get("/{tournament_id}/players", response_model=List[TournamentPlayerResponse])
async def get_tournament_players(tournament_id: str):
    """Get all players registered for a tournament, enriched with current points/rank from rankings table (single source of truth)."""
    try:
        # Check if this is a test tournament
        from api.routes.test_tournaments import test_manager
        test_tournament = test_manager.get_current_tournament()
        if test_tournament and test_tournament.get('tournament_id') == tournament_id:
            # Return test tournament players
            players = test_manager.get_registered_players()
            # Convert to expected format for TournamentPlayerResponse
            formatted_players = []
            for player in players:
                formatted_player = {
                    'player_id': player['player_id'],
                    'first_name': player['name'].split()[0] if player['name'] else '',
                    'last_name': ' '.join(player['name'].split()[1:]) if player['name'] and len(player['name'].split()) > 1 else '',
                    'nickname': None,
                    'email': None,
                    'phone': None,
                    'license_number': None,
                    'license_expiry_date': None,
                    'avatar_url': None,
                    'fargo_score': player.get('fargo_rating'),
                    'fargo_robustness': None,
                    'fargo_last_sync': None,
                    'fargo_source': None,
                    'nationality': player.get('country'),
                    'hometown': None,
                    'state': None,
                    'membership_status': 'active',
                    'hall_of_fame': False,
                    'total_tournaments_played': 0,
                    'total_points': 0.0,
                    'current_rank': None,
                    'hot_streak_count': 0,
                    'tournament_player_id': f"{tournament_id}_{player['player_id']}",
                    'registered_at': '2026-03-05T20:00:00.000000',
                    'status': 'registered',
                    'seed': None,
                    'group_id': None,
                    'table_assigned': None,
                    'checked_in': False,
                    'checked_in_at': None,
                    'fargo_handicap': 0
                }
                formatted_players.append(formatted_player)
            return [TournamentPlayerResponse(**player) for player in formatted_players]

        # Regular tournament players: enrich with current points/rank from rankings (single source of truth)
        players = tm.get_tournament_players(tournament_id)

        # Get current leaderboard data for enrichment
        from database import get_database_manager
        db_manager = get_database_manager()
        leaderboard_data = db_manager.get_leaderboard_from_rankings(limit=None)

        # Create lookup map by player_id for enrichment
        leaderboard_by_player_id: Dict[str, Dict[str, Any]] = {
            p['player_id']: p for p in leaderboard_data if p.get('player_id')
        }

        # Enrich each player with current points/rank from rankings table
        for player in players:
            player_id = player.get('player_id')
            if player_id and player_id in leaderboard_by_player_id:
                leaderboard_entry = leaderboard_by_player_id[player_id]
                player['total_points'] = leaderboard_entry.get('total_points', 0.0)
                player['current_rank'] = leaderboard_entry.get('current_rank')

        return [TournamentPlayerResponse(**player) for player in players]
    except Exception as e:
        logger.error(f"Error getting tournament players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}/check-in/{player_id}")
async def check_in_player(tournament_id: str, player_id: str):
    """Record player check-in (scan QR code). Returns HTML for mobile display."""
    from fastapi.responses import HTMLResponse
    success = tm.record_check_in(tournament_id, player_id)
    if not success:
        raise HTTPException(status_code=404, detail="Player not registered for this tournament")
    player = tm.get_player(player_id)
    name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip() if player else player_id
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Checked In</title></head><body style="font-family:sans-serif;text-align:center;padding:2rem;background:#0f172a;color:#e2e8f0;"><h1 style="color:#22c55e;">✓ Checked in!</h1><p>{name}</p></body></html>"""
    return HTMLResponse(content=html)


@router.get("/{tournament_id}/table-calls")
async def get_table_calls(tournament_id: str):
    """Get table calls for a tournament (report-to-table with warnings)."""
    try:
        return tm.get_table_calls(tournament_id)
    except Exception as e:
        logger.error(f"Error getting table calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/table-calls")
async def create_table_call(tournament_id: str, body: dict):
    """Create a table call for a match. Body: match_id, table_number, report_by (ISO), warning_minutes (optional)."""
    from datetime import datetime
    try:
        match_id = body.get("match_id")
        table_number = body.get("table_number")
        report_by = body.get("report_by")
        warning_minutes = body.get("warning_minutes", [20, 15, 10, 5, 1])
        if not match_id or not table_number or not report_by:
            raise HTTPException(status_code=400, detail="match_id, table_number, report_by required")
        try:
            report_dt = datetime.fromisoformat(str(report_by).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="report_by must be ISO datetime")
        result = tm.create_table_call(
            tournament_id=tournament_id,
            match_id=match_id,
            table_number=int(table_number),
            report_by_utc=report_dt,
            warning_minutes=warning_minutes,
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create table call")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating table call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}/stream")
async def stream_tournament_events(tournament_id: str):
    """SSE stream for live bracket updates. Sends match_score_update, match_completed, tournament_progress."""
    from api.services.tournament_events import get_events_since
    async def event_generator():
        last_index = 0
        for _ in range(360):  # ~1 hour at 10s intervals
            try:
                # Send any new events
                events = get_events_since(tournament_id, last_index)
                last_index += len(events)
                for ev in events:
                    yield f"data: {json.dumps(ev)}\n\n"
                # Always send progress
                matches = tm.get_tournament_matches(tournament_id)
                total = len([m for m in matches if m.get("status") != "bye"])
                completed = len([m for m in matches if m.get("status") == "completed"])
                percent = round(100.0 * completed / total, 1) if total > 0 else 0.0
                data = json.dumps({"type": "tournament_progress", "completed": completed, "total": total, "percent": percent})
                yield f"data: {data}\n\n"
            except Exception:
                logger.warning("SSE tournament stream loop encountered an error", exc_info=True)
            await asyncio.sleep(10)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{tournament_id}/progress")
async def get_tournament_progress(tournament_id: str):
    """Get tournament completion percentage (completed matches / total matches, excluding byes)"""
    try:
        matches = tm.get_tournament_matches(tournament_id)
        total = len([m for m in matches if m.get("status") != "bye"])
        completed = len([m for m in matches if m.get("status") == "completed"])
        percent = round(100.0 * completed / total, 1) if total > 0 else 0.0
        return {"tournament_id": tournament_id, "completed": completed, "total": total, "percent": percent}
    except Exception as e:
        logger.error(f"Error getting tournament progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# BRACKET GENERATION
# ==========================================

@router.post("/{tournament_id}/generate-bracket")
async def generate_bracket(tournament_id: str, request: GenerateBracketRequest):
    """Generate tournament bracket and matches"""
    try:
        matches_created = tm.generate_bracket(
            tournament_id,
            race_to=request.race_to,
            shuffle_seeds=request.shuffle_seeds,
            bye_player_ids=request.bye_player_ids,
            bye_seed_positions=request.bye_seed_positions,
        )
        return {
            "message": "Bracket generated successfully",
            "tournament_id": tournament_id,
            "matches_created": matches_created
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating bracket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tournament_id}/start-stage2")
async def start_stage2(tournament_id: str, request: Stage2StartRequest):
    """Start stage 2 bracket for a tournament"""
    try:
        result = tm.start_stage2(
            tournament_id,
            cutoff=request.cutoff,
            advancing_player_ids=request.advancing_player_ids,
            seed_strategy=request.seed_strategy,
            race_to=request.race_to,
            bye_player_ids=request.bye_player_ids,
            bye_seed_positions=request.bye_seed_positions,
        )
        return {
            "message": "Stage 2 started",
            "tournament_id": tournament_id,
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting stage 2: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/apply-fargo-handicaps")
async def apply_fargo_handicaps(tournament_id: str):
    """Apply Fargo-based handicaps to all matches in tournament"""
    result = tm.apply_fargo_handicaps(tournament_id)
    return result


@router.post("/{tournament_id}/submit-fargo")
async def submit_tournament_to_fargo(tournament_id: str):
    """Submit completed tournament results to Fargo Rate (when FARGO_SUBMIT_URL + FARGO_SUBMIT_ENABLED configured)"""
    from api.services.fargo_submit import (
        collect_tournament_results,
        submit_to_fargo,
    )
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
    matches = tm.get_tournament_matches(tournament_id)
    players = tm.get_all_players(active_only=False)
    players_by_id = {p["player_id"]: p for p in players}
    results = collect_tournament_results(tournament_id, matches, players_by_id)
    if not results:
        return {"message": "No completed matches to submit", "submitted": 0}
    outcome = submit_to_fargo(
        tournament_id,
        tournament.get("tournament_name", ""),
        results,
    )
    if outcome.get("error"):
        raise HTTPException(status_code=502, detail=outcome["error"])
    return {"message": "Results submitted to Fargo", "submitted": outcome["submitted"]}


# ==========================================
# MATCH ENDPOINTS
# ==========================================

@router.get("/{tournament_id}/matches", response_model=List[MatchResponse])
async def get_tournament_matches(tournament_id: str):
    """Get all matches for a tournament (with projected start/end times)"""
    try:
        # Check if this is a test tournament
        from api.routes.test_tournaments import test_manager
        test_tournament = test_manager.get_current_tournament()
        if test_tournament and test_tournament.get('tournament_id') == tournament_id:
            # Return test tournament matches
            matches = test_manager.get_matches()
            # Convert to expected format for MatchResponse
            formatted_matches = []
            for match in matches:
                formatted_match = {
                    'match_id': match['match_id'],
                    'tournament_id': match['tournament_id'],
                    'bracket_type': 'winners',  # Default to winners bracket
                    'round_number': 1,  # Default round
                    'status': match['status'],
                    'table_number': match.get('table_number'),
                    'scheduled_time': None,
                    'winner_id': match.get('winner_id'),
                    'operator_id': match.get('operator_id'),
                    'player2_id': match.get('player2_id'),
                    'operator_name': match.get('operator_name'),
                    'player2_name': match.get('player2_name'),
                    'operator_score': match.get('operator_score'),
                    'player2_score': match.get('player2_score'),
                    'race_to': 9,  # Default race to 9
                    'handicap1': 0,
                    'handicap2': 0,
                    'projected_start_time': None,
                    'projected_end_time': None
                }
                formatted_matches.append(formatted_match)
            return [MatchResponse(**match) for match in formatted_matches]

        # Regular tournament matches
        matches = tm.get_tournament_matches(tournament_id)
        tournament = tm.get_tournament(tournament_id)
        td = tournament.get("tournament_date") if tournament else None
        tournament_date = td.isoformat() if hasattr(td, "isoformat") else str(td or "")
        from api.services.projected_times import compute_projected_times
        matches = compute_projected_times(matches, tournament_date=tournament_date)
        return [MatchResponse(**match) for match in matches]
    except Exception as e:
        logger.error(f"Error getting matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MatchFieldUpdate(BaseModel):
    table_number: Optional[int] = None
    notes: Optional[str] = None
    scheduled_time: Optional[str] = None


@router.patch("/matches/{match_id}")
async def update_match(match_id: str, body: MatchFieldUpdate):
    """Update match fields (table_number, notes, scheduled_time, etc.)"""
    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    success = tm.update_match(match_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return {"message": "Match updated", "match_id": match_id}


@router.patch("/matches/{match_id}/outcome")
async def set_match_outcome(match_id: str, body: MatchOutcomeUpdate):
    """Director records forfeit or DQ with reason"""
    if body.outcome.lower() not in ("forfeit", "dq"):
        raise HTTPException(status_code=400, detail="outcome must be 'forfeit' or 'dq'")
    try:
        success = tm.set_match_outcome(
            match_id,
            outcome=body.outcome.lower(),
            reason=body.reason,
            winner_id=body.winner_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
        try:
            from api.services.live_odds_engine import recompute_and_broadcast_live_odds
            recompute_and_broadcast_live_odds(
                tm,
                match_id,
                trigger="state_change",
                extra_context={"outcome": body.outcome.lower(), "reason": body.reason},
            )
        except Exception as odds_err:
            logger.warning("live odds after outcome failed: %s", odds_err)
        return {"message": f"Match {match_id} marked as {body.outcome}", "match_id": match_id}
    except Exception as e:
        logger.error(f"Error setting match outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/matches/{match_id}/score")
async def update_match_score(match_id: str, score: MatchScoreUpdate):
    """Update match score and determine winner"""
    try:
        success = tm.update_match_score(
            match_id,
            score.operator_score,
            score.player2_score,
            score.status
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

        # Live odds (score-state) — Phase 3
        odds_payload = None
        try:
            from api.services.live_odds_engine import recompute_and_broadcast_live_odds
            odds_payload = recompute_and_broadcast_live_odds(
                tm, match_id, trigger="score_update"
            )
        except Exception as odds_err:
            logger.warning("live odds after score update failed: %s", odds_err)

        # Broadcast live update for match score change
        from api.notifications import broadcast_match_score_update
        import asyncio

        # Get tournament_id for the match
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tournament_id, operator_id, player2_id, winner_id
                FROM matches WHERE match_id = :match_id
            """), {"match_id": match_id}).first()

            if result:
                tournament_id = result[0]
                payload = {
                    "operator_score": score.operator_score,
                    "player2_score": score.player2_score,
                    "status": score.status,
                    "operator_id": result[1],
                    "player2_id": result[2],
                    "winner_id": result[3],
                }
                if odds_payload:
                    payload["odds"] = odds_payload
                # Run broadcast in background to not block response
                asyncio.create_task(broadcast_match_score_update(
                    match_id,
                    tournament_id,
                    payload,
                ))
                try:
                    from api.services.live_topics import Topic
                    from api.services.live_updates import notify_data_changed
                    from api.services.tournament_events import emit as emit_tournament_event
                    notify_data_changed(Topic.SCORES.value, message="Match score updated")
                    emit_tournament_event(
                        tournament_id,
                        "match_score_update",
                        {
                            "match_id": match_id,
                            "operator_score": score.operator_score,
                            "player2_score": score.player2_score,
                            "odds": odds_payload,
                        },
                    )
                except Exception as notify_err:
                    logger.warning("notify_data_changed failed (match score): %s", notify_err)

        out = {"message": "Match score updated successfully", "match_id": match_id}
        if odds_payload:
            out["odds"] = odds_payload
        return out
    except Exception as e:
        logger.error(f"Error updating match score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matches/{match_id}/calculate-handicap")
async def calculate_match_handicap(match_id: str):
    """Calculate Fargo-based handicap suggestion for a match"""
    result = tm.calculate_match_handicap(match_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found or has no players")
    return result


@router.get("/matches/{match_id}/odds")
async def get_match_live_odds(match_id: str):
    """Latest in-match win odds (live_odds_v1). Computes if no snapshot yet."""
    from api.services.live_odds_engine import LiveOddsEngine

    engine = LiveOddsEngine(tm)
    latest = engine.get_latest(match_id)
    if latest:
        return latest
    # Compute on the fly without forcing persist when match missing players is ok
    computed = engine.process_match(match_id, trigger="on_demand", persist=True)
    if not computed:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found or incomplete")
    return computed


@router.get("/matches/{match_id}/odds/history")
async def get_match_live_odds_history(
    match_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Odds snapshot history for tuning / post-event analysis."""
    from api.services.live_odds_engine import LiveOddsEngine

    engine = LiveOddsEngine(tm)
    match = tm.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return {"match_id": match_id, "snapshots": engine.get_history(match_id, limit=limit)}


@router.post("/matches/{match_id}/notify")
async def notify_match(match_id: str):
    """Send match notification to players (email/SMS per prefs). Uses Twilio/SNS when configured."""
    try:
        match = tm.get_match(match_id)
        if not match:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
        p1_id, p2_id = match.get("operator_id"), match.get("player2_id")
        if not p1_id or not p2_id:
            raise HTTPException(status_code=400, detail="Match has no players assigned")
        from api.services.sms_match_call import notify_match_players
        p1 = tm.get_player(p1_id) or {}
        p2 = tm.get_player(p2_id) or {}
        p1_name = f"{p1.get('first_name', '')} {p1.get('last_name', '')}".strip() or "Opponent"
        p2_name = f"{p2.get('first_name', '')} {p2.get('last_name', '')}".strip() or "Opponent"
        sent = notify_match_players(
            p1_phone=p1.get("phone"),
            p2_phone=p2.get("phone"),
            p1_name=p1_name,
            p2_name=p2_name,
            table_number=match.get("table_number"),
            race_to=int(match.get("race_to") or 7),
        )
        logger.info(f"Match notify for {match_id}: SMS sent to {sent}")
        return {"message": "Notification sent", "match_id": match_id, "sms_sent_to": sent}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error notifying match: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GAME/RACK ENDPOINTS
# ==========================================

@router.post("/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def submit_game_result(game: GameCreate, user: dict = Depends(require_director_or_admin)):
    """Submit a game/rack result within a match. Director/Admin only."""
    try:
        # Validate that the match exists and belongs to an active tournament
        with engine.connect() as conn:
            match_result = conn.execute(text("""
                SELECT m.tournament_id, m.operator_id, m.player2_id, m.status, m.race_to,
                       t.status as tournament_status
                FROM matches m
                JOIN tournaments t ON m.tournament_id = t.tournament_id
                WHERE m.match_id = :match_id
            """), {"match_id": game.match_id}).first()

            if not match_result:
                raise HTTPException(status_code=404, detail=f"Match {game.match_id} not found")

            tournament_id = match_result[0]
            operator_id = match_result[1]
            player2_id = match_result[2]
            match_status = match_result[3]
            race_to = match_result[4] or 7  # Default race_to if not set
            tournament_status = match_result[5]

            # Validate that winner is one of the players in the match
            if game.winner_id not in [operator_id, player2_id]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Winner {game.winner_id} is not a player in match {game.match_id}"
                )

            # Validate that breaking player is one of the players (if provided)
            if game.breaking_player_id and game.breaking_player_id not in [operator_id, player2_id]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Breaking player {game.breaking_player_id} is not a player in match {game.match_id}"
                )

        # Create the game record
        game_id = tm.create_game(
            match_id=game.match_id,
            game_number=game.game_number,
            winner_id=game.winner_id,
            breaking_player_id=game.breaking_player_id,
            innings=game.innings,
            run_out=game.run_out,
            break_and_run=game.break_and_run,
            notes=game.notes
        )

        # Synchronize match score from all games
        tm.synchronize_match_score_from_games(game.match_id)

        # Get the created game data
        game_data = tm.get_game(game_id)
        if not game_data:
            raise HTTPException(status_code=500, detail="Game created but not found")

        # Add player names for response
        game_data = dict(game_data)
        winner_name = None
        breaking_player_name = None

        if game_data.get('winner_id'):
            winner = tm.get_player(game_data['winner_id'])
            winner_name = f"{winner['first_name']} {winner['last_name']}" if winner else None

        if game_data.get('breaking_player_id'):
            breaker = tm.get_player(game_data['breaking_player_id'])
            breaking_player_name = f"{breaker['first_name']} {breaker['last_name']}" if breaker else None

        game_data['winner_name'] = winner_name
        game_data['breaking_player_name'] = breaking_player_name

        # Update live ratings for both players
        from api.services.live_rating_engine import LiveRatingEngine, GameContext
        from api.notifications import broadcast_rack_completed
        import asyncio

        rating_engine = LiveRatingEngine(tm)

        # Get opponent information
        p1 = tm.get_player(operator_id)
        p2 = tm.get_player(player2_id)
        p1_name = f"{p1['first_name']} {p1['last_name']}" if p1 else "Unknown"
        p2_name = f"{p2['first_name']} {p2['last_name']}" if p2 else "Unknown"
        opponent_id = operator_id if game.winner_id == player2_id else player2_id
        opponent_name = p1_name if game.winner_id == player2_id else p2_name

        # Create game context for winner
        winner_context = GameContext(
            game_id=game_id,
            match_id=game.match_id,
            tournament_id=tournament_id,
            player_id=game.winner_id,
            opponent_id=opponent_id,
            player_name=winner_name,
            opponent_name=opponent_name,
            outcome='win',
            opponent_rating=None,  # Will be fetched by engine
            game_metadata={
                'game_number': game.game_number,
                'breaking_player_id': game.breaking_player_id,
                'breaking_player_name': breaking_player_name,
                'run_out': game.run_out,
                'break_and_run': game.break_and_run,
                'innings': game.innings
            }
        )

        # Create game context for loser
        loser_context = GameContext(
            game_id=game_id,
            match_id=game.match_id,
            tournament_id=tournament_id,
            player_id=opponent_id,
            opponent_id=game.winner_id,
            player_name=opponent_name,
            opponent_name=winner_name,
            outcome='loss',
            opponent_rating=None,  # Will be fetched by engine
            game_metadata={
                'game_number': game.game_number,
                'breaking_player_id': game.breaking_player_id,
                'breaking_player_name': breaking_player_name,
                'run_out': game.run_out,
                'break_and_run': game.break_and_run,
                'innings': game.innings
            }
        )

        # Update ratings for both players
        winner_transition = rating_engine.process_game_completion(winner_context)
        loser_transition = rating_engine.process_game_completion(loser_context)

        # Live odds after rack + EST update (Phase 3)
        odds_payload = None
        try:
            from api.services.live_odds_engine import recompute_and_broadcast_live_odds
            odds_payload = recompute_and_broadcast_live_odds(
                tm,
                game.match_id,
                trigger="rack",
                game_id=game_id,
                extra_context={
                    "game_number": game.game_number,
                    "breaking_player_id": game.breaking_player_id,
                    "break_and_run": game.break_and_run,
                },
            )
        except Exception as odds_err:
            logger.warning("live odds after rack failed: %s", odds_err)

        # Broadcast live rack completion event with rating updates
        rack_data = {
            "game_id": game_id,
            "game_number": game.game_number,
            "winner_id": game.winner_id,
            "winner_name": winner_name,
            "loser_id": opponent_id,
            "loser_name": opponent_name,
            "breaking_player_id": game.breaking_player_id,
            "breaking_player_name": breaking_player_name,
            "run_out": game.run_out,
            "break_and_run": game.break_and_run,
            "completed_at": game_data.get('completed_at'),
            "rating_updates": {},
            "odds": odds_payload,
        }

        # Include rating changes if available
        if winner_transition:
            rack_data["rating_updates"][game.winner_id] = {
                "previous_rating": winner_transition.previous_rating,
                "new_rating": winner_transition.new_rating,
                "change": winner_transition.change_amount,
                "confidence": winner_transition.confidence,
                "robustness": winner_transition.robustness
            }

        if loser_transition:
            rack_data["rating_updates"][opponent_id] = {
                "previous_rating": loser_transition.previous_rating,
                "new_rating": loser_transition.new_rating,
                "change": loser_transition.change_amount,
                "confidence": loser_transition.confidence,
                "robustness": loser_transition.robustness
            }

        asyncio.create_task(broadcast_rack_completed(
            game.match_id,
            tournament_id,
            rack_data
        ))

        # Tournament SSE stream + global live-updates (scores/rankings cache bust)
        try:
            from api.services.tournament_events import emit as emit_tournament_event
            from api.services.live_topics import Topic
            from api.services.live_updates import notify_data_changed

            match_after = tm.get_match(game.match_id)
            if match_after:
                emit_tournament_event(
                    tournament_id,
                    "rack_completed",
                    {
                        "match_id": game.match_id,
                        "game_id": game_id,
                        "game_number": game.game_number,
                        "winner_id": game.winner_id,
                        "operator_score": match_after.get("operator_score"),
                        "player2_score": match_after.get("player2_score"),
                        "status": match_after.get("status"),
                        "rating_updates": rack_data.get("rating_updates") or {},
                        "odds": odds_payload,
                    },
                )
                emit_tournament_event(
                    tournament_id,
                    "match_score_update",
                    {
                        "match_id": game.match_id,
                        "operator_score": match_after.get("operator_score"),
                        "player2_score": match_after.get("player2_score"),
                        "odds": odds_payload,
                    },
                )
                if match_after.get("status") == "completed" and match_after.get("winner_id"):
                    emit_tournament_event(
                        tournament_id,
                        "match_completed",
                        {
                            "match_id": game.match_id,
                            "winner_id": match_after.get("winner_id"),
                            "loser_id": match_after.get("loser_id"),
                        },
                    )

            notify_data_changed(Topic.SCORES.value, message="Rack completed")
            if rack_data.get("rating_updates"):
                notify_data_changed(Topic.RANKINGS.value, message="Live est_rating updated")
                notify_data_changed(Topic.LEADERBOARD.value, message="Live est_rating updated")
        except Exception as notify_err:
            logger.warning("Live refresh notify failed after rack submit: %s", notify_err)

        return GameResponse(**game_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting game result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matches/{match_id}/games", response_model=List[GameResponse])
async def get_match_games(match_id: str):
    """Get all games/racks for a match"""
    try:
        games = tm.get_match_games(match_id)

        # Enrich with player names
        enriched_games = []
        for game in games:
            game_dict = dict(game)
            winner_name = None
            breaking_player_name = None

            if game_dict.get('winner_id'):
                winner = tm.get_player(game_dict['winner_id'])
                winner_name = f"{winner['first_name']} {winner['last_name']}" if winner else None

            if game_dict.get('breaking_player_id'):
                breaker = tm.get_player(game_dict['breaking_player_id'])
                breaking_player_name = f"{breaker['first_name']} {breaker['last_name']}" if breaker else None

            game_dict['winner_name'] = winner_name
            game_dict['breaking_player_name'] = breaking_player_name
            enriched_games.append(GameResponse(**game_dict))

        return enriched_games
    except Exception as e:
        logger.error(f"Error getting match games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/games/{game_id}", response_model=GameResponse)
async def update_game_result(game_id: int, updates: GameUpdate, user: dict = Depends(require_director_or_admin)):
    """Update an existing game/rack result. Director/Admin only."""
    try:
        success = tm.update_game(game_id, updates.dict(exclude_unset=True))
        if not success:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # Synchronize match score from all games
        game_data = tm.get_game(game_id)
        if game_data:
            tm.synchronize_match_score_from_games(game_data['match_id'])

        # Get updated game data
        updated_game = tm.get_game(game_id)
        if not updated_game:
            raise HTTPException(status_code=500, detail="Game updated but not found")

        # Add player names for response
        updated_game = dict(updated_game)
        winner_name = None
        breaking_player_name = None

        if updated_game.get('winner_id'):
            winner = tm.get_player(updated_game['winner_id'])
            winner_name = f"{winner['first_name']} {winner['last_name']}" if winner else None

        if updated_game.get('breaking_player_id'):
            breaker = tm.get_player(updated_game['breaking_player_id'])
            breaking_player_name = f"{breaker['first_name']} {breaker['last_name']}" if breaker else None

        updated_game['winner_name'] = winner_name
        updated_game['breaking_player_name'] = breaking_player_name

        return GameResponse(**updated_game)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating game result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LIVE RATING ENDPOINTS
# ==========================================

@router.get("/live-ratings/{player_id}")
async def get_player_live_rating(
    player_id: str,
    user: dict = Depends(get_current_user),
):
    """Get current live est_rating for a player."""
    try:
        if not _has_pro_rating_access(user):
            raise HTTPException(status_code=403, detail="PRO subscription required for live ratings")
        from api.services.live_rating_engine import LiveRatingEngine
        rating_engine = LiveRatingEngine(tm)

        rating, confidence, robustness = rating_engine.get_player_current_rating(player_id)
        if rating is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found or no rating available")

        # Get recent transitions
        transitions = rating_engine.get_player_rating_history(player_id, limit=5)

        return {
            "player_id": player_id,
            "current_rating": rating,
            "confidence": confidence,
            "robustness": robustness,
            "recent_transitions": transitions
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting live rating for player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live-ratings")
async def get_current_live_ratings(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Get current live est_ratings for all active players."""
    try:
        if not _has_pro_rating_access(user):
            raise HTTPException(status_code=403, detail="PRO subscription required for live ratings")
        conn = engine.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                player_id,
                first_name || ' ' || last_name as player_name,
                est_rating,
                est_rating_confidence,
                est_rating_robustness,
                est_rating_last_updated
            FROM players
            WHERE membership_status = 'active'
              AND est_rating IS NOT NULL
            ORDER BY est_rating DESC NULLS LAST
            LIMIT %s
        """, (limit,))

        ratings = []
        for row in cursor.fetchall():
            ratings.append({
                "player_id": row[0],
                "player_name": row[1],
                "rating": float(row[2]) if row[2] else None,
                "confidence": float(row[3]) if row[3] else 0.5,
                "robustness": int(row[4]) if row[4] else 0,
                "last_updated": row[5].isoformat() if row[5] else None
            })

        conn.close()

        return {
            "ratings": ratings,
            "count": len(ratings),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting live ratings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rating-transitions/{player_id}")
async def get_player_rating_transitions(
    player_id: str,
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get rating transition history for a player."""
    try:
        if not _has_pro_rating_access(user):
            raise HTTPException(status_code=403, detail="PRO subscription required for live ratings")
        from api.services.live_rating_engine import LiveRatingEngine
        rating_engine = LiveRatingEngine(tm)

        transitions = rating_engine.get_player_rating_history(player_id, limit=limit)

        return {
            "player_id": player_id,
            "transitions": transitions,
            "count": len(transitions)
        }
    except Exception as e:
        logger.error(f"Error getting rating transitions for player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/notify-round/{round_number}")
async def notify_round(tournament_id: str, round_number: int):
    """Round notifications are not implemented (push/email wiring pending)."""
    raise HTTPException(
        status_code=501,
        detail="Round notifications are not implemented. Use tournament communications manually.",
    )
