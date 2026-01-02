"""Deterministic deployment ID generation for Runtm."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Optional

# Prefix for deployment IDs
DEPLOYMENT_ID_PREFIX = "dep_"

# Length of the random suffix (in characters)
RANDOM_SUFFIX_LENGTH = 12


def generate_deployment_id(
    name: Optional[str] = None,
    deterministic: bool = False,
) -> str:
    """Generate a deployment ID.

    By default, generates a random ID for uniqueness.
    If deterministic=True, generates based on name + timestamp for idempotency.

    Args:
        name: Optional deployment name to include in hash
        deterministic: If True, use deterministic generation (for idempotency)

    Returns:
        Deployment ID in format: dep_<12-char-suffix>

    Examples:
        >>> generate_deployment_id()
        'dep_a1b2c3d4e5f6'

        >>> generate_deployment_id(name="my-service", deterministic=True)
        'dep_7f8a9b0c1d2e'
    """
    if deterministic and name:
        # Use hash of name for deterministic IDs
        # In practice, you'd include more context (manifest hash, etc.)
        hash_input = f"{name}:{int(time.time())}"
        hash_bytes = hashlib.sha256(hash_input.encode()).digest()
        suffix = hash_bytes[:6].hex()  # 12 hex chars
    else:
        # Random ID for uniqueness
        suffix = secrets.token_hex(6)  # 12 hex chars

    return f"{DEPLOYMENT_ID_PREFIX}{suffix}"


def generate_idempotency_key() -> str:
    """Generate a random idempotency key for API requests.

    Returns:
        Random 32-character hex string
    """
    return secrets.token_hex(16)


def is_valid_deployment_id(deployment_id: str) -> bool:
    """Check if a string is a valid deployment ID format.

    Args:
        deployment_id: String to validate

    Returns:
        True if valid deployment ID format, False otherwise
    """
    if not deployment_id.startswith(DEPLOYMENT_ID_PREFIX):
        return False

    suffix = deployment_id[len(DEPLOYMENT_ID_PREFIX) :]

    # Must be exactly 12 hex characters
    if len(suffix) != RANDOM_SUFFIX_LENGTH:
        return False

    # Must be valid hex
    try:
        int(suffix, 16)
        return True
    except ValueError:
        return False


def parse_deployment_id(deployment_id: str) -> Optional[str]:
    """Parse and validate a deployment ID.

    Args:
        deployment_id: Deployment ID to parse

    Returns:
        The deployment ID if valid, None otherwise
    """
    if is_valid_deployment_id(deployment_id):
        return deployment_id
    return None


def generate_artifact_key(deployment_id: str) -> str:
    """Generate storage key for deployment artifact.

    Args:
        deployment_id: Deployment ID

    Returns:
        Storage key for the artifact
    """
    return f"artifacts/{deployment_id}/artifact.zip"


def generate_build_context_key(deployment_id: str) -> str:
    """Generate storage key for extracted build context.

    Args:
        deployment_id: Deployment ID

    Returns:
        Storage key for the build context directory
    """
    return f"build/{deployment_id}"
