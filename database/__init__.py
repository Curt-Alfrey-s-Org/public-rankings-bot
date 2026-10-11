"""Database layer: Postgres only."""
import os
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool

# Declare base for models (imported by api.models.user)
Base = declarative_base()

# Create database engine lazily
_engine = None
_SessionLocal = None
_test_center_engine = None
logger = logging.getLogger(__name__)


def _load_dotenv_from_project_root() -> None:
    """Load .env from repo root when python-dotenv is available (dev / IDE)."""
    try:
        import dotenv

        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
        if env_path.is_file():
            dotenv.load_dotenv(env_path)
    except ImportError:
        pass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r, using default=%s", name, raw, default)
        return default

def _init_engine():
    """Initialize database engine (called once on first use)."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine, _SessionLocal
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        _load_dotenv_from_project_root()
        DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Set it to a valid PostgreSQL connection string, e.g.: "
            "postgresql://user:password@host:port/database"
        )
    _u = DATABASE_URL.strip()
    _allowed = ("postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://")
    if not any(_u.startswith(p) for p in _allowed):
        raise RuntimeError(
            "DATABASE_URL must use PostgreSQL (postgres-only deployment). "
            f"Allowed URL prefixes: {', '.join(_allowed)}. "
            "SQLite and other backends are not supported."
        )
    _engine = _create_engine_from_url(_u)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine, _SessionLocal


def _create_engine_from_url(database_url: str):
    """Shared pool settings for main and Test Center engines."""
    pool_size = _env_int("DB_POOL_SIZE", 10)
    max_overflow = _env_int("DB_MAX_OVERFLOW", 20)
    pool_timeout = _env_int("DB_POOL_TIMEOUT", 30)
    pool_recycle = _env_int("DB_POOL_RECYCLE", 3600)
    sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        echo=sql_echo,
    )


def _validate_postgres_url(url: str, env_label: str) -> str:
    u = url.strip()
    _allowed = ("postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://")
    if not any(u.startswith(p) for p in _allowed):
        raise RuntimeError(
            f"{env_label} must use PostgreSQL. "
            f"Allowed URL prefixes: {', '.join(_allowed)}."
        )
    return u


def get_test_center_engine():
    """
    SQLAlchemy engine for Test Center only (test_* tournament tables).

    When ``TEST_CENTER_DATABASE_URL`` is set, uses a separate PostgreSQL database so
    Test Center reads/writes never hit the main ``DATABASE_URL`` database.

    When unset, falls back to ``get_engine()`` and logs a warning (not recommended for production).
    """
    global _test_center_engine
    url = (os.getenv("TEST_CENTER_DATABASE_URL") or "").strip()
    if not url:
        _load_dotenv_from_project_root()
        url = (os.getenv("TEST_CENTER_DATABASE_URL") or "").strip()
    if not url:
        logger.warning(
            "TEST_CENTER_DATABASE_URL is not set; Test Center uses DATABASE_URL for test_* tables. "
            "Set TEST_CENTER_DATABASE_URL to a dedicated database (e.g. rankings_testcenter on the same Postgres "
            "instance) so Test Center never writes to production data."
        )
        return get_engine()
    u = _validate_postgres_url(url, "TEST_CENTER_DATABASE_URL")
    if _test_center_engine is None:
        _test_center_engine = _create_engine_from_url(u)
    return _test_center_engine

def get_engine():
    """Get database engine (lazy init)."""
    engine, _ = _init_engine()
    return engine

def get_session_local():
    """Get session factory (lazy init)."""
    _, session_local = _init_engine()
    return session_local

def get_db() -> Session:
    """Get database session (FastAPI dependency)."""
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()

def get_db_session() -> Session:
    """Get database session."""
    session_local = get_session_local()
    return session_local()

def get_database_manager():
    """Get database manager instance (PostgresManager)."""
    from database.postgres_manager import PostgresManager
    return PostgresManager()

def ensure_rankings_tables_postgres():
    """Create all tables in PostgreSQL."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

__all__ = [
    "Base",
    "get_engine",
    "get_test_center_engine",
    "get_session_local",
    "get_db",
    "get_db_session",
    "get_database_manager",
    "ensure_rankings_tables_postgres",
]



