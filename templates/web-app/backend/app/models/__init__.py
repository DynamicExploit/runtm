"""Shared Pydantic models for API requests and responses.

These models define the contract between frontend and backend.
The frontend TypeScript types should mirror these models.
"""

from app.models.common import (
    ErrorResponse,
    HealthResponse,
    SuccessResponse,
)
from app.models.items import (
    Item,
    ItemCreate,
    ItemList,
    ItemUpdate,
)

__all__ = [
    # Item models
    "Item",
    "ItemCreate",
    "ItemUpdate",
    "ItemList",
    # Common models
    "HealthResponse",
    "ErrorResponse",
    "SuccessResponse",
]
