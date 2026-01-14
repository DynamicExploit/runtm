"""Secure token storage for Runtm CLI.

Token resolution order:
1. RUNTM_API_KEY environment variable (CI/headless)
2. ~/.runtm/credentials file (0o600 permissions) - default, no popups
3. OS keychain via keyring library (opt-in, future --secure flag)

Design notes:
- Token is NEVER stored in config.yaml
- File-first to avoid scary "Python wants keychain access" popups on macOS
- Host-keyed storage (api_token@{host}) for future multi-profile support
- File created with os.open(..., 0o600) to handle weird umasks
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from urllib.parse import urlparse

# Lazy import keyring to handle cases where it's not installed
# This prevents CLI crashes on startup when keyring is missing
_keyring = None
_keyring_available: bool | None = None


def _get_keyring():
    """Lazy load keyring module.

    Returns:
        keyring module or None if not available
    """
    global _keyring, _keyring_available

    if _keyring_available is None:
        try:
            import keyring

            _keyring = keyring
            _keyring_available = True
        except ImportError:
            _keyring_available = False

    return _keyring


SERVICE_NAME = "runtm"
CREDENTIALS_FILE = Path.home() / ".runtm" / "credentials"


def _get_api_url() -> str:
    """Get api_url from config (lazy import to avoid circular deps)."""
    from runtm_cli.config import get_api_url

    return get_api_url()


def _keyring_key(api_url: str) -> str:
    """Generate keyring key from api_url for future multi-profile support.

    Args:
        api_url: The API URL to generate a key for

    Returns:
        Key in format "api_token@{host}" (e.g., "api_token@app.runtm.com")
    """
    host = urlparse(api_url).netloc or "default"
    return f"api_token@{host}"


def get_token(api_url: str | None = None) -> str | None:
    """Get token: env var -> file -> keychain.

    Args:
        api_url: Optional API URL to get token for. Defaults to config api_url.

    Returns:
        Token string if found, None otherwise.
    """
    # 1. Environment variable (highest priority, CI-friendly)
    if env_token := os.environ.get("RUNTM_API_KEY"):
        return env_token

    # 2. Credentials file (default - no scary popups)
    if CREDENTIALS_FILE.exists():
        try:
            if token := CREDENTIALS_FILE.read_text().strip():
                return token
        except Exception:
            pass  # File read error

    # 3. OS keychain (fallback for users who stored there previously)
    keyring = _get_keyring()
    if keyring is not None:
        api_url = api_url or _get_api_url()
        key = _keyring_key(api_url)
        try:
            if token := keyring.get_password(SERVICE_NAME, key):
                return token
        except Exception:
            # Handle KeyringError and any other exceptions
            # Keyring unavailable or backend misconfigured (common on Linux without SecretService)
            pass

    return None


def get_token_source(api_url: str | None = None) -> str:
    """Return which storage has the active token.

    Args:
        api_url: Optional API URL to check. Defaults to config api_url.

    Returns:
        One of: 'env' | 'file' | 'keychain' | 'none'
    """
    if os.environ.get("RUNTM_API_KEY"):
        return "env"

    # Check file first (default storage)
    if CREDENTIALS_FILE.exists():
        try:
            if CREDENTIALS_FILE.read_text().strip():
                return "file"
        except Exception:
            pass

    # Then keychain (for users who stored there previously)
    keyring = _get_keyring()
    if keyring is not None:
        api_url = api_url or _get_api_url()
        key = _keyring_key(api_url)
        try:
            if keyring.get_password(SERVICE_NAME, key):
                return "keychain"
        except Exception:
            pass

    return "none"


def get_keyring_key(api_url: str | None = None) -> str:
    """Get the keyring key name for display purposes.

    Args:
        api_url: Optional API URL. Defaults to config api_url.

    Returns:
        The keyring key name (e.g., "api_token@app.runtm.com")
    """
    api_url = api_url or _get_api_url()
    return _keyring_key(api_url)


def set_token(token: str, api_url: str | None = None) -> str:
    """Store token in file with 0o600 permissions (default, no popups).

    Args:
        token: The token to store
        api_url: Optional API URL (unused for now, reserved for future multi-profile)

    Returns:
        Storage method used: 'file'
    """
    # Always use file - no scary keychain popups
    # Keychain storage can be added later as opt-in --secure flag
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Create file with 0o600 from the start (not chmod after)
    # This handles weird umasks correctly
    fd = os.open(CREDENTIALS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(token)
    except Exception:
        # If fdopen fails, close the fd manually
        with contextlib.suppress(Exception):
            os.close(fd)
        raise
    return "file"


def clear_token(api_url: str | None = None) -> None:
    """Remove token from both keychain and file.

    Args:
        api_url: Optional API URL to clear token for. Defaults to config api_url.
    """
    # Try to remove from keychain
    keyring = _get_keyring()
    if keyring is not None:
        api_url = api_url or _get_api_url()
        key = _keyring_key(api_url)
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except Exception:
            pass  # Ignore errors - token might not exist or keyring unavailable

    # Also remove credentials file if it exists
    if CREDENTIALS_FILE.exists():
        try:
            CREDENTIALS_FILE.unlink()
        except Exception:
            pass  # Ignore errors


def check_credentials_permissions() -> tuple[bool, str]:
    """Check if credentials file has secure permissions.

    Returns:
        Tuple of (is_ok, message).
        - If file doesn't exist: (True, "No credentials file")
        - If permissions are 0o600: (True, "~/.runtm/credentials (0o600)")
        - If permissions are wrong: (False, warning message with fix command)
    """
    if not CREDENTIALS_FILE.exists():
        return True, "No credentials file"

    try:
        mode = CREDENTIALS_FILE.stat().st_mode & 0o777
        if mode == 0o600:
            return True, "~/.runtm/credentials (0o600)"
        else:
            return (
                False,
                f"⚠️  ~/.runtm/credentials has mode {oct(mode)} - "
                f"run: chmod 600 ~/.runtm/credentials",
            )
    except Exception as e:
        return False, f"⚠️  Could not check credentials file: {e}"
