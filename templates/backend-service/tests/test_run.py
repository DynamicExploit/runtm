"""Tests for run endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_run_with_input():
    """Run endpoint should process input."""
    response = client.post(
        "/api/v1/run",
        json={"input": "hello world"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "output" in data
    assert "Processed:" in data["output"]


def test_run_with_options():
    """Run endpoint should accept options."""
    response = client.post(
        "/api/v1/run",
        json={
            "input": "test",
            "options": {"key": "value"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["options_used"] == {"key": "value"}


def test_run_returns_metadata():
    """Run endpoint should return metadata."""
    response = client.post(
        "/api/v1/run",
        json={"input": "test input"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert data["metadata"]["input_length"] == 10
