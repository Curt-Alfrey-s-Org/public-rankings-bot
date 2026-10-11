"""
SQLAlchemy ORM model for user authentication system.

This module defines the core data model for user account management,
including user accounts with authentication and profile information.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, CheckConstraint, Index, Text
from datetime import datetime
from database import Base


class User(Base):
    """
    User account model for storing user authentication and profile information.
    
    Attributes:
        id: Primary key, auto-incremented integer
        username: Unique username for login (max 50 chars)
        email: Unique email address (max 120 chars)
        password_hash: Hashed password using bcrypt or similar (max 255 chars)
        role: user, director, admin, super_admin, moderator, or score_keeper (tablet score-entry mode, director-assigned).
        email_verified: Boolean flag for email verification status
        totp_secret: Optional TOTP secret for 2FA (max 32 chars)
        totp_enabled: Boolean flag for 2FA enablement
        created_at: Account creation timestamp
        last_login: Last successful login timestamp
        failed_login_attempts: Counter for failed login attempts
        account_locked_until: Timestamp for account lockout period
        is_active: Boolean flag for account activation status
    """
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    email_verified = Column(Boolean, default=False)
    totp_secret = Column(String(32), nullable=True)
    totp_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)  # Force password change on next login
    requires_email_setup = Column(Boolean, default=False)  # Require email setup on next login
    force_password_reset = Column(Boolean, default=False)  # Force password reset after email verification
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    home_pool_room = Column(String(200), nullable=True)
    preferences_json = Column(Text, nullable=True, default='{}')  # JSON: {"ranking_history_days": 30}
    
    __table_args__ = (
        CheckConstraint("failed_login_attempts >= 0", name="check_failed_login_non_negative"),
        CheckConstraint("role IN ('user', 'admin', 'director', 'moderator', 'super_admin', 'score_keeper')", name="check_role_values"),
        Index("idx_username_active", "username", "is_active"),
        Index("idx_email_verified", "email", "email_verified"),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email}, is_active={self.is_active})>"
