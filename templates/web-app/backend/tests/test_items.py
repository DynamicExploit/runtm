"""Items API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_item():
    """Test creating a new item."""
    response = client.post(
        "/api/v1/items",
        json={"title": "Test Item", "description": "A test item"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["description"] == "A test item"
    assert data["completed"] is False
    assert "id" in data
    assert "created_at" in data


def test_list_items():
    """Test listing items."""
    response = client.get("/api/v1/items")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_item_not_found():
    """Test getting a non-existent item."""
    response = client.get("/api/v1/items/nonexistent-id")
    assert response.status_code == 404


def test_update_item():
    """Test updating an item."""
    # Create an item first
    create_response = client.post(
        "/api/v1/items",
        json={"title": "Original Title"},
    )
    item_id = create_response.json()["id"]
    
    # Update it
    update_response = client.patch(
        f"/api/v1/items/{item_id}",
        json={"title": "Updated Title", "completed": True},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["title"] == "Updated Title"
    assert data["completed"] is True


def test_delete_item():
    """Test deleting an item."""
    # Create an item first
    create_response = client.post(
        "/api/v1/items",
        json={"title": "To Be Deleted"},
    )
    item_id = create_response.json()["id"]
    
    # Delete it
    delete_response = client.delete(f"/api/v1/items/{item_id}")
    assert delete_response.status_code == 200
    
    # Verify it's gone
    get_response = client.get(f"/api/v1/items/{item_id}")
    assert get_response.status_code == 404

