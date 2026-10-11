"""
League Management API Routes.
CRUD for leagues, teams, members, and matches.
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from database import get_database_manager
from api.auth import require_director_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/leagues", tags=["leagues"])


class LeagueCreate(BaseModel):
    name: str
    org_code: Optional[str] = None
    season_start: Optional[str] = None
    season_end: Optional[str] = None


class LeagueResponse(BaseModel):
    league_id: str
    name: str
    org_code: Optional[str]
    season_start: Optional[str]
    season_end: Optional[str]


class TeamCreate(BaseModel):
    team_name: str
    captain_player_id: Optional[str] = None


class TeamMemberCreate(BaseModel):
    player_id: str
    role: Optional[str] = "member"


@router.get("/{league_id}/teams", response_model=List[dict])
async def list_teams(league_id: str):
    """List teams in a league."""
    db = get_database_manager()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, team_name, captain_player_id FROM league_teams
            WHERE league_id = %s ORDER BY team_name
        """, (league_id,))
        rows = cur.fetchall()
        return [{"id": r[0], "team_name": r[1], "captain_player_id": r[2]} for r in rows]
    finally:
        conn.close()


@router.post("/{league_id}/teams", status_code=201)
async def create_team(league_id: str, team: TeamCreate, _=Depends(require_director_or_admin)):
    """Create a team in a league. Director/admin only."""
    db = get_database_manager()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO league_teams (league_id, team_name, captain_player_id)
            VALUES (%s, %s, %s)
        """, (league_id, team.team_name, team.captain_player_id))
        conn.commit()
        return {"message": "Team created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
