"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns 200 OK if the service is healthy.
    This endpoint is checked by the platform to verify
    that the application started successfully.

    DO NOT remove or modify this endpoint.
    """
    return {"status": "healthy"}

