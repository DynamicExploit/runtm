"""Automatic database migrations.

Runs Alembic migrations on startup when database feature is enabled.
Creates the database and runs all pending migrations automatically.
"""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.session import get_engine

logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration.

    Returns:
        Alembic Config object pointing to the migrations directory
    """
    # Find the alembic directory relative to this file
    app_dir = Path(__file__).parent.parent
    alembic_dir = app_dir / "db" / "alembic"

    # Create alembic.ini path (or use programmatic config)
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", os.environ.get(
        "DATABASE_URL", "sqlite:////data/app.db"
    ))

    return alembic_cfg


def run_migrations() -> None:
    """Run all pending database migrations.

    This is called on application startup when features.database is enabled.
    It ensures the database schema is always up to date.

    The migration process:
    1. Creates database file if using SQLite and doesn't exist
    2. Runs all pending Alembic migrations
    3. Logs the migration status
    """
    logger.info("Checking database migrations...")

    # Ensure data directory exists for SQLite
    database_url = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    try:
        alembic_cfg = get_alembic_config()

        # Get engine to ensure connection works
        engine = get_engine()

        # Import all models BEFORE checking alembic - this registers them with Base.metadata
        # This is critical for create_all() fallback to work
        try:
            from app.db import models  # noqa: F401 - import for side effects
        except ImportError:
            logger.debug("No models module found, skipping model import")

        # Check if alembic directory exists with migrations
        alembic_dir = Path(alembic_cfg.get_main_option("script_location"))
        versions_dir = alembic_dir / "versions"
        has_migrations = versions_dir.exists() and any(
            f.suffix == ".py" and f.name != "__init__.py"
            for f in versions_dir.iterdir()
        ) if versions_dir.exists() else False

        if not alembic_dir.exists() or not has_migrations:
            logger.info(
                "No Alembic migrations found. Using create_all() for initial schema."
            )
            # Fallback: create tables directly from models
            from app.db.base import Base
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created via create_all()")
            return

        # Run migrations to head
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations complete")

    except Exception as e:
        logger.error(f"Migration error: {e}")
        # Fallback: try create_all() if migrations fail
        logger.warning("Falling back to create_all() for schema creation")
        try:
            # Import models again to ensure they're registered
            try:
                from app.db import models  # noqa: F401
            except ImportError:
                pass
            from app.db.base import Base
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created via create_all() fallback")
        except Exception as fallback_error:
            logger.error(f"Fallback schema creation also failed: {fallback_error}")
            raise

