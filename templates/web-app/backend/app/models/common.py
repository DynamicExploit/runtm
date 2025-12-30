"""Common response models shared across the API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "healthy"


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str
    detail: str | None = None


class SuccessResponse(BaseModel):
    """Generic success response."""
    
    success: bool = True
    message: str | None = None

