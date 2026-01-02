"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.items import router as items_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Initializes database and runs migrations if database feature is enabled.
    """
    # Initialize database if feature is enabled
    if settings.features_database:
        logger.info("Database feature enabled, initializing...")
        from app.db.migrations import run_migrations
        from app.db.session import warn_if_sqlite_multi_machine

        warn_if_sqlite_multi_machine()
        run_migrations()
        logger.info("Database initialized")

    yield


app = FastAPI(
    title="My App API",
    description="Fullstack Runtm app - Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(items_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "my-web-app-api",
        "version": "0.1.0",
        "docs": "/docs",
    }
