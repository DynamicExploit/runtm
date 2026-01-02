"""API key generation and verification with versioned HMAC.

This module provides secure API key handling with:
- HMAC-SHA256 hashing with server-side pepper (not plain SHA256)
- Versioned peppers for rotation without breaking existing keys
- 16-character prefix for near-O(1) database lookup
- Constant-time comparison to prevent timing attacks

Pepper Rotation Workflow:
1. Add TOKEN_PEPPER_V2 to environment
2. Update CURRENT_PEPPER_VERSION to 2 for new keys
3. Set PEPPER_MIGRATION_VERSIONS="1,2" during transition
4. Verification tries stored version first, then migration window versions
5. After all keys rotated: remove TOKEN_PEPPER_V1, clear migration versions
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

# Prefix length: 16 chars reduces collisions, makes lookup near-O(1)
# Format: "runtm_" (6 chars) + 10 chars of token = 16 chars total
PREFIX_LENGTH = 16


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key.

    The raw key is shown to the user exactly once at creation.
    Only the prefix and hash are stored in the database.

    Returns:
        Tuple of (raw_token, prefix):
        - raw_token: Full key like "runtm_abc123..." (shown once, never stored)
        - prefix: First 16 chars for database lookup
    """
    # Generate secure random token with runtm_ prefix
    random_part = secrets.token_urlsafe(32)
    raw_token = f"runtm_{random_part}"
    prefix = raw_token[:PREFIX_LENGTH]
    return raw_token, prefix


def hash_key(raw_token: str, pepper: str) -> str:
    """HMAC-SHA256 hash with server pepper.

    Uses HMAC instead of plain SHA256 for:
    - Resistance to offline brute-force if database leaks
    - Ability to rotate pepper without rehashing all keys

    Args:
        raw_token: The raw API key from user
        pepper: Server-side secret (from environment/KMS)

    Returns:
        Hex-encoded HMAC-SHA256 hash (64 characters)
    """
    return hmac.new(
        pepper.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_key(
    raw_token: str,
    stored_hash: str,
    stored_pepper_version: int,
    peppers: dict[int, str],
    migration_window_versions: Optional[set[int]] = None,
) -> bool:
    """Verify an API key with pepper versioning support.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        raw_token: The raw API key from the request
        stored_hash: Hash stored in database for this key
        stored_pepper_version: Pepper version used when key was created
        peppers: Map of version number -> pepper value
        migration_window_versions: Optional set of versions to try during rotation

    Returns:
        True if key is valid, False otherwise

    Security Notes:
        - Always tries stored version first (most common case)
        - Migration window allows rotation without breaking existing keys
        - Uses hmac.compare_digest for constant-time comparison
    """
    # Try stored version first (most common case, best performance)
    if stored_pepper_version in peppers:
        computed = hash_key(raw_token, peppers[stored_pepper_version])
        if hmac.compare_digest(computed, stored_hash):
            return True

    # During migration window, try other versions
    # This handles the case where a key's pepper_version doesn't match
    # the actual pepper used (shouldn't happen, but defensive)
    if migration_window_versions:
        for version in migration_window_versions:
            if version != stored_pepper_version and version in peppers:
                computed = hash_key(raw_token, peppers[version])
                if hmac.compare_digest(computed, stored_hash):
                    return True

    return False


def validate_token_format(token: str) -> bool:
    """Validate that a token has the expected format.

    Args:
        token: Token string to validate

    Returns:
        True if token format is valid (starts with "runtm_" and has sufficient length)
    """
    if not token:
        return False
    if not token.startswith("runtm_"):
        return False
    # Minimum length: "runtm_" (6) + some random chars
    if len(token) < 20:
        return False
    return True
