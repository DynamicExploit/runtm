"""Database session management for Runtm API."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from runtm_api.core.config import get_settings


def get_engine():
    """Create database engine."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory() -> sessionmaker:
    """Create session factory."""
    engine = get_engine()
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session.

    Usage:
        @router.get("/")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# For use in non-FastAPI contexts (e.g., worker)
def create_session() -> Session:
    """Create a new database session.

    Remember to close the session when done:
        session = create_session()
        try:
            # use session
        finally:
            session.close()
    """
    session_factory = get_session_factory()
    return session_factory()
