"""Tests for feature requests in runtm.requests.yaml."""

import pytest

from runtm_shared.requests import (
    RequestedChanges,
    RequestedFeatures,
    RequestsFile,
)


class TestRequestedFeatures:
    """Test RequestedFeatures model."""

    def test_default_no_changes(self):
        """Default features have no changes."""
        features = RequestedFeatures()
        assert features.database is None
        assert features.auth is None
        assert not features.has_changes()

    def test_request_database(self):
        """Can request database feature."""
        features = RequestedFeatures(database=True)
        assert features.database is True
        assert features.has_changes()

    def test_request_auth(self):
        """Can request auth feature."""
        features = RequestedFeatures(auth=True)
        assert features.auth is True
        assert features.has_changes()

    def test_request_both_features(self):
        """Can request both features."""
        features = RequestedFeatures(database=True, auth=True, reason="Need user accounts")
        assert features.database is True
        assert features.auth is True
        assert features.reason == "Need user accounts"
        assert features.has_changes()

    def test_request_disable_feature(self):
        """Can request to disable a feature."""
        features = RequestedFeatures(database=False)
        assert features.database is False
        assert features.has_changes()


class TestRequestedChangesWithFeatures:
    """Test RequestedChanges with features."""

    def test_changes_with_features(self):
        """RequestedChanges includes features."""
        changes = RequestedChanges(
            features=RequestedFeatures(database=True),
        )
        assert changes.features is not None
        assert changes.features.database is True

    def test_changes_empty_without_features(self):
        """Empty changes has no features."""
        changes = RequestedChanges()
        assert changes.features is None


class TestRequestsFileWithFeatures:
    """Test RequestsFile with features."""

    def test_parse_features_from_yaml(self):
        """Can parse features from YAML."""
        yaml_content = """
requested:
  features:
    database: true
    auth: true
    reason: "App needs user data storage"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert requests.requested.features is not None
        assert requests.requested.features.database is True
        assert requests.requested.features.auth is True
        assert requests.requested.features.reason == "App needs user data storage"

    def test_parse_database_only(self):
        """Can parse database feature only."""
        yaml_content = """
requested:
  features:
    database: true
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert requests.requested.features.database is True
        assert requests.requested.features.auth is None

    def test_is_empty_false_with_features(self):
        """is_empty returns False when features requested."""
        yaml_content = """
requested:
  features:
    database: true
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert not requests.is_empty()

    def test_get_summary_includes_features(self):
        """Summary includes features."""
        yaml_content = """
requested:
  features:
    database: true
    auth: true
"""
        requests = RequestsFile.from_yaml(yaml_content)
        summary = requests.get_summary()
        assert "database" in summary
        assert "auth" in summary

    def test_to_dict_includes_features(self):
        """to_dict includes features."""
        yaml_content = """
requested:
  features:
    database: true
    reason: "Need storage"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        data = requests.to_dict()
        assert "features" in data["requested"]
        assert data["requested"]["features"]["database"] is True
        assert data["requested"]["features"]["reason"] == "Need storage"

    def test_roundtrip_with_features(self):
        """YAML roundtrip preserves features."""
        yaml_content = """
requested:
  features:
    database: true
    auth: true
    reason: "Full stack app needs both"
  env_vars:
    - name: AUTH_SECRET
      type: string
      secret: true
      required: true
      reason: "Required for auth"
notes:
  - "This enables user management"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        yaml_out = requests.to_yaml()
        requests2 = RequestsFile.from_yaml(yaml_out)

        assert requests2.requested.features.database is True
        assert requests2.requested.features.auth is True
        assert len(requests2.requested.env_vars) == 1
        assert requests2.requested.env_vars[0].name == "AUTH_SECRET"


class TestRequestsFileFullExample:
    """Full example of feature requests."""

    def test_full_auth_request(self):
        """Complete auth feature request with all requirements."""
        yaml_content = """
requested:
  features:
    database: true
    auth: true
    reason: "Building a SaaS dashboard with user accounts"
  env_vars:
    - name: AUTH_SECRET
      type: string
      secret: true
      required: true
      reason: "Required for Better Auth session signing"
    - name: GOOGLE_CLIENT_ID
      type: string
      required: false
      reason: "Optional Google OAuth"
    - name: GOOGLE_CLIENT_SECRET
      type: string
      secret: true
      required: false
      reason: "Optional Google OAuth"
notes:
  - "Agent is adding user authentication"
  - "Social login is optional but recommended"
"""
        requests = RequestsFile.from_yaml(yaml_content)

        # Features
        assert requests.requested.features.database is True
        assert requests.requested.features.auth is True

        # Env vars
        assert len(requests.requested.env_vars) == 3
        auth_secret = next(ev for ev in requests.requested.env_vars if ev.name == "AUTH_SECRET")
        assert auth_secret.secret is True
        assert auth_secret.required is True

        # Summary
        summary = requests.get_summary()
        assert "database" in summary
        assert "auth" in summary
        assert "3 env vars" in summary

