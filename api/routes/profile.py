"""
Profile endpoints: Allow users to customize their profile (nickname, email).
- PUT /profile/nickname: Update display name
- PUT /profile/email: Update email address
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import logging

from api.auth import get_current_user
from api.models.user import User
from api.models.audit import AuditLog
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from database import get_db

router = APIRouter(tags=["profile"])
logger = logging.getLogger(__name__)


class NicknameUpdateRequest(BaseModel):
    nickname: str = None


class EmailUpdateRequest(BaseModel):
    email: EmailStr


class ProfileResponse(BaseModel):
    username: str
    nickname: str = None
    email: str = None
    role: str


@router.put("/profile/nickname")
async def update_nickname(
    body: NicknameUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user's display nickname.
    Nickname is shown to other users in rankings.
    If not set, username is used as display name.
    """
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="No authenticated user")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate nickname
    if body.nickname:
        nickname = body.nickname.strip()
        if len(nickname) == 0:
            raise HTTPException(status_code=400, detail="Nickname cannot be empty")
        if len(nickname) > 100:
            raise HTTPException(status_code=400, detail="Nickname too long (max 100 characters)")
        user.nickname = nickname
    else:
        user.nickname = None

    try:
        db.add(AuditLog(
            user_id=user.id,
            event_type="profile_nickname_updated",
            success=True,
        ))
        db.commit()
        try:
            notify_data_changed(Topic.SETTINGS.value, message="Nickname updated")
        except Exception as e:
            logger.warning("notify_data_changed failed (nickname): %s", e)
        return {
            "message": "Nickname updated successfully",
            "nickname": user.nickname,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update nickname: {str(e)}")


@router.put("/profile/email")
async def update_email(
    body: EmailUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user's email address.
    Email is required for password reset functionality.
    """
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="No authenticated user")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    email = body.email.strip().lower()
    
    # Check if email is already in use by another user
    existing = db.query(User).filter(
        User.email == email,
        User.id != user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use by another user")

    user.email = email
    # Setting email verified to True for self-update (admin-assigned users will have it set during bulk create)
    user.email_verified = True

    try:
        db.add(AuditLog(
            user_id=user.id,
            event_type="profile_email_updated",
            success=True,
        ))
        db.commit()
        try:
            notify_data_changed(Topic.SETTINGS.value, message="Email updated")
        except Exception as e:
            logger.warning("notify_data_changed failed (email): %s", e)
        return {
            "message": "Email updated successfully",
            "email": user.email,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update email: {str(e)}")


@router.get("/me", response_model=ProfileResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's profile information."""
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="No authenticated user")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse(
        username=user.username,
        nickname=user.nickname,
        email=user.email,
        role=user.role,
    )
