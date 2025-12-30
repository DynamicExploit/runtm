"""FastAPI application entrypoint for Runtm API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure .env is loaded from project root before anything else
from runtm_shared.env import ensure_env_loaded  # noqa: F401

ensure_env_loaded()

from runtm_api import __version__
from runtm_api.core.config import get_settings
from runtm_api.routes import deployments_router, health_router, telemetry_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Runs startup and shutdown logic.
    """
    # Startup
    settings = get_settings()
    print(f"Starting Runtm API v{__version__}")
    print(f"Auth mode: {settings.auth_mode.value}")
    print(f"Debug mode: {settings.debug}")

    yield

    # Shutdown
    print("Shutting down Runtm API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Runtm API",
        description="Control plane API for Runtm deployments",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(deployments_router)
    app.include_router(telemetry_router)

    return app


# Create app instance
app = create_app()

