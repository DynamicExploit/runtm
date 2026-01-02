"""Tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient

from runtm_api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_returns_200(client):
    """Health endpoint should return 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status(client):
    """Health endpoint should return status."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
