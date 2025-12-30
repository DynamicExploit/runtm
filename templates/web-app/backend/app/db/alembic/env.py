"""Alembic environment configuration.

This module is used by Alembic to run migrations.
It configures the migration context with the SQLAlchemy engine.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

# Import your models' Base and all models for autogenerate
from app.db.base import Base

# Alembic Config object
config = context.config

# Set up logging if alembic.ini exists
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment or config."""
    return os.environ.get("DATABASE_URL", "sqlite:////data/app.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL scripts instead of executing directly.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects to the database and runs migrations directly.
    """
    from sqlalchemy import create_engine

    url = get_url()
    connect_args = {}

    # SQLite-specific configuration
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

