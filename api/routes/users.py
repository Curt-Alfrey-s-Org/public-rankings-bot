"""
User management endpoints (admin only).
"""

# Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/AUTH_DESIGN.md;
#   docs/ROLES_AND_PERMISSIONS.md

import os
import json
import logging
import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, load_only
from sqlalchemy import text
from typing import List, Optional, Set
from datetime import datetime

from api.auth import get_current_user, get_current_user_allow_password_change, hash_password
from api.services.email import send_welcome_email_admin_created, send_password_changed_by_admin
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from api.models.user import User
from api.models.ai_coach import AICoachUsage
from api.config.admin_config import get_effective_tier_config
from api.routes.auth import validate_password_strength
from api.models.audit import AuditLog
from database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])
logger = logging.getLogger(__name__)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    email_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    country: Optional[str] = None
    state: Optional[str] = None
    home_pool_room: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdateRequest(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    home_pool_room: Optional[str] = None


class UserPreferencesRequest(BaseModel):
    key: str
    value: Optional[int] = None


class UserPreferencesResponse(BaseModel):
    key: str
    value: Optional[int] = None


class UpdateUserRequest(BaseModel):
    role: str
    username: Optional[str] = None  # Super_admin only; new username (3-20 chars)
    associations: Optional[List[str]] = None  # If set, replaces all user_associations rows for this user.


class SetPasswordRequest(BaseModel):
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str  # user, admin, director, super_admin (super_admin only); or user, admin, director, moderator (admin)
    tier: Optional[str] = None  # AI Coach tier: FREEBIE, ROOKIE, WEEKEND_WARRIOR, POOL_SHARK, PRO (no default; super admin must choose)
    associations: Optional[List[str]] = None  # user_associations.association values (e.g. WPA_Women, WPBA_Women). Required for directors.


class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]


class PlayerLink(BaseModel):
    user_id: int
    username: str
    player_name: str
    player_id: Optional[str] = None
    license_number: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlayerLinkListResponse(BaseModel):
    total: int
    links: List[PlayerLink]


class PlayerLinkUpsertRequest(BaseModel):
    username: str
    player_name: str
    player_id: Optional[str] = None
    license_number: Optional[str] = None


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin or super_admin (both have full access)."""
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_admin_or_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin or super_admin (super_admin can add all roles including other super_admins)."""
    role = current_user.get("role")
    if role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin or super admin access required")
    return current_user


