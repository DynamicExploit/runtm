"""Fly.io secrets provider implementation.

Uses flyctl CLI to manage secrets. Secret values are passed directly
to Fly and never stored in the Runtm database.
"""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Optional

from .secrets_base import SecretListResult, SecretSetResult, SecretsProvider


class FlySecretsProvider(SecretsProvider):
    """Fly.io secrets provider using flyctl CLI.

    Manages secrets via `fly secrets` commands. Requires flyctl to be
    installed and FLY_API_TOKEN to be set.

    Security notes:
        - Secret values are passed to flyctl via stdin (not command line args)
        - Values are never logged or persisted locally
        - Only secret names are returned from list operations
    """

    def __init__(self, api_token: Optional[str] = None):
        """Initialize Fly secrets provider.

        Args:
            api_token: Fly.io API token (defaults to FLY_API_TOKEN env var)
        """
        self.api_token = api_token or os.environ.get("FLY_API_TOKEN")

    @property
    def name(self) -> str:
        return "fly"

    def _get_env(self) -> Dict[str, str]:
        """Get environment with FLY_API_TOKEN set."""
        env = os.environ.copy()
        if self.api_token:
            env["FLY_API_TOKEN"] = self.api_token
        return env

    def set_secrets(
        self,
        app_name: str,
        secrets: Dict[str, str],
        stage: bool = False,
    ) -> SecretSetResult:
        """Set secrets for a Fly app.

        Uses `fly secrets set` with values passed via stdin to avoid
        exposing them in process listings or logs.

        Args:
            app_name: Fly app name
            secrets: Key-value pairs to set
            stage: If True, stage secrets without releasing (--stage flag)

        Returns:
            SecretSetResult with success/error status
        """
        if not secrets:
            return SecretSetResult(success=True, secrets_set=0)

        if not self.api_token:
            return SecretSetResult(
                success=False,
                error="FLY_API_TOKEN not configured",
            )

        try:
            # Build secrets as KEY=VALUE pairs for stdin
            # Using stdin avoids exposing values in process args
            secrets_input = "\n".join(f"{k}={v}" for k, v in secrets.items())

            # Build command - use --stage to avoid immediate release
            cmd = ["fly", "secrets", "import", "-a", app_name]
            if stage:
                cmd.append("--stage")

            # Use fly secrets import which reads from stdin
            result = subprocess.run(
                cmd,
                input=secrets_input,
                capture_output=True,
                text=True,
                timeout=60,
                env=self._get_env(),
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return SecretSetResult(
                    success=False,
                    error=f"Failed to set secrets: {error_msg}",
                )

            return SecretSetResult(
                success=True,
                secrets_set=len(secrets),
            )

        except subprocess.TimeoutExpired:
            return SecretSetResult(
                success=False,
                error="Timeout setting secrets (60s)",
            )
        except FileNotFoundError:
            return SecretSetResult(
                success=False,
                error="flyctl not installed. Install from https://fly.io/docs/flyctl/",
            )
        except Exception as e:
            return SecretSetResult(
                success=False,
                error=f"Error setting secrets: {str(e)}",
            )

    def get_secret_names(self, app_name: str) -> SecretListResult:
        """List secret names (not values) for a Fly app.

        Uses `fly secrets list` and parses output for names only.

        Args:
            app_name: Fly app name

        Returns:
            SecretListResult with list of secret names
        """
        if not self.api_token:
            return SecretListResult(
                success=False,
                error="FLY_API_TOKEN not configured",
            )

        try:
            result = subprocess.run(
                ["fly", "secrets", "list", "-a", app_name, "--json"],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._get_env(),
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                # "No secrets" is not an error
                if "no secrets" in error_msg.lower():
                    return SecretListResult(success=True, names=[])
                return SecretListResult(
                    success=False,
                    error=f"Failed to list secrets: {error_msg}",
                )

            # Parse JSON output
            import json

            try:
                secrets_data = json.loads(result.stdout)
                # Extract just the names, never the values
                names = [s.get("Name", s.get("name", "")) for s in secrets_data]
                names = [n for n in names if n]  # Filter empty
                return SecretListResult(success=True, names=names)
            except json.JSONDecodeError:
                # Fallback: parse text output (one name per line)
                lines = result.stdout.strip().split("\n")
                # Skip header line if present
                names = []
                for line in lines:
                    if line and not line.startswith("NAME") and not line.startswith("-"):
                        # First column is the name
                        name = line.split()[0] if line.split() else ""
                        if name:
                            names.append(name)
                return SecretListResult(success=True, names=names)

        except subprocess.TimeoutExpired:
            return SecretListResult(
                success=False,
                error="Timeout listing secrets (30s)",
            )
        except FileNotFoundError:
            return SecretListResult(
                success=False,
                error="flyctl not installed",
            )
        except Exception as e:
            return SecretListResult(
                success=False,
                error=f"Error listing secrets: {str(e)}",
            )

    def delete_secrets(
        self,
        app_name: str,
        names: List[str],
    ) -> SecretSetResult:
        """Remove secrets from a Fly app.

        Uses `fly secrets unset` to remove specified secrets.

        Args:
            app_name: Fly app name
            names: Secret names to delete

        Returns:
            SecretSetResult with success/error status
        """
        if not names:
            return SecretSetResult(success=True, secrets_set=0)

        if not self.api_token:
            return SecretSetResult(
                success=False,
                error="FLY_API_TOKEN not configured",
            )

        try:
            result = subprocess.run(
                ["fly", "secrets", "unset", "-a", app_name] + names,
                capture_output=True,
                text=True,
                timeout=60,
                env=self._get_env(),
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return SecretSetResult(
                    success=False,
                    error=f"Failed to delete secrets: {error_msg}",
                )

            return SecretSetResult(
                success=True,
                secrets_set=len(names),
            )

        except subprocess.TimeoutExpired:
            return SecretSetResult(
                success=False,
                error="Timeout deleting secrets (60s)",
            )
        except FileNotFoundError:
            return SecretSetResult(
                success=False,
                error="flyctl not installed",
            )
        except Exception as e:
            return SecretSetResult(
                success=False,
                error=f"Error deleting secrets: {str(e)}",
            )
