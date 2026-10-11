"""
Notification preferences and rank change alerts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, get_database_manager
from api.auth import get_current_user_object as get_current_user
from api.models.ai_coach import AICoachUsage

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _user_id(user) -> str:
    return getattr(user, "id", None) or getattr(user, "username", None) or str(getattr(user, "sub", ""))


class NotificationPreferencesResponse(BaseModel):
    notify_rank_changes: bool


class NotificationPreferencesUpdate(BaseModel):
    notify_rank_changes: bool


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's notification settings. Returns defaults if ai_coach_usage table is missing (e.g. migrations not run)."""
    uid = _user_id(user)
    try:
        usage = db.query(AICoachUsage).filter_by(user_id=uid).first()
    except Exception:
        return NotificationPreferencesResponse(notify_rank_changes=True)
    notify = True
    if usage is not None:
        notify = getattr(usage, "notify_rank_changes", True)
        if notify is None:
            notify = True
    return NotificationPreferencesResponse(notify_rank_changes=notify)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    body: NotificationPreferencesUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user's notification settings. No-op if ai_coach_usage table is missing."""
    uid = _user_id(user)
    try:
        usage = db.query(AICoachUsage).filter_by(user_id=uid).first()
    except Exception:
        return NotificationPreferencesResponse(notify_rank_changes=body.notify_rank_changes)
    if usage is None:
        usage = AICoachUsage(
            user_id=uid,
            tier="FREEBIE",
            analyses_limit=0,
            lifetime_limit=3,
            notify_rank_changes=body.notify_rank_changes,
        )
        db.add(usage)
    else:
        usage.notify_rank_changes = body.notify_rank_changes
    try:
        db.commit()
    except Exception:
        db.rollback()
        return NotificationPreferencesResponse(notify_rank_changes=body.notify_rank_changes)
    return NotificationPreferencesResponse(notify_rank_changes=body.notify_rank_changes)


@router.post("/test-rank-change")
async def test_rank_change(
    user=Depends(get_current_user),
):
    """Test endpoint for rank change notification flow. Uses shared DB (get_database_manager)."""
    from api.services.rank_change_notifier import detect_rank_changes, send_rank_change_alerts

    db_manager = get_database_manager()
    changes = detect_rank_changes(db_manager, "WPBA_Women")
    sent = send_rank_change_alerts(db_manager, changes[:3], dry_run=True)
    return {"status": "ok", "changes_detected": len(changes), "alerts_would_send": sent}
