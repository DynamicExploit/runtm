"""Tests for runtm_shared.ids."""

from runtm_shared.ids import (
    generate_artifact_key,
    generate_deployment_id,
    generate_idempotency_key,
    is_valid_deployment_id,
    parse_deployment_id,
)


class TestDeploymentIdGeneration:
    """Tests for deployment ID generation."""

    def test_has_correct_prefix(self) -> None:
        """Generated ID should start with 'dep_'."""
        deployment_id = generate_deployment_id()
        assert deployment_id.startswith("dep_")

    def test_has_correct_length(self) -> None:
        """Generated ID should have correct total length."""
        deployment_id = generate_deployment_id()
        # "dep_" (4) + 12 hex chars = 16
        assert len(deployment_id) == 16

    def test_random_ids_are_unique(self) -> None:
        """Random IDs should be unique."""
        ids = {generate_deployment_id() for _ in range(100)}
        assert len(ids) == 100

    def test_is_valid_hex(self) -> None:
        """Suffix should be valid hex."""
        deployment_id = generate_deployment_id()
        suffix = deployment_id[4:]  # Remove "dep_"
        int(suffix, 16)  # Should not raise


class TestDeploymentIdValidation:
    """Tests for deployment ID validation."""

    def test_valid_id(self) -> None:
        """Valid deployment ID should pass."""
        assert is_valid_deployment_id("dep_a1b2c3d4e5f6")

    def test_wrong_prefix(self) -> None:
        """Wrong prefix should fail."""
        assert not is_valid_deployment_id("dpl_a1b2c3d4e5f6")

    def test_too_short(self) -> None:
        """Too short suffix should fail."""
        assert not is_valid_deployment_id("dep_a1b2c3")

    def test_too_long(self) -> None:
        """Too long suffix should fail."""
        assert not is_valid_deployment_id("dep_a1b2c3d4e5f6g7h8")

    def test_invalid_hex(self) -> None:
        """Invalid hex characters should fail."""
        assert not is_valid_deployment_id("dep_ghijklmnopqr")

    def test_parse_valid(self) -> None:
        """parse_deployment_id should return valid IDs."""
        assert parse_deployment_id("dep_a1b2c3d4e5f6") == "dep_a1b2c3d4e5f6"

    def test_parse_invalid(self) -> None:
        """parse_deployment_id should return None for invalid IDs."""
        assert parse_deployment_id("invalid") is None


class TestIdempotencyKey:
    """Tests for idempotency key generation."""

    def test_has_correct_length(self) -> None:
        """Idempotency key should be 32 hex chars."""
        key = generate_idempotency_key()
        assert len(key) == 32

    def test_is_valid_hex(self) -> None:
        """Key should be valid hex."""
        key = generate_idempotency_key()
        int(key, 16)  # Should not raise

    def test_unique(self) -> None:
        """Keys should be unique."""
        keys = {generate_idempotency_key() for _ in range(100)}
        assert len(keys) == 100


class TestArtifactKey:
    """Tests for artifact key generation."""

    def test_artifact_key_format(self) -> None:
        """Artifact key should have correct format."""
        key = generate_artifact_key("dep_a1b2c3d4e5f6")
        assert key == "artifacts/dep_a1b2c3d4e5f6/artifact.zip"
