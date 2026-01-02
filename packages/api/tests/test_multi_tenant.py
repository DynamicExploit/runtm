"""Multi-tenant isolation and security tests.

These tests verify that:
1. Tenant A cannot access tenant B's resources
2. Filter bypass attacks are prevented
3. Write protection is enforced (tenant_id set server-side)
4. Scope enforcement works correctly
5. Returns 404 (not 403) to prevent enumeration
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from runtm_api.db.repository import (
    FORBIDDEN_FILTERS,
    TenantRepository,
)
from runtm_shared.types import ApiKeyScope, has_scope, validate_scopes


class MockSession:
    """Mock SQLAlchemy session for testing."""

    def __init__(self):
        self.items = []
        self.deleted = []
        self._query_results = []

    def query(self, model):
        return MockQuery(model, self)

    def add(self, item):
        self.items.append(item)

    def delete(self, item):
        self.deleted.append(item)

    def flush(self):
        pass

    def commit(self):
        pass


class MockQuery:
    """Mock query for testing."""

    def __init__(self, model, session):
        self.model = model
        self.session = session
        self._filters = []
        self._results = session._query_results

    def filter(self, *args):
        self._filters.extend(args)
        return self

    def first(self):
        return self._results[0] if self._results else None

    def all(self):
        return self._results


class TestTenantIsolation:
    """Tests for cross-tenant isolation."""

    def test_forbidden_filters_rejects_tenant_id(self):
        """Verify that tenant_id cannot be passed as a filter."""
        assert "tenant_id" in FORBIDDEN_FILTERS
        assert "owner_id" in FORBIDDEN_FILTERS

    def test_list_rejects_tenant_id_filter(self):
        """Verify list() raises ValueError if tenant_id is passed."""
        session = MockSession()
        session._query_results = []

        # Create a mock model class
        class MockDeployment:
            tenant_id = "test"
            id = uuid4()

        repo = TenantRepository(session, "tenant_a", MockDeployment)

        # Attempt filter bypass attack
        with pytest.raises(ValueError) as exc_info:
            repo.list(tenant_id="tenant_b")  # Should fail!

        assert "Cannot filter by" in str(exc_info.value)
        assert "tenant_id" in str(exc_info.value)

    def test_list_rejects_owner_id_filter(self):
        """Verify list() raises ValueError if owner_id is passed."""
        session = MockSession()
        session._query_results = []

        class MockDeployment:
            owner_id = "test"
            id = uuid4()

        repo = TenantRepository(session, "tenant_a", MockDeployment)

        with pytest.raises(ValueError) as exc_info:
            repo.list(owner_id="other_owner")

        assert "Cannot filter by" in str(exc_info.value)
        assert "owner_id" in str(exc_info.value)

    def test_create_ignores_tenant_id_from_input(self):
        """Verify create() sets tenant_id from auth context, ignoring input."""
        session = MockSession()

        class MockModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        repo = TenantRepository(session, "tenant_from_auth", MockModel)

        # Attacker tries to create in different tenant
        entity = repo.create(
            tenant_id="malicious_tenant",  # Should be ignored!
            name="test",
        )

        # Verify tenant_id came from auth context, not input
        assert entity.tenant_id == "tenant_from_auth"
        assert entity.name == "test"

    def test_update_cannot_change_tenant_id(self):
        """Verify update() cannot change tenant_id."""
        session = MockSession()

        class MockEntity:
            id = "123"
            tenant_id = "tenant_a"
            name = "original"

        session._query_results = [MockEntity()]

        class MockModel:
            id = "123"
            tenant_id = "tenant_a"

        repo = TenantRepository(session, "tenant_a", MockModel)

        # Try to update tenant_id
        updated = repo.update("123", tenant_id="different_tenant", name="new_name")

        # tenant_id should be unchanged
        assert updated.tenant_id == "tenant_a"
        assert updated.name == "new_name"

    def test_get_by_id_returns_none_for_wrong_tenant(self):
        """Verify get_by_id returns None (not 403) for wrong tenant."""
        session = MockSession()
        session._query_results = []  # Empty = not found in this tenant

        class MockModel:
            tenant_id = "different_tenant"
            id = uuid4()

        repo = TenantRepository(session, "tenant_a", MockModel)
        result = repo.get_by_id("some_id")

        # Should return None (404 semantics), not raise 403
        assert result is None

    def test_delete_returns_false_for_wrong_tenant(self):
        """Verify delete returns False for wrong tenant."""
        session = MockSession()
        session._query_results = []  # Not found in this tenant's scope

        class MockModel:
            tenant_id = "different_tenant"
            id = uuid4()

        repo = TenantRepository(session, "tenant_a", MockModel)
        result = repo.delete("some_id")

        assert result is False
        assert len(session.deleted) == 0


class TestScopeValidation:
    """Tests for API key scope validation."""

    def test_validate_scopes_accepts_valid_scopes(self):
        """Verify valid scopes are accepted and normalized."""
        result = validate_scopes(["read", "deploy"])
        assert result == ["deploy", "read"]  # Sorted

    def test_validate_scopes_rejects_invalid_scope(self):
        """Verify invalid scopes raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_scopes(["read", "invalid_scope"])

        assert "Invalid scopes" in str(exc_info.value)
        assert "invalid_scope" in str(exc_info.value)

    def test_validate_scopes_deduplicates(self):
        """Verify duplicate scopes are removed."""
        result = validate_scopes(["read", "read", "deploy"])
        assert result == ["deploy", "read"]

    def test_has_scope_direct_match(self):
        """Verify direct scope matches work."""
        granted = {"read", "deploy"}
        assert has_scope(granted, ApiKeyScope.READ) is True
        assert has_scope(granted, ApiKeyScope.DEPLOY) is True
        assert has_scope(granted, ApiKeyScope.DELETE) is False

    def test_has_scope_admin_includes_all(self):
        """Verify ADMIN scope includes all others."""
        granted = {"admin"}
        assert has_scope(granted, ApiKeyScope.READ) is True
        assert has_scope(granted, ApiKeyScope.DEPLOY) is True
        assert has_scope(granted, ApiKeyScope.DELETE) is True
        assert has_scope(granted, ApiKeyScope.ADMIN) is True

    def test_has_scope_deploy_includes_read(self):
        """Verify DEPLOY scope includes READ."""
        granted = {"deploy"}
        assert has_scope(granted, ApiKeyScope.READ) is True
        assert has_scope(granted, ApiKeyScope.DEPLOY) is True
        assert has_scope(granted, ApiKeyScope.DELETE) is False

    def test_has_scope_delete_includes_read(self):
        """Verify DELETE scope includes READ."""
        granted = {"delete"}
        assert has_scope(granted, ApiKeyScope.READ) is True
        assert has_scope(granted, ApiKeyScope.DELETE) is True
        assert has_scope(granted, ApiKeyScope.DEPLOY) is False

    def test_has_scope_read_only(self):
        """Verify READ-only scope is restrictive."""
        granted = {"read"}
        assert has_scope(granted, ApiKeyScope.READ) is True
        assert has_scope(granted, ApiKeyScope.DEPLOY) is False
        assert has_scope(granted, ApiKeyScope.DELETE) is False
        assert has_scope(granted, ApiKeyScope.ADMIN) is False


