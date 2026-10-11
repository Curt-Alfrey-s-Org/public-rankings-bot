"""
Login attempt tracking service.
Records successful and failed login attempts with IP addresses for security monitoring.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional

from api.models.login_attempt import LoginAttempt
from api.models.user import User


def record_login_attempt(
    db: Session,
    username: str,
    ip_address: str,
    success: bool,
    failure_reason: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    """
    Record a login attempt (success or failure) with IP address.
    
    Args:
        db: Database session
        username: Username attempted
        ip_address: Client IP address
        success: True if login succeeded
        failure_reason: Reason for failure (e.g., "invalid_password", "account_locked")
        user_id: User ID (for successful attempts)
    """
    attempt = LoginAttempt(
        username=username,
        ip_address=ip_address,
        success=success,
        failure_reason=failure_reason,
        user_id=user_id,
        timestamp=datetime.utcnow(),
    )
    db.add(attempt)
    db.commit()


def check_and_update_failed_attempts(
    db: Session,
    user: User,
    ip_address: str,
    max_attempts: int = 5,
    lockout_minutes: int = 30,
) -> bool:
    """
    Check if user account should be locked due to failed login attempts.
    
    Args:
        db: Database session
        user: User object
        ip_address: IP address of attempt
        max_attempts: Max failed attempts before lockout (default 5)
        lockout_minutes: Minutes to lock account (default 30)
    
    Returns:
        True if account is now locked, False otherwise
    """
    # Increment failed attempts
    user.failed_login_attempts += 1
    
    # Check if should lock
    if user.failed_login_attempts >= max_attempts:
        user.account_locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        db.commit()
        
        # Log the lockout
        record_login_attempt(
            db,
            username=user.username,
            ip_address=ip_address,
            success=False,
            failure_reason="account_locked_due_to_attempts",
            user_id=user.id,
        )
        return True
    else:
        db.commit()
        return False


def reset_failed_attempts(db: Session, user: User) -> None:
    """Reset failed login attempts after successful login."""
    user.failed_login_attempts = 0
    user.account_locked_until = None
    db.commit()


def is_account_locked(user: User) -> bool:
    """Check if user account is currently locked."""
    if user.account_locked_until is None:
        return False
    return user.account_locked_until > datetime.utcnow()


def get_account_lock_info(user: User) -> dict:
    """
    Get account lock information.
    
    Returns:
        Dict with keys:
        - is_locked: Whether account is locked
        - locked_until: datetime when lock expires (if locked)
        - minutes_remaining: Minutes until unlock (if locked)
    """
    if not is_account_locked(user):
        return {
            "is_locked": False,
            "locked_until": None,
            "minutes_remaining": 0,
        }
    
    now = datetime.utcnow()
    locked_until = user.account_locked_until
    minutes_remaining = (locked_until - now).total_seconds() / 60
    
    return {
        "is_locked": True,
        "locked_until": locked_until.isoformat(),
        "minutes_remaining": max(1, int(minutes_remaining)),
    }


def get_user_login_history(
    db: Session,
    user_id: int,
    hours: int = 24,
    limit: int = 20,
) -> list:
    """
    Get user's recent login attempts.
    
    Args:
        db: Database session
        user_id: User ID
        hours: Look back this many hours
        limit: Max records to return
    
    Returns:
        List of LoginAttempt records
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return db.query(LoginAttempt).filter(
        LoginAttempt.user_id == user_id,
        LoginAttempt.timestamp >= cutoff,
    ).order_by(LoginAttempt.timestamp.desc()).limit(limit).all()
