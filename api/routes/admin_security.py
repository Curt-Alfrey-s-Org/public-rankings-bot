"""
Admin endpoints for bulk user management, login monitoring, and security.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import csv
import io

from database import get_db
from api.models.user import User
from api.models.audit import AuditLog
from api.models.ip_block import IPBlock
from sqlalchemy import func, or_, select
from api.auth import get_current_user, get_current_user_object
from api.services.bulk_user_service import (
    create_bulk_users_from_fargo,
    export_users_csv,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Auth flow writes to audit_log (api.routes.auth._record_login), not login_attempts.
_LOGIN_AUDIT_EVENT_TYPES = frozenset(
    {
        "login_success",
        "login_failed",
        "login_locked",
        "login_blocked_email_not_verified",
        "honeypot_blocked_ip",
        "honeypot_trapped",
    }
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class FargoPlayerInput(BaseModel):
    """Fargo player data for bulk import."""
    name: str
    fargo_rating: Optional[int] = None
    fargo_id: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    pool_room: Optional[str] = None
    country: Optional[str] = "USA"


class BulkUserCreateRequest(BaseModel):
    """Request to create users from Fargo data."""
    players: List[FargoPlayerInput]


class BulkUserCreateResponse(BaseModel):
    """Response with created users."""
    created_count: int
    error_count: int
    users: List[dict]
    errors: List[str]
    csv_data: str


class LoginAttemptResponse(BaseModel):
    """Single login attempt record."""
    id: int
    username: str
    ip_address: str
    success: bool
    failure_reason: Optional[str] = None
    timestamp: str


def _display_username_for_audit(audit: AuditLog, joined_username: str | None) -> str:
    if joined_username:
        return joined_username
    if audit.event_type in ("honeypot_blocked_ip", "honeypot_trapped"):
        return "admin"
    return "(unknown)"


def _audit_to_attempt_response(audit: AuditLog, joined_username: str | None) -> LoginAttemptResponse:
    is_success = audit.event_type == "login_success" and audit.success is True
    failure_reason = None if is_success else (audit.details or audit.event_type)
    return LoginAttemptResponse(
        id=audit.id,
        username=_display_username_for_audit(audit, joined_username),
        ip_address=audit.ip_address or "",
        success=is_success,
        failure_reason=failure_reason,
        timestamp=audit.timestamp.isoformat(),
    )


class LoginAttemptsResponse(BaseModel):
    """List of login attempts."""
    total: int
    attempts: List[LoginAttemptResponse]


class UserSecurityStatusResponse(BaseModel):
    """Security status of a user."""
    username: str
    failed_attempts: int
    is_locked: bool
    locked_until: Optional[str] = None
    recent_ips: List[str]
    recent_attempts: List[LoginAttemptResponse]


class SecurityMetricsResponse(BaseModel):
    """Aggregated security metrics for the Global Metrics dashboard."""
    failed_attempts_24h: int
    successful_attempts_24h: int
    unique_ips_24h: int
    locked_accounts_count: int


class IPBlockResponse(BaseModel):
    """Single blocked IP record."""
    id: int
    ip_address: str
    reason: str
    attempt_count: int
    blocked_at: str
    expires_at: Optional[str] = None
    is_active: bool
    first_attempt: Optional[str] = None


class IPBlocksListResponse(BaseModel):
    """List of all blocked IPs."""
    total: int
    active: int
    blocks: List[IPBlockResponse]


class IPUnblockResponse(BaseModel):
    """Response from unblocking an IP."""
    success: bool
    message: str
    ip_address: str


# ============================================================================
# ENDPOINT 1: POST /api/admin/users/bulk-create
# Bulk create users from Fargo player data
# ============================================================================

@router.post("/users/bulk-create", response_model=BulkUserCreateResponse)
async def bulk_create_users(
    request: BulkUserCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create multiple users from Fargo player data.
    Only accessible to super_admin.
    
    Returns newly created usernames, passwords, and CSV export.
    """
    # Check authorization
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can bulk-create users")
    
    # Convert input to dicts
    players = [p.dict() for p in request.players]
    
    # Create users
    created_users, errors = create_bulk_users_from_fargo(players, db)
    
    # Generate CSV
    csv_data = export_users_csv(created_users)
    
    return BulkUserCreateResponse(
        created_count=len(created_users),
        error_count=len(errors),
        users=created_users,
        errors=errors,
        csv_data=csv_data,
    )


