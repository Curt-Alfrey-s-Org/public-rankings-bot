"""
Alembic environment configuration.

This module initializes Alembic for database migrations with SQLAlchemy.
"""

# Doc refs (AI / maintainers): docs/DATABASE_UPGRADE.md; docs/CONTAINER_DRIFT_PREVENTION.md;
#   docs/PRODUCTION_DEPLOYMENT.md (migrations from app image)

from logging.config import fileConfig
import logging
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add project root to path so we can import from database and models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the database configuration (use lazy-initialized get_engine)
from database import get_engine, Base

# This is the Alembic Config object
config = context.config
logger = logging.getLogger(__name__)

# Set SQLAlchemy URL from environment or config (Postgres only)
sqlalchemy_section = config.get_section('sqlalchemy')
env_db_url = os.environ.get('DATABASE_URL')
if env_db_url:
    config.set_main_option('sqlalchemy.url', env_db_url)
elif not (sqlalchemy_section and sqlalchemy_section.get('sqlalchemy.url')):
    config.set_main_option(
        'sqlalchemy.url',
        'postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot'
    )

# Interpret the config file for Python logging (optional)
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception as e:
        logger.debug("Could not initialize Alembic logging from config file: %s", e)

# Add metadata object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.
    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
