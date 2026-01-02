"""Items API endpoints - REST API for item operations.

This module defines the API endpoints. Business logic is delegated
to the ItemsService - endpoints should remain thin.
"""

from fastapi import APIRouter, HTTPException

from app.models import Item, ItemCreate, ItemList, ItemUpdate, SuccessResponse
from app.services import ItemsService
from app.services.items import items_service

router = APIRouter()


def get_items_service() -> ItemsService:
    """Get the items service instance.

    This function can be replaced with proper dependency injection
    if needed (e.g., for testing or different environments).
    """
    return items_service


@router.get("/items", response_model=ItemList)
async def list_items() -> ItemList:
    """List all items."""
    service = get_items_service()
    items = service.list_items()
    return ItemList(items=items, total=len(items))


@router.post("/items", response_model=Item, status_code=201)
async def create_item(data: ItemCreate) -> Item:
    """Create a new item."""
    service = get_items_service()
    return service.create_item(data)


@router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: str) -> Item:
    """Get a specific item by ID."""
    service = get_items_service()
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, data: ItemUpdate) -> Item:
    """Update an existing item."""
    service = get_items_service()
    item = service.update_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}", response_model=SuccessResponse)
async def delete_item(item_id: str) -> SuccessResponse:
    """Delete an item."""
    service = get_items_service()
    if not service.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return SuccessResponse(message="Item deleted successfully")
