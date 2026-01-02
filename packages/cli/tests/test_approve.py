"""Tests for approve.py CLI command."""

import tempfile
from pathlib import Path

import pytest

from runtm_cli.commands.approve import (
    approve_command,
    load_requests,
    merge_connections,
    merge_env_vars,
)
from runtm_shared.manifest import Connection, EnvVar, EnvVarType


class TestLoadRequests:
    """Tests for load_requests function."""

    def test_returns_none_if_file_missing(self) -> None:
        """Should return None if runtm.requests.yaml doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            result = load_requests(path)
            assert result is None

    def test_loads_valid_requests_file(self) -> None:
        """Should load and parse valid requests file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.requests.yaml").write_text("""
requested:
  env_vars:
    - name: API_KEY
      type: string
      secret: true
      required: false
      reason: "Needed for external API"
  egress_allowlist:
    - "api.example.com"
notes:
  - "This is a test note"
""")

            result = load_requests(path)

            assert result is not None
            assert len(result.requested.env_vars) == 1
            assert result.requested.env_vars[0].name == "API_KEY"
            assert result.requested.env_vars[0].secret is True
            assert len(result.requested.egress_allowlist) == 1
            assert result.requested.egress_allowlist[0] == "api.example.com"
            assert len(result.notes) == 1

    def test_handles_invalid_yaml(self) -> None:
        """Should return None for invalid YAML."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.requests.yaml").write_text("invalid: yaml: content:")

            result = load_requests(path)
            assert result is None


class TestMergeEnvVars:
    """Tests for merge_env_vars function."""

    def test_adds_new_env_vars(self) -> None:
        """Should add new env vars to existing list."""
        existing = [
            EnvVar(name="EXISTING_VAR", type=EnvVarType.STRING),
        ]
        requested = [
            EnvVar(name="NEW_VAR", type=EnvVarType.STRING, required=True),
        ]

        merged, added = merge_env_vars(existing, requested)

        assert len(merged) == 2
        assert "NEW_VAR" in added
        assert any(ev.name == "EXISTING_VAR" for ev in merged)
        assert any(ev.name == "NEW_VAR" for ev in merged)

    def test_skips_existing_env_vars(self) -> None:
        """Should not duplicate existing env vars."""
        existing = [
            EnvVar(name="SHARED_VAR", type=EnvVarType.STRING),
        ]
        requested = [
            EnvVar(name="SHARED_VAR", type=EnvVarType.STRING, required=True),
        ]

        merged, added = merge_env_vars(existing, requested)

        assert len(merged) == 1
        assert added == []

    def test_handles_empty_existing(self) -> None:
        """Should handle empty existing list."""
        existing: list[EnvVar] = []
        requested = [
            EnvVar(name="NEW_VAR", type=EnvVarType.STRING),
        ]

        merged, added = merge_env_vars(existing, requested)

        assert len(merged) == 1
        assert "NEW_VAR" in added

    def test_handles_empty_requested(self) -> None:
        """Should handle empty requested list."""
        existing = [
            EnvVar(name="EXISTING_VAR", type=EnvVarType.STRING),
        ]
        requested: list[EnvVar] = []

        merged, added = merge_env_vars(existing, requested)

        assert len(merged) == 1
        assert added == []


class TestMergeConnections:
    """Tests for merge_connections function."""

    def test_adds_new_connections(self) -> None:
        """Should add new connections to existing list."""
        existing = [
            Connection(name="supabase", env_vars=["SUPABASE_URL"]),
        ]
        requested = [
            Connection(name="stripe", env_vars=["STRIPE_KEY"]),
        ]

        merged, added = merge_connections(existing, requested)

        assert len(merged) == 2
        assert "stripe" in added
        assert any(c.name == "supabase" for c in merged)
        assert any(c.name == "stripe" for c in merged)

    def test_skips_existing_connections(self) -> None:
        """Should not duplicate existing connections."""
        existing = [
            Connection(name="supabase", env_vars=["SUPABASE_URL"]),
        ]
        requested = [
            Connection(name="supabase", env_vars=["SUPABASE_URL", "SUPABASE_KEY"]),
        ]

        merged, added = merge_connections(existing, requested)

        assert len(merged) == 1
        assert added == []

    def test_handles_empty_existing(self) -> None:
        """Should handle empty existing list."""
        existing: list[Connection] = []
        requested = [
            Connection(name="stripe", env_vars=["STRIPE_KEY"]),
        ]

        merged, added = merge_connections(existing, requested)

        assert len(merged) == 1
        assert "stripe" in added

    def test_handles_empty_requested(self) -> None:
        """Should handle empty requested list."""
        existing = [
            Connection(name="supabase", env_vars=["SUPABASE_URL"]),
        ]
        requested: list[Connection] = []

        merged, added = merge_connections(existing, requested)

        assert len(merged) == 1
        assert added == []


