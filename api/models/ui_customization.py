"""
UI customization settings stored in the database.
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class UiCustomization(Base):
    """Global UI customization payload stored as JSON."""

    __tablename__ = "ui_customizations"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(64), unique=True, nullable=False, default="global")
    data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_ui_customizations_scope", "scope"),
    )
