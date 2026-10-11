"""
SQLAlchemy ORM model for backup codes (2FA).

This module defines the model for managing backup codes used in two-factor authentication.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from datetime import datetime
from database import Base


class BackupCode(Base):
    """
    Backup code model for two-factor authentication recovery.
    
    Backup codes are one-time use codes that users can use to login
    when their 2FA device is not available.
    
    Attributes:
        id: Primary key, auto-incremented integer
        user_id: Foreign key reference to user who owns these codes
        code_hash: Hashed backup code (max 255 chars)
        used: Boolean flag indicating if code has been used
        created_at: Timestamp when code was created
    """
    
    __tablename__ = "backup_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_backup_codes_user_id_used", "user_id", "used"),
        Index("idx_backup_codes_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<BackupCode(id={self.id}, user_id={self.user_id}, used={self.used})>"