class TestApproveCommand:
    """Tests for approve_command function."""

    def test_fails_without_manifest(self) -> None:
        """Should fail if no runtm.yaml exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)

            import typer

            with pytest.raises(typer.Exit):
                approve_command(path)

    def test_handles_no_requests_file(self, capsys) -> None:
        """Should handle missing requests file gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")

            approve_command(path)

            captured = capsys.readouterr()
            assert "No runtm.requests.yaml" in captured.out

    def test_handles_empty_requests(self, capsys) -> None:
        """Should handle empty requests file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")
            (path / "runtm.requests.yaml").write_text("""
requested: {}
""")

            approve_command(path)

            captured = capsys.readouterr()
            assert "no pending requests" in captured.out

    def test_dry_run_does_not_modify(self, capsys) -> None:
        """Should not modify files in dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            manifest_content = """
name: test-service
template: backend-service
runtime: python
"""
            (path / "runtm.yaml").write_text(manifest_content)
            (path / "runtm.requests.yaml").write_text("""
requested:
  env_vars:
    - name: NEW_VAR
      type: string
      required: true
""")

            approve_command(path, dry_run=True)

            # Manifest should not be modified
            assert (path / "runtm.yaml").read_text() == manifest_content
            # Requests file should still exist
            assert (path / "runtm.requests.yaml").exists()

            captured = capsys.readouterr()
            assert "Dry run" in captured.out

    def test_merges_env_vars_into_manifest(self) -> None:
        """Should merge requested env vars into manifest."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")
            (path / "runtm.requests.yaml").write_text("""
requested:
  env_vars:
    - name: API_KEY
      type: string
      secret: true
      required: true
""")

            approve_command(path)

            # Check manifest was updated
            manifest_content = (path / "runtm.yaml").read_text()
            assert "API_KEY" in manifest_content
            assert "env_schema" in manifest_content

            # Check requests file was deleted
            assert not (path / "runtm.requests.yaml").exists()

    def test_merges_egress_allowlist(self) -> None:
        """Should merge egress allowlist into manifest policy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")
            (path / "runtm.requests.yaml").write_text("""
requested:
  egress_allowlist:
    - "api.example.com"
    - "cdn.example.com"
""")

            approve_command(path)

            manifest_content = (path / "runtm.yaml").read_text()
            assert "policy" in manifest_content
            assert "egress_allowlist" in manifest_content
            assert "api.example.com" in manifest_content
            assert "cdn.example.com" in manifest_content

    def test_merges_connections(self) -> None:
        """Should merge connections into manifest."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            # Need env_schema for connections to reference
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
env_schema:
  - name: STRIPE_KEY
    type: string
    secret: true
""")
            (path / "runtm.requests.yaml").write_text("""
requested:
  connections:
    - name: stripe
      env_vars: [STRIPE_KEY]
""")

            approve_command(path)

            manifest_content = (path / "runtm.yaml").read_text()
            assert "connections" in manifest_content
            assert "stripe" in manifest_content

    def test_skips_already_existing_items(self, capsys) -> None:
        """Should skip items that already exist in manifest."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
env_schema:
  - name: EXISTING_VAR
    type: string
""")
            (path / "runtm.requests.yaml").write_text("""
requested:
  env_vars:
    - name: EXISTING_VAR
      type: string
""")

            approve_command(path)

            captured = capsys.readouterr()
            assert "already exist" in captured.out

    def test_shows_reminder_for_secrets(self, capsys) -> None:
        """Should remind user to set secret values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "runtm.yaml").write_text("""
name: test-service
template: backend-service
runtime: python
""")
            (path / "runtm.requests.yaml").write_text("""
requested:
  env_vars:
    - name: API_SECRET
      type: string
      secret: true
      required: true
""")

            approve_command(path)

            captured = capsys.readouterr()
            assert "runtm secrets set" in captured.out
            assert "API_SECRET" in captured.out
