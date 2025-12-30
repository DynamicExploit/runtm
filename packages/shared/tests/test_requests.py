"""Tests for runtm_shared.requests - agent-proposed changes parsing."""

import tempfile
from pathlib import Path

import pytest

from runtm_shared.manifest import EnvVarType
from runtm_shared.requests import (
    RequestedChanges,
    RequestedConnection,
    RequestedEnvVar,
    RequestsFile,
)


class TestRequestedEnvVar:
    """Tests for RequestedEnvVar model."""

    def test_valid_requested_env_var(self) -> None:
        """Should create valid requested env var."""
        env_var = RequestedEnvVar(
            name="API_KEY",
            type=EnvVarType.STRING,
            required=True,
            secret=True,
            reason="Needed for external API calls",
        )
        assert env_var.name == "API_KEY"
        assert env_var.secret is True
        assert env_var.reason == "Needed for external API calls"

    def test_env_var_name_validation(self) -> None:
        """Should validate env var name format."""
        # Valid names
        RequestedEnvVar(name="MY_VAR")
        RequestedEnvVar(name="API_KEY_123")

        # Invalid: empty name
        with pytest.raises(ValueError, match="cannot be empty"):
            RequestedEnvVar(name="")

        # Invalid: starts with number
        with pytest.raises(ValueError, match="must start with a letter"):
            RequestedEnvVar(name="123_VAR")

        # Invalid: contains invalid characters
        with pytest.raises(ValueError, match="alphanumeric with underscores"):
            RequestedEnvVar(name="MY-VAR")

    def test_to_env_var_conversion(self) -> None:
        """Should convert to manifest EnvVar (drops reason)."""
        requested = RequestedEnvVar(
            name="DATABASE_URL",
            type=EnvVarType.URL,
            required=True,
            secret=True,
            description="Database connection string",
            reason="Needed for persistence",
        )
        env_var = requested.to_env_var()

        assert env_var.name == "DATABASE_URL"
        assert env_var.type == EnvVarType.URL
        assert env_var.required is True
        assert env_var.secret is True
        assert env_var.description == "Database connection string"
        # Reason should not be in EnvVar
        assert not hasattr(env_var, "reason") or env_var.model_dump().get("reason") is None


class TestRequestedConnection:
    """Tests for RequestedConnection model."""

    def test_valid_requested_connection(self) -> None:
        """Should create valid requested connection."""
        conn = RequestedConnection(
            name="Supabase",
            env_vars=["SUPABASE_URL", "SUPABASE_ANON_KEY"],
            reason="Needed for database and auth",
        )
        # Name should be lowercased
        assert conn.name == "supabase"
        assert len(conn.env_vars) == 2
        assert conn.reason == "Needed for database and auth"

    def test_connection_name_validation(self) -> None:
        """Should validate connection name format."""
        # Valid names
        RequestedConnection(name="my-conn", env_vars=["VAR"])
        RequestedConnection(name="MyConn", env_vars=["VAR"])  # Gets lowercased

        # Invalid: empty name
        with pytest.raises(ValueError, match="cannot be empty"):
            RequestedConnection(name="", env_vars=["VAR"])


class TestRequestedChanges:
    """Tests for RequestedChanges model."""

    def test_empty_requested_changes(self) -> None:
        """Should create empty requested changes."""
        changes = RequestedChanges()
        assert changes.env_vars == []
        assert changes.egress_allowlist == []
        assert changes.connections == []

    def test_full_requested_changes(self) -> None:
        """Should create requested changes with all fields."""
        changes = RequestedChanges(
            env_vars=[
                RequestedEnvVar(name="API_KEY", secret=True),
            ],
            egress_allowlist=["api.example.com"],
            connections=[
                RequestedConnection(name="external", env_vars=["API_KEY"]),
            ],
        )
        assert len(changes.env_vars) == 1
        assert len(changes.egress_allowlist) == 1
        assert len(changes.connections) == 1


class TestRequestsFile:
    """Tests for RequestsFile model."""

    def test_from_yaml_minimal(self) -> None:
        """Should parse minimal requests file."""
        yaml_content = """
requested: {}
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert requests.is_empty()

    def test_from_yaml_with_env_vars(self) -> None:
        """Should parse requests file with env vars."""
        yaml_content = """
requested:
  env_vars:
    - name: API_KEY
      type: string
      secret: true
      required: false
      reason: "Optional API for enhanced features"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert len(requests.requested.env_vars) == 1
        assert requests.requested.env_vars[0].name == "API_KEY"
        assert requests.requested.env_vars[0].secret is True
        assert requests.requested.env_vars[0].reason == "Optional API for enhanced features"

    def test_from_yaml_with_egress_allowlist(self) -> None:
        """Should parse requests file with egress allowlist."""
        yaml_content = """
requested:
  egress_allowlist:
    - "api.example.com"
    - "cdn.example.com"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert len(requests.requested.egress_allowlist) == 2
        assert "api.example.com" in requests.requested.egress_allowlist

    def test_from_yaml_with_connections(self) -> None:
        """Should parse requests file with connections."""
        yaml_content = """
requested:
  connections:
    - name: stripe
      env_vars: [STRIPE_KEY, STRIPE_SECRET]
      reason: "Payment processing"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert len(requests.requested.connections) == 1
        assert requests.requested.connections[0].name == "stripe"
        assert len(requests.requested.connections[0].env_vars) == 2

    def test_from_yaml_with_notes(self) -> None:
        """Should parse requests file with notes."""
        yaml_content = """
requested: {}
notes:
  - "Default implementation uses scraping"
  - "API is more reliable but requires key"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert len(requests.notes) == 2
        assert "scraping" in requests.notes[0]

    def test_from_yaml_full_example(self) -> None:
        """Should parse full requests file."""
        yaml_content = """
