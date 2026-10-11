"""
Tournament Wizard API Routes
Provides interactive wizard-based tournament setup and test tournament management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Dict, Any
import logging
import json
from datetime import datetime

from database import get_engine
engine = get_engine()
from api.auth import get_current_user, require_director_or_admin
from api.models.tournament_models import TournamentResponse, TournamentCreate
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tournament-wizard", tags=["Tournament Wizard"])


# ==========================================
# WIZARD SESSION MODELS
# ==========================================

from pydantic import BaseModel, Field


class WizardStartRequest(BaseModel):
    """Request to start a new wizard session"""
    setup_mode: str = Field(..., pattern="^(manual|wizard)$")
    # Deprecated: test tournaments use /api/test-tournaments (Test Center). Ignored if sent.
    is_test_tournament: bool = False


class WizardStartResponse(BaseModel):
    """Response when starting wizard"""
    tournament_id: str
    setup_mode: str
    is_test_tournament: bool
    current_step: int
    total_steps: int


class WizardStepData(BaseModel):
    """Data for a specific wizard step"""
    step_number: int = Field(..., ge=1, le=6)
    data: Dict[str, Any]
    is_complete: bool = False


class WizardStepResponse(BaseModel):
    """Response after saving a wizard step"""
    tournament_id: str
    step_number: int
    is_complete: bool
    next_step: Optional[int]
    wizard_progress: Dict[str, Any]


class WizardProgressResponse(BaseModel):
    """Current wizard progress"""
    tournament_id: str
    setup_mode: str
    is_test_tournament: bool
    wizard_progress: Dict[str, Any]
    current_step: int
    completed_steps: List[int]
    can_finalize: bool


# ==========================================
# WIZARD ENDPOINTS
# ==========================================

@router.post("/start", response_model=WizardStartResponse, status_code=status.HTTP_201_CREATED)
async def start_wizard(
    request: WizardStartRequest,
    user: dict = Depends(require_director_or_admin)
) -> WizardStartResponse:
    """
    Initialize a new tournament wizard session.
    Creates a tournament record in 'setup' status with wizard tracking.
    """
    if request.is_test_tournament:
        logger.warning(
            "Wizard is_test_tournament is deprecated; use Test Center (/api/test-tournaments). "
            "Creating a normal (non-test-flag) wizard row."
        )

    try:
        with engine.connect() as conn:
            # Generate tournament ID
            import uuid
            tournament_id = f"T{uuid.uuid4().hex[:8].upper()}"
            
            # Initial wizard progress
            wizard_progress = {
                "step_1_basics": {"complete": False, "data": {}},
                "step_2_participants": {"complete": False, "data": {}},
                "step_3_divisions": {"complete": False, "data": {}},
                "step_4_schedule": {"complete": False, "data": {}},
                "step_5_rules": {"complete": False, "data": {}},
                "step_6_review": {"complete": False, "data": {}},
            }
            
            # Create tournament record
            sql = text("""
                INSERT INTO tournaments (
                    tournament_id, tournament_name, tournament_date,
                    status, setup_mode, is_test_tournament,
                    wizard_progress, created_by, created_by_username,
                    elimination_type, points_structure
                )
                VALUES (
                    :tournament_id, :tournament_name, :tournament_date,
                    :status, :setup_mode, :is_test_tournament,
                    :wizard_progress, :created_by, :created_by_username,
                    :elimination_type, :points_structure
                )
                RETURNING id
            """)
            
            result = conn.execute(sql, {
                "tournament_id": tournament_id,
                "tournament_name": "[Wizard In Progress]" if request.setup_mode == "wizard" else "New Tournament",
                "tournament_date": datetime.now().date(),
                "status": "setup",
                "setup_mode": request.setup_mode,
                "is_test_tournament": False,
                "wizard_progress": json.dumps(wizard_progress),
                "created_by": user.get("sub", "unknown"),
                "created_by_username": user.get("sub", "unknown"),
                "elimination_type": "single",  # default, will be updated in wizard
                "points_structure": "{}",  # default, will be updated in wizard
            })
            
            conn.commit()
            
            logger.info(
                f"Wizard started: {tournament_id} by {user.get('sub')} "
                f"(mode: {request.setup_mode})"
            )
            
            return WizardStartResponse(
                tournament_id=tournament_id,
                setup_mode=request.setup_mode,
                is_test_tournament=False,
                current_step=1,
                total_steps=6
            )
            
    except Exception as e:
        logger.error(f"Error starting wizard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start wizard: {str(e)}")


@router.post("/{tournament_id}/step", response_model=WizardStepResponse)
async def save_wizard_step(
    tournament_id: str,
    step_data: WizardStepData,
    user: dict = Depends(require_director_or_admin)
) -> WizardStepResponse:
    """
    Save progress for a specific wizard step.
    Updates wizard_progress JSON and tournament fields based on step data.
    """
    try:
        with engine.connect() as conn:
            # Get current tournament and validate access
            sql = text("""
                SELECT wizard_progress, is_test_tournament, created_by_username, setup_mode
                FROM tournaments
                WHERE tournament_id = :tournament_id
            """)
            result = conn.execute(sql, {"tournament_id": tournament_id})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            wizard_progress = json.loads(row[0]) if row[0] else {}
            setup_mode = row[3]
            
            # Validate setup mode is wizard
            if setup_mode != "wizard":
                raise HTTPException(
                    status_code=400,
                    detail="Tournament was not created in wizard mode"
                )
            
            # Update wizard progress
            step_key = f"step_{step_data.step_number}_"
            step_names = ["", "basics", "participants", "divisions", "schedule", "rules", "review"]
            if 1 <= step_data.step_number <= 6:
                step_key += step_names[step_data.step_number]
            
            wizard_progress[step_key] = {
                "complete": step_data.is_complete,
                "data": step_data.data,
                "updated_at": datetime.now().isoformat()
            }
            
            # Update tournament fields based on step data
            update_fields = {"wizard_progress": json.dumps(wizard_progress)}
            
            # Step 1: Basics (name, date, location, elimination type, ranking_system, game_type)
            if step_data.step_number == 1:
                if "tournament_name" in step_data.data:
                    update_fields["tournament_name"] = step_data.data["tournament_name"]
                if "tournament_date" in step_data.data:
                    update_fields["tournament_date"] = step_data.data["tournament_date"]
                if "location" in step_data.data:
                    update_fields["location"] = step_data.data["location"]
                if "elimination_type" in step_data.data:
                    update_fields["elimination_type"] = step_data.data["elimination_type"]
                if "max_players" in step_data.data:
                    update_fields["max_players"] = step_data.data["max_players"]
                if "ranking_system" in step_data.data:
                    update_fields["ranking_system"] = step_data.data["ranking_system"]
                if "game_type" in step_data.data:
                    update_fields["game_type"] = step_data.data["game_type"]
            
            # Step 4: Schedule (time limits, shot clock)
            elif step_data.step_number == 4:
                if "match_time_limit_minutes" in step_data.data:
                    update_fields["match_time_limit_minutes"] = step_data.data["match_time_limit_minutes"]
                if "shot_clock_seconds" in step_data.data:
                    update_fields["shot_clock_seconds"] = step_data.data["shot_clock_seconds"]
            
            # Step 5: Rules (points structure)
            elif step_data.step_number == 5:
                if "points_structure" in step_data.data:
                    update_fields["points_structure"] = json.dumps(step_data.data["points_structure"])
            
            # Build UPDATE query
            set_clause = ", ".join([f"{k} = :{k}" for k in update_fields.keys()])
            update_sql = text(f"""
                UPDATE tournaments
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE tournament_id = :tournament_id
            """)
            
            conn.execute(update_sql, {**update_fields, "tournament_id": tournament_id})
            conn.commit()
            
            # Determine next step
            next_step = step_data.step_number + 1 if step_data.step_number < 6 else None
            
            logger.info(
                f"Wizard step {step_data.step_number} saved for {tournament_id} "
                f"by {user.get('sub')}"
            )
            
            return WizardStepResponse(
                tournament_id=tournament_id,
                step_number=step_data.step_number,
                is_complete=step_data.is_complete,
                next_step=next_step,
                wizard_progress=wizard_progress
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving wizard step: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save wizard step: {str(e)}")


@router.get("/{tournament_id}/progress", response_model=WizardProgressResponse)
async def get_wizard_progress(
    tournament_id: str,
    user: dict = Depends(require_director_or_admin)
) -> WizardProgressResponse:
    """Get current wizard progress for a tournament."""
    try:
        with engine.connect() as conn:
            sql = text("""
                SELECT setup_mode, is_test_tournament, wizard_progress
                FROM tournaments
                WHERE tournament_id = :tournament_id
            """)
            result = conn.execute(sql, {"tournament_id": tournament_id})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            setup_mode, is_test, wizard_progress_json = row
            wizard_progress = json.loads(wizard_progress_json) if wizard_progress_json else {}
            
            # Calculate completed steps
            completed_steps = []
            current_step = 1
            for i in range(1, 7):
                step_key = f"step_{i}_"
                step_names = ["", "basics", "participants", "divisions", "schedule", "rules", "review"]
                step_key += step_names[i]
                
                if step_key in wizard_progress and wizard_progress[step_key].get("complete"):
                    completed_steps.append(i)
                    current_step = i + 1
            
            can_finalize = len(completed_steps) >= 5  # All steps except review must be complete
            
            return WizardProgressResponse(
                tournament_id=tournament_id,
                setup_mode=setup_mode,
                is_test_tournament=is_test,
                wizard_progress=wizard_progress,
                current_step=min(current_step, 6),
                completed_steps=completed_steps,
                can_finalize=can_finalize
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting wizard progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/finalize")
async def finalize_wizard(
    tournament_id: str,
    user: dict = Depends(require_director_or_admin)
) -> Dict[str, Any]:
    """
    Finalize wizard setup and move tournament to 'registration' status.
    Validates that all required steps are complete.
    """
    try:
        with engine.connect() as conn:
            # Get wizard progress
            sql = text("""
                SELECT wizard_progress, is_test_tournament, setup_mode
                FROM tournaments
                WHERE tournament_id = :tournament_id
            """)
            result = conn.execute(sql, {"tournament_id": tournament_id})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            wizard_progress = json.loads(row[0]) if row[0] else {}
            setup_mode = row[2]
            
            # Validate setup mode
            if setup_mode != "wizard":
                raise HTTPException(status_code=400, detail="Tournament was not created in wizard mode")
            
            # Check that required steps are complete (steps 1-5)
            required_steps = ["step_1_basics", "step_2_participants", "step_3_divisions", 
                            "step_4_schedule", "step_5_rules"]
            incomplete_steps = []
            
            for step_key in required_steps:
                if step_key not in wizard_progress or not wizard_progress[step_key].get("complete"):
                    incomplete_steps.append(step_key)
            
            if incomplete_steps:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot finalize: incomplete steps: {', '.join(incomplete_steps)}"
                )
            
            # Update tournament status to registration
            update_sql = text("""
                UPDATE tournaments
                SET status = 'registration', updated_at = CURRENT_TIMESTAMP
                WHERE tournament_id = :tournament_id
            """)
            
            conn.execute(update_sql, {"tournament_id": tournament_id})
            conn.commit()
            
            logger.info(f"Wizard finalized for {tournament_id} by {user.get('sub')}")
            
            return {
                "success": True,
                "tournament_id": tournament_id,
                "status": "registration",
                "message": "Tournament wizard completed successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finalizing wizard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize wizard: {str(e)}")


