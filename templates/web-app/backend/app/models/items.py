"""Item models - Example domain models for the fullstack app.

These models demonstrate how to structure data that flows between
the frontend and backend. Modify or replace with your own domain models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ItemBase(BaseModel):
    """Base item fields shared between create/update/read."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: bool = False


class ItemCreate(ItemBase):
    """Request model for creating a new item."""

    pass


class ItemUpdate(BaseModel):
    """Request model for updating an item. All fields optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: Optional[bool] = None


class Item(ItemBase):
    """Full item model with all fields (response model)."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ItemList(BaseModel):
    """Response model for listing items."""

    items: list[Item]
    total: int
