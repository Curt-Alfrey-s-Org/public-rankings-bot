"""
Database access for admin and other API routes.
Re-exports get_database_manager as get_db_manager for compatibility.
"""

from database import get_database_manager


def get_db_manager():
    """Get database manager (Postgres, DATABASE_URL)."""
    return get_database_manager()