requested:
  env_vars:
    - name: ALPHAVANTAGE_API_KEY
      type: string
      secret: true
      required: false
      reason: "Optional API for stock data"
  egress_allowlist:
    - "api.alphavantage.co"
  connections:
    - name: alpha_vantage
      env_vars: [ALPHAVANTAGE_API_KEY]
notes:
  - "Default impl scrapes Yahoo; API is more stable"
"""
        requests = RequestsFile.from_yaml(yaml_content)
        assert len(requests.requested.env_vars) == 1
        assert len(requests.requested.egress_allowlist) == 1
        assert len(requests.requested.connections) == 1
        assert len(requests.notes) == 1

    def test_from_file(self) -> None:
        """Should parse requests from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtm.requests.yaml"
            path.write_text("""
requested:
  env_vars:
    - name: TEST_VAR
      type: string
""")
            requests = RequestsFile.from_file(path)
            assert len(requests.requested.env_vars) == 1
            assert requests.requested.env_vars[0].name == "TEST_VAR"

    def test_from_file_not_found(self) -> None:
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            RequestsFile.from_file(Path("/nonexistent/path.yaml"))

    def test_invalid_yaml(self) -> None:
        """Should raise ValueError for invalid YAML."""
        with pytest.raises(ValueError, match="Invalid YAML"):
            RequestsFile.from_yaml("invalid: yaml: content:")

    def test_invalid_structure(self) -> None:
        """Should raise ValueError for non-dict YAML."""
        with pytest.raises(ValueError, match="must be a YAML dictionary"):
            RequestsFile.from_yaml("just a string")


class TestRequestsFileHelpers:
    """Tests for RequestsFile helper methods."""

    def test_is_empty_true(self) -> None:
        """Should return True when no pending requests."""
        requests = RequestsFile()
        assert requests.is_empty()

        requests = RequestsFile(requested=RequestedChanges())
        assert requests.is_empty()

    def test_is_empty_false_with_env_vars(self) -> None:
        """Should return False when env vars requested."""
        requests = RequestsFile(
            requested=RequestedChanges(
                env_vars=[RequestedEnvVar(name="VAR")]
            )
        )
        assert not requests.is_empty()

    def test_is_empty_false_with_egress(self) -> None:
        """Should return False when egress requested."""
        requests = RequestsFile(
            requested=RequestedChanges(
                egress_allowlist=["example.com"]
            )
        )
        assert not requests.is_empty()

    def test_is_empty_false_with_connections(self) -> None:
        """Should return False when connections requested."""
        requests = RequestsFile(
            requested=RequestedChanges(
                connections=[RequestedConnection(name="conn", env_vars=["VAR"])]
            )
        )
        assert not requests.is_empty()

    def test_get_summary_empty(self) -> None:
        """Should return 'No pending requests' when empty."""
        requests = RequestsFile()
        assert requests.get_summary() == "No pending requests"

    def test_get_summary_with_items(self) -> None:
        """Should return summary of pending items."""
        requests = RequestsFile(
            requested=RequestedChanges(
                env_vars=[RequestedEnvVar(name="VAR1"), RequestedEnvVar(name="VAR2")],
                egress_allowlist=["example.com"],
                connections=[RequestedConnection(name="conn", env_vars=["VAR1"])],
            )
        )
        summary = requests.get_summary()
        assert "2 env vars" in summary
        assert "1 egress" in summary
        assert "1 connection" in summary


class TestRequestsFileSerialization:
    """Tests for RequestsFile serialization."""

    def test_to_yaml(self) -> None:
        """Should serialize to YAML."""
        requests = RequestsFile(
            requested=RequestedChanges(
                env_vars=[
                    RequestedEnvVar(
                        name="API_KEY",
                        secret=True,
                        reason="For external API",
                    )
                ],
            ),
            notes=["Test note"],
        )
        yaml_output = requests.to_yaml()
        assert "API_KEY" in yaml_output
        assert "secret: true" in yaml_output
        assert "Test note" in yaml_output

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        requests = RequestsFile(
            requested=RequestedChanges(
                env_vars=[RequestedEnvVar(name="VAR")]
            )
        )
        d = requests.to_dict()
        assert "requested" in d
        assert "env_vars" in d["requested"]
        assert d["requested"]["env_vars"][0]["name"] == "VAR"

    def test_roundtrip(self) -> None:
        """Should survive YAML roundtrip."""
        original = RequestsFile(
            requested=RequestedChanges(
                env_vars=[
                    RequestedEnvVar(
                        name="DATABASE_URL",
                        type=EnvVarType.URL,
                        required=True,
                        secret=True,
                        description="DB connection",
                        reason="For persistence",
                    )
                ],
                egress_allowlist=["db.example.com"],
            ),
            notes=["Important note"],
        )
        yaml_str = original.to_yaml()
        parsed = RequestsFile.from_yaml(yaml_str)

        assert len(parsed.requested.env_vars) == 1
        assert parsed.requested.env_vars[0].name == "DATABASE_URL"
        assert parsed.requested.env_vars[0].secret is True
        assert len(parsed.requested.egress_allowlist) == 1
        assert len(parsed.notes) == 1