class TestHmacSecurity:
    """Tests for HMAC-based token security."""

    def test_hash_key_uses_hmac_not_sha256(self):
        """Verify we use HMAC-SHA256, not plain SHA256."""
        import hashlib
        import hmac as hmac_module

        # Import directly from keys module to avoid fastapi dependency
        from runtm_api.auth.keys import hash_key

        token = "runtm_test_token_123"
        pepper = "test_pepper"

        result = hash_key(token, pepper)

        # Should match HMAC-SHA256
        expected = hmac_module.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()
        assert result == expected

        # Should NOT match plain SHA256
        plain_sha256 = hashlib.sha256(token.encode()).hexdigest()
        assert result != plain_sha256

    def test_verify_key_constant_time(self):
        """Verify we use constant-time comparison."""
        from runtm_api.auth.keys import hash_key, verify_key

        token = "runtm_test_token_123"
        pepper = "test_pepper"
        correct_hash = hash_key(token, pepper)

        # This should use hmac.compare_digest internally
        result = verify_key(
            raw_token=token,
            stored_hash=correct_hash,
            stored_pepper_version=1,
            peppers={1: pepper},
        )
        assert result is True

        # Wrong token should fail
        result = verify_key(
            raw_token="runtm_wrong_token",
            stored_hash=correct_hash,
            stored_pepper_version=1,
            peppers={1: pepper},
        )
        assert result is False

    def test_verify_key_pepper_versioning(self):
        """Verify pepper version lookup works correctly."""
        from runtm_api.auth.keys import hash_key, verify_key

        token = "runtm_test_token_123"
        pepper_v1 = "pepper_version_1"
        pepper_v2 = "pepper_version_2"

        # Hash with v1 pepper
        hash_v1 = hash_key(token, pepper_v1)

        # Should work with correct version
        assert (
            verify_key(
                raw_token=token,
                stored_hash=hash_v1,
                stored_pepper_version=1,
                peppers={1: pepper_v1, 2: pepper_v2},
            )
            is True
        )

        # Should fail with wrong version (no migration window)
        assert (
            verify_key(
                raw_token=token,
                stored_hash=hash_v1,
                stored_pepper_version=2,  # Wrong version
                peppers={1: pepper_v1, 2: pepper_v2},
            )
            is False
        )

    def test_verify_key_migration_window(self):
        """Verify migration window allows both pepper versions."""
        from runtm_api.auth.keys import hash_key, verify_key

        token = "runtm_test_token_123"
        pepper_v1 = "pepper_version_1"
        pepper_v2 = "pepper_version_2"

        # Hash with v1 pepper
        hash_v1 = hash_key(token, pepper_v1)

        # During migration, should work even with wrong stored version
        # if migration_window_versions includes the correct version
        assert (
            verify_key(
                raw_token=token,
                stored_hash=hash_v1,
                stored_pepper_version=2,  # Wrong version in DB
                peppers={1: pepper_v1, 2: pepper_v2},
                migration_window_versions={1, 2},  # Try both
            )
            is True
        )


class TestTokenGeneration:
    """Tests for API token generation."""

    def test_generate_api_key_format(self):
        """Verify generated key has correct format."""
        from runtm_api.auth.keys import PREFIX_LENGTH, generate_api_key

        raw_token, prefix = generate_api_key()

        # Should start with runtm_
        assert raw_token.startswith("runtm_")

        # Prefix should be first 16 chars
        assert len(prefix) == PREFIX_LENGTH
        assert prefix == raw_token[:PREFIX_LENGTH]

        # Token should be long enough for security
        assert len(raw_token) >= 40

    def test_generate_api_key_uniqueness(self):
        """Verify generated keys are unique."""
        from runtm_api.auth.keys import generate_api_key

        keys = set()
        for _ in range(100):
            raw_token, _ = generate_api_key()
            assert raw_token not in keys
            keys.add(raw_token)

    def test_validate_token_format(self):
        """Verify token format validation."""
        from runtm_api.auth.keys import validate_token_format

        # Valid formats
        assert validate_token_format("runtm_abc123def456ghi789jkl012") is True

        # Invalid formats
        assert validate_token_format("") is False
        assert validate_token_format("invalid_token") is False
        assert validate_token_format("runtm_") is False
        assert validate_token_format("runtm_short") is False
