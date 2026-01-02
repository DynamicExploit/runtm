"""Tests for runtm_shared.errors."""

from runtm_shared.errors import (
    ArtifactTooLargeError,
    DeploymentNotFoundError,
    InvalidTokenError,
    ManifestNotFoundError,
    ManifestValidationError,
    RateLimitError,
    RuntmError,
)


class TestRuntmError:
    """Tests for base RuntmError."""

    def test_message(self) -> None:
        """Error should have message."""
        error = RuntmError("Test error")
        assert str(error) == "Test error"

    def test_with_recovery_hint(self) -> None:
        """Error should include recovery hint in string."""
        error = RuntmError("Test error", recovery_hint="Try again")
        assert "Test error" in str(error)
        assert "Recovery: Try again" in str(error)

    def test_to_dict(self) -> None:
        """Error should convert to dict."""
        error = RuntmError(
            "Test error",
            recovery_hint="Try again",
            error_code="TEST_ERROR",
        )
        d = error.to_dict()
        assert d["error"] == "Test error"
        assert d["code"] == "TEST_ERROR"
        assert d["recovery_hint"] == "Try again"


class TestManifestErrors:
    """Tests for manifest-related errors."""

    def test_manifest_not_found(self) -> None:
        """ManifestNotFoundError should have correct message."""
        error = ManifestNotFoundError("/my/path")
        assert "Missing runtm.yaml" in str(error)
        assert "runtm init" in str(error)

    def test_manifest_validation_error(self) -> None:
        """ManifestValidationError should have correct message."""
        error = ManifestValidationError("invalid name", field="name")
        assert "Invalid manifest" in str(error)
        assert error.field == "name"


class TestArtifactErrors:
    """Tests for artifact-related errors."""

    def test_artifact_too_large(self) -> None:
        """ArtifactTooLargeError should show sizes in MB."""
        error = ArtifactTooLargeError(
            size_bytes=25 * 1024 * 1024,
            max_bytes=20 * 1024 * 1024,
        )
        assert "25.0 MB" in str(error)
        assert "20 MB" in str(error)


class TestDeploymentErrors:
    """Tests for deployment-related errors."""

    def test_deployment_not_found(self) -> None:
        """DeploymentNotFoundError should include deployment ID."""
        error = DeploymentNotFoundError("dep_abc123")
        assert "dep_abc123" in str(error)


class TestAuthErrors:
    """Tests for auth-related errors."""

    def test_invalid_token(self) -> None:
        """InvalidTokenError should suggest fix."""
        error = InvalidTokenError()
        assert "Invalid" in str(error)
        assert "RUNTM_API_KEY" in str(error)

    def test_rate_limit_with_retry(self) -> None:
        """RateLimitError should include retry time."""
        error = RateLimitError(retry_after_seconds=60)
        assert "Rate limit" in str(error)
        assert "60 seconds" in str(error)
        assert error.retry_after_seconds == 60