# ============================================================================
# ENDPOINT 2: GET /api/admin/login-attempts
# View recent login attempts (all users)
# ============================================================================

@router.get("/login-attempts", response_model=LoginAttemptsResponse)
async def get_login_attempts(
    hours: int = Query(24, ge=1, le=168),  # Last 1-168 hours
    limit: int = Query(100, ge=1, le=1000),
    failed_only: bool = Query(False),  # Show only failed attempts
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    View login attempts (with IP addresses) for security monitoring.
    Only accessible to super_admin or admin.
    """
    # Check authorization
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Query audit_log (same source as auth._record_login)
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = (
        db.query(AuditLog, User.username)
        .outerjoin(User, User.id == AuditLog.user_id)
        .filter(AuditLog.timestamp >= cutoff_time)
        .filter(AuditLog.event_type.in_(_LOGIN_AUDIT_EVENT_TYPES))
    )

    if failed_only:
        query = query.filter(
            or_(AuditLog.event_type != "login_success", AuditLog.success.is_(False))
        )

    rows = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    attempt_responses = [_audit_to_attempt_response(a, uname) for a, uname in rows]

    return LoginAttemptsResponse(
        total=len(attempt_responses),
        attempts=attempt_responses,
    )


# ============================================================================
# ENDPOINT 3: GET /api/admin/users/{user_id}/security
# View security status of a specific user
# ============================================================================

@router.get("/users/{username}/security", response_model=UserSecurityStatusResponse)
async def get_user_security_status(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    View security status of a specific user:
    - Failed login attempts
    - Account lock status
    - Recent IP addresses
    - Recent login attempts
    
    Only accessible to super_admin or admin.
    """
    # Check authorization
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get user
    target_user = db.query(User).filter_by(username=username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Recent login-related audit rows for this user
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    recent_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == target_user.id,
            AuditLog.timestamp >= cutoff_time,
            AuditLog.event_type.in_(_LOGIN_AUDIT_EVENT_TYPES),
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )

    recent_ips = list({a.ip_address for a in recent_audit if a.ip_address})

    # Check if account is locked
    is_locked = (
        target_user.account_locked_until is not None and
        target_user.account_locked_until > datetime.utcnow()
    )

    attempt_responses = [
        _audit_to_attempt_response(a, target_user.username) for a in recent_audit
    ]
    
    return UserSecurityStatusResponse(
        username=target_user.username,
        failed_attempts=target_user.failed_login_attempts,
        is_locked=is_locked,
        locked_until=target_user.account_locked_until.isoformat() if target_user.account_locked_until else None,
        recent_ips=recent_ips,
        recent_attempts=attempt_responses,
    )


# ============================================================================
# ENDPOINT 4: POST /api/admin/users/{username}/unlock
# Manually unlock a locked account
# ============================================================================

@router.post("/users/{username}/unlock")
async def unlock_user_account(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually unlock a user's locked account.
    Only accessible to super_admin.
    """
    # Check authorization
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can unlock accounts")
    
    # Get user
    target_user = db.query(User).filter_by(username=username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Unlock
    target_user.account_locked_until = None
    target_user.failed_login_attempts = 0
    db.commit()
    
    return {"message": f"Account {username} unlocked"}


# ============================================================================
# ENDPOINT 5: GET /api/admin/security-metrics
# Aggregated security metrics for Global Metrics dashboard
# ============================================================================

@router.get("/security-metrics", response_model=SecurityMetricsResponse)
async def get_security_metrics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated security metrics for the last 24 hours.
    Returns:
    - Failed login attempts (24h)
    - Successful login attempts (24h)
    - Unique IPs accessing the system (24h)
    - Count of currently locked accounts
    
    Only accessible to super_admin or admin.
    """
    # Check authorization
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get metrics for the last 24 hours (audit_log — same as auth._record_login)
    cutoff_time = datetime.utcnow() - timedelta(hours=24)

    # Aggregate COUNT only. Legacy Query(Entity).count() can emit a subquery
    # listing every mapped column; DBs missing a column then 500 this endpoint.
    failed_attempts_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.timestamp >= cutoff_time,
            AuditLog.event_type.in_(_LOGIN_AUDIT_EVENT_TYPES),
            AuditLog.event_type != "login_success",
        )
    ).scalar_one()

    successful_attempts_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.timestamp >= cutoff_time,
            AuditLog.event_type == "login_success",
            AuditLog.success.is_(True),
        )
    ).scalar_one()

    unique_ips_24h = db.execute(
        select(func.count(func.distinct(AuditLog.ip_address)))
        .select_from(AuditLog)
        .where(
            AuditLog.timestamp >= cutoff_time,
            AuditLog.event_type.in_(_LOGIN_AUDIT_EVENT_TYPES),
            AuditLog.ip_address.isnot(None),
            AuditLog.ip_address != "",
        )
    ).scalar_one()

    # Count locked accounts (account_locked_until > now)
    locked_accounts_count = db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.account_locked_until.isnot(None),
            User.account_locked_until > datetime.utcnow(),
        )
    ).scalar_one()
    
    return SecurityMetricsResponse(
        failed_attempts_24h=failed_attempts_24h,
        successful_attempts_24h=successful_attempts_24h,
        unique_ips_24h=unique_ips_24h,
        locked_accounts_count=locked_accounts_count,
    )


