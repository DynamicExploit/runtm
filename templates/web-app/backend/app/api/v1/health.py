"""Health check endpoint."""

from fastapi import APIRouter

from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns 200 OK if the service is healthy.
    This endpoint is checked by the platform to verify
    that the application started successfully.

    DO NOT remove or modify this endpoint.
    """
    return HealthResponse(status="healthy")

