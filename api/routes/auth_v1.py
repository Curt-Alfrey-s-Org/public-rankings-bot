"""
Auth v1 API — stable contract for mobile app (docs/PRODUCTION_AND_APP_CONVERSION.md).
Exposes POST /login and POST /logout with response shape { success, token?, user?, role?, message? }.
Uses same DB auth as /api/auth; no separate credential store.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import logging

from api.auth import (
    create_access_token,
    authenticate_user,
)
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth-v1"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    user: str | None = None
    role: str | None = None
    message: str | None = None
    # When true the token only works for POST /api/users/change-password (and /api/auth/me)
    # until the password has been changed.
    must_change_password: bool = False


class LogoutRequest(BaseModel):
    token: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login_v1(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Mobile app login. Returns { success, token, user, role } on success,
    { success: false, message } on failure. Uses same DB users as /api/auth.
    """
    try:
        # Bootstrap users are created at startup only (api/main.py); never at login.
        result = authenticate_user(db, body.username, body.password)
        if result is None:
            return LoginResponse(success=False, message="Invalid username or password")

        user, must_change = result
        token = create_access_token(
            user.role, subject=user.username, password_change_required=must_change
        )
        return LoginResponse(
            success=True,
            token=token,
            user=user.username,
            role=user.role,
            must_change_password=must_change,
        )
    except OperationalError as e:
        logger.warning("Login v1 failed: database unreachable: %s", e)
        return LoginResponse(
            success=False,
            message="Service unavailable. Please try again later.",
        )
    except Exception as e:
        logger.exception("Login v1 error: %s", e)
        return LoginResponse(success=False, message="Login failed")


@router.post("/logout")
async def logout_v1(req: LogoutRequest | None = None):
    """Mobile app logout. Token is stateless (JWT); client discards it. Returns success."""
    return {"success": True}
