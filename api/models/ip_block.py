"""
IPBlock model for tracking and enforcing IP-based security blocks.
Used to automatically block IPs attempting admin account attacks.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from datetime import datetime
from database import Base


class IPBlock(Base):
    """
    Track blocked IP addresses for security enforcement.
    
    Attributes:
        id: Primary key
        ip_address: The blocked IP address (IPv4 or IPv6)
        reason: Why the IP was blocked (e.g., "admin_brute_force")
        attempt_count: Number of failed attempts before blocking
        first_attempt: Timestamp of first suspicious attempt
        blocked_at: Timestamp when IP was blocked
        expires_at: When the IP block expires (auto-removal)
        is_active: Whether this block is currently enforced
    """
    
    __tablename__ = "ip_blocks"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)  # IPv4/IPv6
    reason = Column(String(100), nullable=False)  # "admin_brute_force", etc.
    attempt_count = Column(Integer, default=0)
    first_attempt = Column(DateTime, nullable=True)
    blocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Automatic expiration time
    is_active = Column(Boolean, default=True, index=True)
    
    __table_args__ = (
        Index("idx_ip_active", "ip_address", "is_active"),
        Index("idx_expires_at", "expires_at"),
    )
