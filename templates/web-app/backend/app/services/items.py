"""Items service - Business logic for item operations.

This service encapsulates all business logic related to items.
The API layer should call these methods rather than implementing logic directly.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from app.models import Item, ItemCreate, ItemUpdate


class ItemsService:
    """Service for managing items.

    This class contains all business logic for item operations.
    In a real application, this would interact with a database.
    """

    def __init__(self) -> None:
        """Initialize the items service with in-memory storage."""
        self._items: Dict[str, Item] = {}

    @staticmethod
    def _now() -> datetime:
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc)

    def list_items(self) -> List[Item]:
        """List all items, sorted by creation date (newest first).

        Returns:
            List of all items
        """
        items = list(self._items.values())
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def get_item(self, item_id: str) -> Optional[Item]:
        """Get a specific item by ID.

        Args:
            item_id: The item ID to look up

        Returns:
            The item if found, None otherwise
        """
        return self._items.get(item_id)

    def create_item(self, data: ItemCreate) -> Item:
        """Create a new item.

        Args:
            data: Item creation data

        Returns:
            The newly created item
        """
        now = self._now()
        item = Item(
            id=str(uuid4()),
            title=data.title,
            description=data.description,
            completed=data.completed,
            created_at=now,
            updated_at=now,
        )
        self._items[item.id] = item
        return item

    def update_item(self, item_id: str, data: ItemUpdate) -> Optional[Item]:
        """Update an existing item.

        Args:
            item_id: The ID of the item to update
            data: The update data (partial update supported)

        Returns:
            The updated item if found, None otherwise
        """
        if item_id not in self._items:
            return None

        item = self._items[item_id]
        update_data = data.model_dump(exclude_unset=True)

        # Apply updates
        updated_item = item.model_copy(
            update={
                **update_data,
                "updated_at": self._now(),
            }
        )
        self._items[item_id] = updated_item
        return updated_item

    def delete_item(self, item_id: str) -> bool:
        """Delete an item.

        Args:
            item_id: The ID of the item to delete

        Returns:
            True if the item was deleted, False if not found
        """
        if item_id not in self._items:
            return False

        del self._items[item_id]
        return True

    def toggle_complete(self, item_id: str) -> Optional[Item]:
        """Toggle the completion status of an item.

        Args:
            item_id: The ID of the item to toggle

        Returns:
            The updated item if found, None otherwise
        """
        item = self.get_item(item_id)
        if not item:
            return None

        return self.update_item(item_id, ItemUpdate(completed=not item.completed))


# Singleton instance for use across the application
# In a real app, you might use dependency injection instead
items_service = ItemsService()
