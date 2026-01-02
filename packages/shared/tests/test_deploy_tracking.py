"""Tests for deploy tracking (concurrent deploy reservation)."""

from unittest.mock import MagicMock, patch

import pytest

from runtm_shared.deploy_tracking import (
    CONCURRENT_DEPLOY_TTL_SECONDS,
    get_concurrent_deploy_count,
    release_concurrent_deploy,
    reserve_concurrent_deploy,
)


class TestReserveConcurrentDeploy:
    """Tests for reserve_concurrent_deploy function."""

    def test_unlimited_always_allowed(self) -> None:
        """When limit is None, always return allowed."""
        redis = MagicMock()
        allowed, count = reserve_concurrent_deploy(redis, "tenant_1", limit=None)

        assert allowed is True
        assert count == 0
        # Redis should not be called for unlimited
        redis.pipeline.assert_not_called()

    def test_first_deploy_allowed(self) -> None:
        """First deploy should be allowed when limit > 0."""
        redis = MagicMock()
        pipe = MagicMock()
        redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]  # count=1 after INCR

        allowed, count = reserve_concurrent_deploy(
            redis, "tenant_1", limit=3, deployment_id="dep_123"
        )

        assert allowed is True
        assert count == 1
        pipe.incr.assert_called_once()
        pipe.expire.assert_called_once_with(
            "concurrent_deploys:tenant_1", CONCURRENT_DEPLOY_TTL_SECONDS
        )

    def test_at_limit_still_allowed(self) -> None:
        """Deploy at limit should be allowed (limit=3, count becomes 3)."""
        redis = MagicMock()
        pipe = MagicMock()
        redis.pipeline.return_value = pipe
        pipe.execute.return_value = [3, True]  # count=3 after INCR (limit is 3)

        allowed, count = reserve_concurrent_deploy(redis, "tenant_1", limit=3)

        assert allowed is True
        assert count == 3
        redis.decr.assert_not_called()

    def test_over_limit_denied_and_decremented(self) -> None:
        """Deploy over limit should be denied and counter decremented."""
        redis = MagicMock()
        pipe = MagicMock()
        redis.pipeline.return_value = pipe
        pipe.execute.return_value = [4, True]  # count=4 after INCR (limit is 3)

        allowed, count = reserve_concurrent_deploy(redis, "tenant_1", limit=3)

        assert allowed is False
        assert count == 3  # Returns count - 1 after decrement
        redis.decr.assert_called_once_with("concurrent_deploys:tenant_1")

    def test_deployment_slot_tracked(self) -> None:
        """Deployment ID should be tracked for debugging when provided."""
        redis = MagicMock()
        pipe = MagicMock()
        redis.pipeline.return_value = pipe
        pipe.execute.return_value = [1, True]

        reserve_concurrent_deploy(
            redis, "tenant_1", limit=3, deployment_id="dep_abc123"
        )

        redis.setex.assert_called_once_with(
            "concurrent_deploy_slot:tenant_1:dep_abc123",
            CONCURRENT_DEPLOY_TTL_SECONDS,
            "1",
        )

    def test_no_slot_tracking_when_denied(self) -> None:
        """Deployment ID should not be tracked when denied."""
        redis = MagicMock()
        pipe = MagicMock()
        redis.pipeline.return_value = pipe
        pipe.execute.return_value = [4, True]  # over limit

        reserve_concurrent_deploy(
            redis, "tenant_1", limit=3, deployment_id="dep_abc123"
        )

        # setex should not be called since we were denied
        redis.setex.assert_not_called()


class TestReleaseConcurrentDeploy:
    """Tests for release_concurrent_deploy function."""

    def test_decrements_counter(self) -> None:
        """Release should decrement the counter."""
        redis = MagicMock()
        redis.decr.return_value = 2

        count = release_concurrent_deploy(redis, "tenant_1")

        assert count == 2
        redis.decr.assert_called_once_with("concurrent_deploys:tenant_1")

    def test_clamps_to_zero(self) -> None:
        """Counter should never go below zero."""
        redis = MagicMock()
        redis.decr.return_value = -1  # Somehow went negative

        count = release_concurrent_deploy(redis, "tenant_1")

        assert count == 0
        redis.set.assert_called_once_with("concurrent_deploys:tenant_1", 0)

    def test_cleans_up_slot_tracker(self) -> None:
        """Slot tracker should be cleaned up when deployment_id provided."""
        redis = MagicMock()
        redis.decr.return_value = 1

        release_concurrent_deploy(redis, "tenant_1", deployment_id="dep_abc123")

        redis.delete.assert_called_once_with(
            "concurrent_deploy_slot:tenant_1:dep_abc123"
        )

    def test_no_slot_cleanup_without_deployment_id(self) -> None:
        """No slot cleanup when deployment_id not provided."""
        redis = MagicMock()
        redis.decr.return_value = 1

        release_concurrent_deploy(redis, "tenant_1")

        redis.delete.assert_not_called()


class TestGetConcurrentDeployCount:
    """Tests for get_concurrent_deploy_count function."""

    def test_returns_count_as_int(self) -> None:
        """Count should be returned as an integer."""
        redis = MagicMock()
        redis.get.return_value = b"3"

        count = get_concurrent_deploy_count(redis, "tenant_1")

        assert count == 3
        redis.get.assert_called_once_with("concurrent_deploys:tenant_1")

    def test_returns_zero_when_not_set(self) -> None:
        """Returns 0 when key doesn't exist."""
        redis = MagicMock()
        redis.get.return_value = None

        count = get_concurrent_deploy_count(redis, "tenant_1")

        assert count == 0


class TestTTLConstant:
    """Tests for TTL constant."""

    def test_ttl_is_six_hours(self) -> None:
        """TTL should be 6 hours (21600 seconds)."""
        assert CONCURRENT_DEPLOY_TTL_SECONDS == 6 * 60 * 60
        assert CONCURRENT_DEPLOY_TTL_SECONDS == 21600