def require_authenticated(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require any authenticated user."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


def require_authenticated_allow_password_change(
    current_user: dict = Depends(get_current_user_allow_password_change),
) -> dict:
    """Dependency for POST /change-password only: also accepts a restricted
    (must_change_password) token, which is rejected everywhere else."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


def _replace_user_associations(db: Session, user_id: int, associations: List[str]) -> None:
    """Replace all association rows for user_id. Values are trimmed; max length 32 (DB column). Deduped."""
    db.execute(text("DELETE FROM user_associations WHERE user_id = :uid"), {"uid": user_id})
    now = datetime.utcnow()
    seen: Set[str] = set()
    for raw in associations:
        a = (raw or "").strip()
        if not a:
            continue
        if len(a) > 32:
            raise HTTPException(
                status_code=400,
                detail=f"Association value too long (max 32 characters): {a[:24]}…",
            )
        if a in seen:
            continue
        seen.add(a)
        db.execute(
            text(
                "INSERT INTO user_associations (user_id, association, created_at) "
                "VALUES (:uid, :assoc, :ts)"
            ),
            {"uid": user_id, "assoc": a, "ts": now},
        )


def _count_user_associations(db: Session, user_id: int) -> int:
    row = db.execute(
        text("SELECT COUNT(*) FROM user_associations WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _allowed_roles_for_create(current_user: dict) -> tuple:
    """Roles the current user can assign when creating/updating. Super_admin: all; admin: user, admin, director, moderator."""
    if current_user.get("role") == "super_admin":
        return ("user", "admin", "director", "moderator", "super_admin")
    return ("user", "admin", "director", "moderator")


def _get_default_reset_password() -> str:
    """
    Temporary password for admin-initiated resets. User must change it on next login.
    DEFAULT_RESET_PASSWORD (if set and strong) is used; otherwise a random one-off password
    is generated per reset (no hardcoded default). The reset endpoint returns it to the admin.
    """
    pw = (os.getenv("DEFAULT_RESET_PASSWORD") or "").strip()
    if pw and validate_password_strength(pw):
        return pw
    # token_urlsafe gives ~96 bits; the suffix guarantees upper/lower/digit/special for the policy.
    return f"{secrets.token_urlsafe(12)}-Aa9!"


async def list_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
) -> UserListResponse:
    """List all users (admin or super_admin). Used by GET /api/users in main.py."""
    # load_only: avoid SELECT of columns missing on older DBs (see alembic 046).
    users = (
        db.query(User)
        .options(
            load_only(
                User.id,
                User.username,
                User.email,
                User.role,
                User.email_verified,
                User.created_at,
                User.last_login,
                User.country,
                User.state,
                User.home_pool_room,
            )
        )
        .order_by(User.username)
        .all()
    )
    return UserListResponse(
        total=len(users),
        users=[UserResponse.model_validate(u) for u in users],
    )


async def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
) -> UserResponse:
    """Create a new user (admin or super_admin). Used by POST /api/users in main.py."""
    if not validate_password_strength(body.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )
    allowed = _allowed_roles_for_create(current_user)
    if body.role not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {', '.join(allowed)}")
    valid_tiers = {"FREEBIE", "ROOKIE", "WEEKEND_WARRIOR", "POOL_SHARK", "PRO"}
    if body.tier is not None and body.tier.strip():
        tier = body.tier.strip().upper()
        if tier not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"Invalid tier. Allowed: {', '.join(sorted(valid_tiers))}")
    else:
        tier = None
    username = body.username.strip().lower()
    email = body.email.strip().lower()
    cleaned_associations: List[str] = []
    if body.associations:
        cleaned_associations = [str(a).strip() for a in body.associations if a and str(a).strip()]
    if body.role == "director" and not cleaned_associations:
        raise HTTPException(
            status_code=400,
            detail=(
                "Directors must have at least one association (e.g. WPA_Women, WPBA_Women, WPA_Men). "
                "Associations control which ranking systems they may import. Pass `associations` in the request body."
            ),
        )
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Email already in use")
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(body.password),
        role=body.role,
        email_verified=False,
        must_change_password=False,
    )
    db.add(user)
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_created",
        success=True,
        details=f"Created user {username} (role={body.role})",
    ))
    db.commit()
    db.refresh(user)
    if cleaned_associations:
        _replace_user_associations(db, user.id, cleaned_associations)
        db.commit()
        db.refresh(user)
    if tier:
        tier_config = get_effective_tier_config().get(tier, {})
        monthly = tier_config.get("monthly_limit")
        lifetime = tier_config.get("lifetime_limit")
        max_video = tier_config.get("max_video_duration") or 30
        usage = AICoachUsage(
            user_id=username,
            tier=tier,
            analyses_limit=monthly if monthly is not None else 999999,
            lifetime_limit=lifetime,
            max_video_duration_seconds=max_video,
        )
        db.add(usage)
        db.commit()
    if user.email:
        await send_welcome_email_admin_created(user.email, user.username)
    return UserResponse.model_validate(user)


@router.get("/player-links", response_model=PlayerLinkListResponse)
async def list_player_links(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
):
    """List user-to-player links (admin or super_admin)."""
    rows = db.execute(text("""
        SELECT upl.user_id, u.username, upl.player_name, upl.player_id, upl.license_number,
               upl.created_at, upl.updated_at
        FROM user_player_links upl
        JOIN users u ON u.id = upl.user_id
        ORDER BY u.username ASC
    """)).fetchall()
    links = [
        PlayerLink(
            user_id=r[0],
            username=r[1],
            player_name=r[2],
            player_id=r[3],
            license_number=r[4],
            created_at=str(r[5]) if r[5] else None,
            updated_at=str(r[6]) if r[6] else None,
        )
        for r in rows
    ]
    return PlayerLinkListResponse(total=len(links), links=links)


@router.post("/player-links", response_model=PlayerLink)
async def upsert_player_link(
    body: PlayerLinkUpsertRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
):
    """Create or update a user-to-player link (admin or super_admin)."""
    user = db.query(User).filter_by(username=body.username.strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    license_number = body.license_number
    if not license_number and body.player_id:
        row = db.execute(text("""
            SELECT license_number FROM players WHERE player_id = :pid
        """), {"pid": body.player_id}).fetchone()
        if row and row[0]:
            license_number = str(row[0]).strip()
        if not license_number:
            row = db.execute(text("""
                SELECT license_number FROM rankings
                WHERE LOWER(TRIM(player_name)) = LOWER(TRIM(:name)) AND license_number IS NOT NULL
                LIMIT 1
            """), {"name": body.player_name.strip()}).fetchone()
            if row and row[0]:
                license_number = str(row[0]).strip()

    db.execute(text("""
        INSERT INTO user_player_links (user_id, player_id, player_name, license_number, created_at, updated_at)
        VALUES (:user_id, :player_id, :player_name, :license_number, NOW(), NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            player_name = EXCLUDED.player_name,
            license_number = EXCLUDED.license_number,
            updated_at = NOW()
    """), {
        "user_id": user.id,
        "player_id": body.player_id,
        "player_name": body.player_name.strip(),
        "license_number": license_number,
    })
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_player_link_upsert",
        success=True,
        details=f"Linked {body.username} to player {body.player_name}",
    ))
    db.commit()
    try:
        notify_data_changed(Topic.PLAYERS.value, message="Player link updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (player-link upsert): %s", e)
    return PlayerLink(
        user_id=user.id,
        username=user.username,
        player_name=body.player_name.strip(),
        player_id=body.player_id,
        license_number=license_number,
    )


@router.delete("/player-links/{username}")
async def delete_player_link(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
):
    """Remove a user-to-player link (admin or super_admin)."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.execute(text("DELETE FROM user_player_links WHERE user_id = :user_id"), {"user_id": user.id})
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_player_link_delete",
        success=True,
        details=f"Removed player link for {username}",
    ))
    db.commit()
    try:
        notify_data_changed(Topic.PLAYERS.value, message="Player link removed")
    except Exception as e:
        logger.warning("notify_data_changed failed (player-link delete): %s", e)
    return {"message": "Player link removed"}


