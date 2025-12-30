"""API routes."""

from runtm_api.routes.deployments import router as deployments_router
from runtm_api.routes.health import router as health_router
from runtm_api.routes.telemetry import router as telemetry_router

__all__ = [
    "deployments_router",
    "health_router",
    "telemetry_router",
]
