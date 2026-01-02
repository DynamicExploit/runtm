"""FastAPI application entrypoint for Runtm API."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure .env is loaded from project root before anything else
from runtm_shared.env import ensure_env_loaded  # noqa: F401

ensure_env_loaded()

from runtm_api import __version__
from runtm_api.core.config import get_settings
from runtm_api.routes import deployments_router, health_router, me_router, telemetry_router


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

    # Initialize Redis rate limiter
    # SECURITY: Rate limiting fails closed in production - if Redis is unavailable,
    # auth requests return 503 rather than allowing unthrottled access
    if settings.redis_url:
        try:
            import redis

            from runtm_api.services.rate_limit import RateLimiter, set_rate_limiter

            redis_client = redis.from_url(settings.redis_url)
            # Test connection
            redis_client.ping()
            set_rate_limiter(RateLimiter(redis_client))
            print("Rate limiter initialized with Redis")
        except Exception as e:
            if settings.debug:
                print(f"Warning: Redis rate limiter unavailable: {e}")
                print("Rate limiting disabled for local development")
            else:
                print(f"ERROR: Redis rate limiter failed to initialize: {e}")
                print("SECURITY: Auth rate limiting will fail closed (503)")

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

    # TLS enforcement middleware (production only)
    # SECURITY: Only trusts X-Forwarded-Proto from trusted proxies
    if settings.require_tls and not settings.debug:
        from runtm_api.middleware.proxy import TLSEnforcementMiddleware

        app.add_middleware(TLSEnforcementMiddleware, settings=settings)

    # CORS middleware - secure configuration
    # SECURITY: Never combine allow_origins=["*"] with allow_credentials=True
    if settings.debug:
        # Debug mode: explicit localhost origins only
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif settings.cors_origins_list:
        # Production with explicit origins configured
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    # else: No CORS middleware = API-only, browser requests blocked

    # Include routers
    app.include_router(health_router)
    app.include_router(deployments_router)
    app.include_router(me_router)
    app.include_router(telemetry_router)

    return app


# Create app instance
app = create_app()
