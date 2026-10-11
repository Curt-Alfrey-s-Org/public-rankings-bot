"""
Database configuration and session management for SQLAlchemy ORM.

Re-exports from the database package (Postgres only). Use this module or
the database package interchangeably; both require DATABASE_URL (Postgres).
"""

from database import (
    Base,
    ensure_rankings_tables_postgres,
    get_db,
    get_database_manager,
    get_engine,
    get_session_local,
    get_test_center_engine,
)

__all__ = [
    "Base",
    "ensure_rankings_tables_postgres",
    "get_db",
    "get_database_manager",
    "get_engine",
    "get_session_local",
    "get_test_center_engine",
]


def init_db():
    """Create ORM tables on the Postgres engine (dev/bootstrap helper)."""
    from api.models.user import Base as UserBase

    UserBase.metadata.create_all(bind=get_engine())
