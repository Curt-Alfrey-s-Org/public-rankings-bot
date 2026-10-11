"""
LoginAttempt model for tracking failed login attempts with IP addresses.
Used for security monitoring and account lockout enforcement.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from datetime import datetime
from database import Base


class LoginAttempt(Base):
    """
    Track login attempts (successful and failed) for security monitoring.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User (nullable for attempts to non-existent users)
        username: Username attempted (for failed attempts on non-existent accounts)
        ip_address: IP address of the attempt
        success: True if login succeeded, False if failed
        failure_reason: Why it failed (e.g., "invalid_password", "account_locked", "invalid_user")
        timestamp: When the attempt occurred
    """
    
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(50), nullable=False, index=True)  # Always record the attempted username
    ip_address = Column(String(45), nullable=False)  # Supports both IPv4 and IPv6
    success = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_user_timestamp", "user_id", "timestamp"),
        Index("idx_ip_timestamp", "ip_address", "timestamp"),
        Index("idx_username_timestamp", "username", "timestamp"),
    )
