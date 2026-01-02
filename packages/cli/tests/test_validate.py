"""Tests for validate command."""

import tempfile
from pathlib import Path

from runtm_cli.commands.validate import validate_project


def test_validate_missing_manifest():
    """Should fail without runtm.yaml."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir)
        is_valid, errors, warnings = validate_project(path)
        assert not is_valid
        assert any("runtm.yaml" in e for e in errors)


def test_validate_missing_dockerfile():
    """Should fail without Dockerfile."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir)

        # Create valid manifest
        (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")

        is_valid, errors, warnings = validate_project(path)
        assert not is_valid
        assert any("Dockerfile" in e for e in errors)


def test_validate_valid_project():
    """Should pass with valid project."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir)

        # Create valid manifest
        (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")

        # Create Dockerfile
        (path / "Dockerfile").write_text("FROM python:3.12-slim")

        is_valid, errors, warnings = validate_project(path)
        assert is_valid
        assert len(errors) == 0


def test_validate_env_file_warning():
    """Should warn about .env file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir)

        # Create valid manifest
        (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")
        (path / "Dockerfile").write_text("FROM python:3.12-slim")
        (path / ".env").write_text("SECRET=value")

        is_valid, errors, warnings = validate_project(path)
        assert is_valid
        assert any(".env" in w for w in warnings)
