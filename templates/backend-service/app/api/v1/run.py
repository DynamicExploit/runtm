"""Main tool endpoint - REST API for the tool.

This module defines the API endpoint. Business logic is delegated
to the ProcessorService - endpoints should remain thin.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ProcessorService, processor_service

router = APIRouter()


class RunRequest(BaseModel):
    """Request body for the run endpoint."""

    input: str
    options: Dict[str, Any] = {}


class RunResponse(BaseModel):
    """Response body for the run endpoint."""

    output: str
    metadata: Dict[str, Any] = {}


def get_processor_service() -> ProcessorService:
    """Get the processor service instance.
    
    This function can be replaced with proper dependency injection
    if needed (e.g., for testing or different environments).
    """
    return processor_service


@router.post("/run", response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Main tool endpoint.

    Processes the input using the ProcessorService and returns the result.

    Args:
        request: Input data for the tool

    Returns:
        Tool output and metadata
    """
    service = get_processor_service()
    
    # Validate input
    if not service.validate_input(request.input):
        raise HTTPException(status_code=400, detail="Invalid input")
    
    # Process the input
    result = service.process(request.input, request.options)

    return RunResponse(
        output=result["output"],
        metadata=result["metadata"],
    )
