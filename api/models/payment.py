"""
Payment and Subscription ORM models for AI Coach Stripe integration.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index
from datetime import datetime, timezone
from database import Base


class Payment(Base):
    """
    Tracks Stripe payment intents for AI Coach passes.
    """

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    stripe_intent_id = Column(String(128), unique=True, nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    hours = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="pending")  # pending, succeeded, canceled, failed
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("idx_payment_user_status", "user_id", "status"),)


class Subscription(Base):
    """
    Tracks AI Coach hour passes (1-hour pass purchases).
    """

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    stripe_customer_id = Column(String(128), nullable=True, index=True)
    hours_remaining = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("idx_sub_user_active", "user_id", "hours_remaining"),)