# ============================================================================
# ENDPOINT: GET /api/admin/security/ip-blocks
# List all blocked IPs (honeypot trap log)
# ============================================================================

@router.get("/security/ip-blocks", response_model=IPBlocksListResponse)
async def list_blocked_ips(
    user: User = Depends(get_current_user_object),
    db: Session = Depends(get_db)
):
    """
    Get list of all blocked IPs (honeypot trap activations).
    Shows IPs caught trying to access the admin account.
    
    Only accessible to super_admin.
    """
    # Check authorization - super_admin only
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can view blocked IPs")
    
    # Get all blocks
    blocks = db.query(IPBlock).order_by(IPBlock.blocked_at.desc()).all()
    
    # Count active blocks
    active_count = db.query(IPBlock).filter(IPBlock.is_active == True).count()
    
    # Convert to response format
    block_responses = []
    for block in blocks:
        block_responses.append(IPBlockResponse(
            id=block.id,
            ip_address=block.ip_address,
            reason=block.reason,
            attempt_count=block.attempt_count,
            blocked_at=block.blocked_at.isoformat() if block.blocked_at else None,
            expires_at=block.expires_at.isoformat() if block.expires_at else None,
            is_active=block.is_active,
            first_attempt=block.first_attempt.isoformat() if block.first_attempt else None,
        ))
    
    return IPBlocksListResponse(
        total=len(blocks),
        active=active_count,
        blocks=block_responses
    )


# ============================================================================
# ENDPOINT: POST /api/admin/security/ip-blocks/{ip_address}/unblock
# Unblock an IP (super_admin only)
# ============================================================================

@router.post("/security/ip-blocks/{ip_address}/unblock", response_model=IPUnblockResponse)
async def unblock_ip(
    ip_address: str,
    user: User = Depends(get_current_user_object),
    db: Session = Depends(get_db)
):
    """
    Unblock a previously blocked IP.
    
    Only accessible to super_admin.
    """
    # Check authorization - super_admin only
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can unblock IPs")
    
    # Find the block
    block = db.query(IPBlock).filter(IPBlock.ip_address == ip_address).first()
    
    if not block:
        raise HTTPException(
            status_code=404, 
            detail=f"No block found for IP {ip_address}"
        )
    
    # Mark as inactive
    block.is_active = False
    db.commit()
    
    return IPUnblockResponse(
        success=True,
        message=f"IP {ip_address} has been unblocked",
        ip_address=ip_address
    )


