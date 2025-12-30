"""Authentication module."""

from runtm_api.auth.keys import (
    PREFIX_LENGTH,
    generate_api_key,
    hash_key,
    validate_token_format,
    verify_key,
)
from runtm_api.auth.token import (
    RequireAuth,
    extract_bearer_token,
    get_auth_context,
    require_scope,
)

__all__ = [
    # Token authentication
    "RequireAuth",
    "extract_bearer_token",
    "get_auth_context",
    "require_scope",
    # Key generation and verification
    "PREFIX_LENGTH",
    "generate_api_key",
    "hash_key",
    "validate_token_format",
    "verify_key",
]
