"""
SQLAlchemy ORM models for authentication tokens.

This module defines models for managing email verification tokens,
password reset tokens, and backup codes for 2FA.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from datetime import datetime
from database import Base


class EmailVerificationToken(Base):
    """
    Email verification token model for user email confirmation.
    
    Attributes:
        id: Primary key, auto-incremented integer
        token: Unique token string (max 255 chars)
        user_id: Foreign key reference to user who needs email verification
        expires_at: Token expiration timestamp
        used: Boolean flag indicating if token has been used
    """
    
    __tablename__ = "email_verification_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    
    __table_args__ = (
        Index("idx_email_verification_tokens_user_id_used", "user_id", "used"),
        Index("idx_email_verification_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<EmailVerificationToken(id={self.id}, token={self.token[:10]}..., user_id={self.user_id}, used={self.used})>"


class PasswordResetToken(Base):
    """
    Password reset token model for password recovery.
    
    Attributes:
        id: Primary key, auto-incremented integer
        token: Unique token string (max 255 chars)
        user_id: Foreign key reference to user requesting password reset
        expires_at: Token expiration timestamp
        used: Boolean flag indicating if token has been used
        created_at: Timestamp when token was created
    """
    
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_password_reset_tokens_user_id_used", "user_id", "used"),
        Index("idx_password_reset_tokens_expires_at", "expires_at"),
        Index("idx_password_reset_tokens_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken(id={self.id}, token={self.token[:10]}..., user_id={self.user_id}, used={self.used})>"
