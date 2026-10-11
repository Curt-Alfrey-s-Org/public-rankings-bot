"""
SQLAlchemy ORM model for audit logging.

This module defines the model for tracking authentication and security events.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from datetime import datetime
from database import Base


class AuditLog(Base):
    """
    Audit log model for tracking authentication and security events.
    
    Attributes:
        id: Primary key, auto-incremented integer
        user_id: Optional reference to user involved in the event (nullable)
        event_type: Type of event (login, logout, failed_login, register, etc.)
        ip_address: Client IP address (IPv4 or IPv6, max 45 chars)
        user_agent: Client user agent string (max 255 chars)
        success: Boolean flag indicating if event was successful
        details: Additional details about the event (JSON or text)
        timestamp: When the event occurred
    """
    
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    success = Column(Boolean, default=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_user_id_timestamp", "user_id", "timestamp"),
        Index("idx_event_type_timestamp", "event_type", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, user_id={self.user_id}, success={self.success})>"
