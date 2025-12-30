"""Tests for health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    """Health endpoint should return 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_healthy():
    """Health endpoint should return healthy status."""
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}

