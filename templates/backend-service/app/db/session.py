"""Database session management.

Provides SQLite with WAL mode and proper pragmas for concurrent access.
Supports optional external PostgreSQL via DATABASE_URL environment variable.
"""

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Database URL: defaults to SQLite in /data for persistence
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the database engine.

    Configures SQLite with WAL mode and proper pragmas for:
    - Better concurrent read performance
    - Safer writes with WAL journaling
    - Foreign key enforcement

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is not None:
        return _engine

    url = DATABASE_URL

    # SQLite-specific configuration
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(url, connect_args=connect_args)

    # Set SQLite pragmas for performance and safety
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # WAL mode for better concurrent reads
            cursor.execute("PRAGMA journal_mode=WAL")
            # Faster syncs (still safe with WAL)
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info("SQLite engine configured with WAL mode")
    else:
        logger.info(f"Database engine configured: {url.split('@')[-1] if '@' in url else url}")

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory.

    Returns:
        SQLAlchemy sessionmaker instance
    """
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    engine = get_engine()
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions.

    Provides a database session that's automatically closed after the request.

    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        SQLAlchemy Session
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def warn_if_sqlite_multi_machine() -> None:
    """Warn if SQLite is used in a multi-machine environment.

    Called on startup to alert users about SQLite's single-writer constraint.
    """
    fly_machine_id = os.environ.get("FLY_MACHINE_ID")

    if "sqlite" in DATABASE_URL and fly_machine_id:
        logger.warning(
            "SQLite database detected on Fly.io. "
            "Ensure only ONE machine is running to avoid database corruption. "
            "For multiple machines, switch to PostgreSQL via DATABASE_URL."
        )