@router.get("/fargo-accounts-csv")
async def download_fargo_accounts_csv(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
):
    """
    Download CSV of all Fargo player accounts with credentials and associations.
    Admin/super_admin only.
    
    CSV columns: username, password, name, email, associations
    """
    import csv
    import io
    
    # Query users with requires_email_setup or those created via Fargo bulk process
    # (identified by placeholder email pattern or requires_email_setup flag)
    rows = db.execute(text("""
        SELECT 
            u.id,
            u.username,
            u.email,
            COALESCE(u.nickname, u.username) as display_name,
            COALESCE(tp.temp_password, '') as temp_password,
            STRING_AGG(DISTINCT ua.association, ', ' ORDER BY ua.association) as associations
        FROM users u
        LEFT JOIN user_temp_passwords tp ON tp.user_id = u.id
        LEFT JOIN user_associations ua ON ua.user_id = u.id
        WHERE u.requires_email_setup = TRUE 
           OR u.email LIKE 'pending_%@fargo.local'
        GROUP BY u.id, u.username, u.email, u.nickname, tp.temp_password
        ORDER BY u.username
    """)).fetchall()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['username', 'password', 'name', 'email', 'associations'])
    
    # Write data
    for row in rows:
        user_id, username, email, display_name, temp_password, associations = row
        # Use actual email if set, otherwise empty
        actual_email = email if email and not email.startswith('pending_') else ''
        writer.writerow([
            username,
            temp_password or '',
            display_name or username,
            actual_email,
            associations or ''
        ])
    
    csv_content = output.getvalue()
    
    # Log the export
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="fargo_accounts_csv_export",
        success=True,
        details=f"Exported {len(rows)} Fargo accounts to CSV",
    ))
    db.commit()
    
    # Return CSV as response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="fargo_accounts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        }
    )


class UserAssociationsResponse(BaseModel):
    associations: List[str]


@router.get("/{username}/associations", response_model=UserAssociationsResponse)
async def get_user_associations_route(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin),
):
    """List ranking association tags for Data input scoping (admin or super_admin)."""
    uname = username.strip().lower()
    user = db.query(User).filter_by(username=uname).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = db.execute(
        text("SELECT association FROM user_associations WHERE user_id = :id ORDER BY association ASC"),
        {"id": user.id},
    ).fetchall()
    return UserAssociationsResponse(associations=[str(r[0]) for r in rows if r and r[0]])


@router.get("/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin)
):
    """Get user details (admin or super_admin)."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("/{username}/set-password")
async def set_user_password(
    username: str,
    body: SetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin)
):
    """Admin or super_admin: set another user's password. User must change it on next login (industry standard)."""
    if not validate_password_strength(body.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    if getattr(user, "must_change_password", None) is not None:
        user.must_change_password = True  # Admin-set password: force change on next login (OWASP/NIST)
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_password_set_by_admin",
        success=True,
        details=f"Password set for user {username} by {current_user.get('sub')}",
    ))
    db.commit()
    if user.email:
        await send_password_changed_by_admin(user.email, username, body.new_password)
    try:
        # Do NOT include username/PII in the SSE payload — /api/live/updates is a
        # public broadcast channel. Use a generic event so connected admins refetch
        # their user-list query without leaking which account changed.
        notify_data_changed(Topic.SETTINGS.value, message="User credentials updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (set-password): %s", e)
    return {"message": f"Password updated for {username}. They must change it on next login."}


