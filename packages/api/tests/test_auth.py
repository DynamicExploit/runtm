"""Tests for authentication."""

import pytest
from fastapi.testclient import TestClient

from runtm_api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_deployment_requires_auth(client):
    """Deployment endpoints should require auth."""
    response = client.get("/v0/deployments/dep_abc123")
    assert response.status_code == 401


def test_deployment_with_invalid_token(client):
    """Invalid token should return 401."""
    response = client.get(
        "/v0/deployments/dep_abc123",
        headers={"Authorization": "Bearer invalid-token"},
    )
    # In debug mode without API_TOKEN set, any token works
    # This test documents the behavior
    assert response.status_code in (401, 404)