@router.post("/{username}/reset-password")
async def reset_user_password(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin)
):
    """
    Admin or super_admin: reset user's password to the default temporary password.
    User must change it on next login (industry standard per OWASP/NIST).
    """
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp_password = _get_default_reset_password()
    user.password_hash = hash_password(temp_password)
    if getattr(user, "must_change_password", None) is not None:
        user.must_change_password = True
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_password_reset_by_admin",
        success=True,
        details=f"Password reset for user {username} by {current_user.get('sub')}",
    ))
    db.commit()
    if user.email:
        await send_password_changed_by_admin(user.email, username, temp_password)
    try:
        # No PII on the public SSE channel.
        notify_data_changed(Topic.SETTINGS.value, message="User credentials updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (reset-password): %s", e)
    return {
        "message": "Password reset. User must change it on next login.",
        "temporary_password": temp_password,
    }


@router.put("/{username}")
async def update_user(
    username: str,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin)
):
    """Update user role (admin or super_admin). Super_admin can also change username."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = _allowed_roles_for_create(current_user)
    if body.role not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {', '.join(allowed)}")

    new_username = (body.username or "").strip() if body.username else None
    if new_username:
        if current_user.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Only super_admin can change usernames")
        if len(new_username) < 3 or len(new_username) > 20:
            raise HTTPException(status_code=400, detail="Username must be 3-20 characters")
        if new_username != username and db.query(User).filter_by(username=new_username).first():
            raise HTTPException(status_code=409, detail="Username already taken")
        old_username = username
        user.username = new_username
        # Update tournaments.created_by_username for audit trail
        try:
            db.execute(
                text("UPDATE tournaments SET created_by_username = :new WHERE created_by_username = :old"),
                {"new": new_username, "old": old_username}
            )
        except Exception as e:
            logger.warning(
                "Could not backfill tournaments.created_by_username during rename %s -> %s: %s",
                old_username,
                new_username,
                e,
            )  # Column may not exist in older schemas
        db.add(AuditLog(
            user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
            event_type="user_username_updated",
            success=True,
            details=f"User {old_username} renamed to {new_username}"
        ))

    user.role = body.role
    if body.associations is not None:
        _replace_user_associations(db, user.id, [str(a) for a in body.associations])
    if user.role == "director" and _count_user_associations(db, user.id) == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Directors must have at least one association. "
                "Set `associations` in this request (e.g. [\"WPA_Women\"]) or add rows before promoting to director."
            ),
        )
    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_role_updated",
        success=True,
        details=f"User {user.username} role changed to {body.role}"
    ))
    db.commit()
    try:
        # No PII on the public SSE channel.
        notify_data_changed(Topic.SETTINGS.value, message="User updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (update-user): %s", e)

    return {"message": f"User {user.username} updated"}


@router.post("/change-password")
async def change_own_password(
    body: SetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated_allow_password_change)
):
    """Change current user's password (any authenticated user, including a user whose
    must_change_password flag is set; this is the only non-auth endpoint such a token can use)."""
    if not validate_password_strength(body.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special character",
        )
    username = current_user.get("sub", current_user.get("role"))
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False  # Clear the flag after changing password
    # Pro (Fargo) first-login flow sets force_password_reset after email verification;
    # clear it here so the password-change gate does not loop after a successful change.
    user.force_password_reset = False
    db.add(AuditLog(
        user_id=user.id,
        event_type="user_password_changed",
        success=True,
        details=f"User {username} changed their own password",
    ))
    db.commit()
    try:
        # No PII on the public SSE channel.
        notify_data_changed(Topic.SETTINGS.value, message="User credentials updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (change-password): %s", e)
    return {"message": "Password changed successfully"}


@router.delete("/{username}")
async def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin_or_super_admin)
):
    """Delete user (admin or super_admin)."""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    uid = user.id
    # Drop FK references so DELETE FROM users succeeds (audit_log, tokens, etc.)
    db.execute(text("UPDATE audit_log SET user_id = NULL WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("UPDATE login_attempts SET user_id = NULL WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM email_verification_tokens WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM password_reset_tokens WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM backup_codes WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM user_player_links WHERE user_id = :uid"), {"uid": uid})

    db.add(AuditLog(
        user_id=current_user.get("sub") if isinstance(current_user.get("sub"), int) else None,
        event_type="user_deleted",
        success=True,
        details=f"User {username} deleted",
    ))
    db.delete(user)
    db.commit()
    try:
        # No PII on the public SSE channel.
        notify_data_changed(Topic.SETTINGS.value, message="User deleted")
    except Exception as e:
        logger.warning("notify_data_changed failed (delete-user): %s", e)

    return {"message": f"User {username} deleted"}


@router.get("/profile/me", response_model=UserResponse)
async def get_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated)
):
    """Get current user profile (any authenticated user)."""
    username = current_user.get("sub", current_user.get("role"))
    user = db.query(User).filter_by(username=username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    return UserResponse.model_validate(user)


@router.get("/profile/me/associations", response_model=UserAssociationsResponse)
async def get_my_associations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated),
):
    """
    Associations the current user may use (director: assigned tags;
    admin/super_admin: union of known tags and tags present in the database).
    """
    role = str(current_user.get("role") or "").strip().lower()
    username = str(current_user.get("sub") or "").strip().lower()
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if role in ("super_admin", "admin"):
        rows = db.execute(
            text("SELECT DISTINCT association FROM user_associations ORDER BY association ASC")
        ).fetchall()
        from_db = [str(r[0]) for r in rows if r and r[0]]
        defaults = [
            "WPA_Women",
            "WPA_Men",
            "WPBA_Women",
            "WPBA",
            "WPA_Heyball_Men",
            "WPA_Heyball_Women",
            "WPA_Artistic",
            "LOCAL",
        ]
        merged = sorted(set(from_db) | set(defaults))
        return UserAssociationsResponse(associations=merged)

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    rows = db.execute(
        text(
            "SELECT association FROM user_associations WHERE user_id = :id ORDER BY association ASC"
        ),
        {"id": user.id},
    ).fetchall()
    return UserAssociationsResponse(associations=[str(r[0]) for r in rows if r and r[0]])


@router.patch("/profile/me", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_authenticated)
):
    """Update current user profile (country, state, home pool room)."""
    username = current_user.get("sub", current_user.get("role"))
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    if body.country is not None:
        user.country = body.country.strip() or None
    if body.state is not None:
        user.state = body.state.strip() or None
    if body.home_pool_room is not None:
        user.home_pool_room = body.home_pool_room.strip() or None
    db.commit()
    try:
        # M-4: notify before db.refresh so a transient refresh failure doesn't drop
        # the SSE event for clients that already saw the commit. No PII in payload.
        notify_data_changed(Topic.SETTINGS.value, message="Profile updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (update-profile): %s", e)
    db.refresh(user)
    return UserResponse.model_validate(user)


def _load_preferences(user: User) -> dict:
    """Parse users.preferences_json (a JSON object); anything else counts as empty."""
    raw = getattr(user, "preferences_json", None)
    if not raw:
        return {}
    try:
        prefs = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return prefs if isinstance(prefs, dict) else {}


@router.get("/preferences/ranking_history_days", response_model=UserPreferencesResponse)
def get_ranking_history_preference(
    current_user: dict = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    """
    Get current user's preferred number of days for ranking history display.
    Admin/super-admin only. Defaults to None (all history).
    """
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="User not authenticated")

    try:
        user = db.query(User).filter(User.username == username).first()
        days = _load_preferences(user).get("ranking_history_days") if user else None
        if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
            days = None
        return {"key": "ranking_history_days", "value": days}
    except Exception:
        logger.warning("Could not read ranking_history_days preference", exc_info=True)
        return {"key": "ranking_history_days", "value": None}


@router.post("/preferences/ranking_history_days", response_model=UserPreferencesResponse)
def set_ranking_history_preference(
    body: UserPreferencesRequest,
    current_user: dict = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    """
    Set current user's preferred number of days for ranking history display.
    Admin/super-admin only. Pass value=null for all history.
    
    Args:
        value: Number of days (30, 60, 90) or None for all history
    """
    username = current_user.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Validate days value if provided
    if body.value is not None:
        if not isinstance(body.value, int) or isinstance(body.value, bool) or body.value <= 0:
            raise HTTPException(status_code=400, detail="days must be a positive integer or null")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        prefs = _load_preferences(user)
        prefs["ranking_history_days"] = body.value
        user.preferences_json = json.dumps(prefs)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Error saving ranking_history_days preference")
        raise HTTPException(status_code=500, detail="Error saving preference")
    return {"key": "ranking_history_days", "value": body.value}

