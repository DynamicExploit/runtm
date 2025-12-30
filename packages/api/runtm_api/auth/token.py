"""Token-based authentication for Runtm API.

Supports two modes:
- SINGLE_TENANT: Simple static token from environment (for self-hosting)
- MULTI_TENANT: API keys stored in database with versioned HMAC hashing

Multi-tenant mode features:
- HMAC-SHA256 with server-side pepper (not plain SHA256)
- Versioned peppers for rotation without breaking existing keys
- 16-character prefix for near-O(1) database lookup
- Throttled last_used_at updates (max every 5 minutes)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from runtm_api.auth.keys import PREFIX_LENGTH, validate_token_format, verify_key
from runtm_api.core.config import Settings, get_settings
from runtm_api.db.models import ApiKey
from runtm_api.db.session import get_db
from runtm_shared.errors import InvalidTokenError
from runtm_shared.types import ApiKeyScope, AuthContext, AuthMode

# Throttle last_used_at updates to avoid write amplification
# Only update if more than 5 minutes since last update
LAST_USED_UPDATE_THRESHOLD_SECONDS = 300


def extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        Token string if found, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


async def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """Validate request authentication and return AuthContext.

    In single-tenant mode, validates against RUNTM_API_TOKEN.
    In multi-tenant mode, looks up API key by prefix and verifies with HMAC.

    Args:
        request: FastAPI request object
        db: Database session
        settings: Application settings

    Returns:
        AuthContext with validated token info

    Raises:
        HTTPException: If authentication fails
    """
    token = extract_bearer_token(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_mode == AuthMode.SINGLE_TENANT:
        return _authenticate_single_tenant(token, settings)

    if settings.auth_mode == AuthMode.MULTI_TENANT:
        return await _authenticate_multi_tenant(token, db, settings)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": f"Unsupported auth mode: {settings.auth_mode}"},
    )


def _authenticate_single_tenant(token: str, settings: Settings) -> AuthContext:
    """Authenticate in single-tenant mode using static token.

    Args:
        token: Bearer token from request
        settings: Application settings

    Returns:
        AuthContext for the default tenant with full permissions

    Raises:
        HTTPException: If token is invalid
    """
    if not settings.api_token:
        # Development mode: allow any token if API_TOKEN not set
        if settings.debug:
            return AuthContext(
                token=token,
                tenant_id="default",
                principal_id="default",
                scopes={
                    ApiKeyScope.READ.value,
                    ApiKeyScope.DEPLOY.value,
                    ApiKeyScope.DELETE.value,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "API token not configured"},
        )

    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthContext(
        token=token,
        tenant_id="default",
        principal_id="default",
        scopes={
            ApiKeyScope.READ.value,
            ApiKeyScope.DEPLOY.value,
            ApiKeyScope.DELETE.value,
        },
    )


async def _authenticate_multi_tenant(
    token: str,
    db: Session,
    settings: Settings,
) -> AuthContext:
    """Authenticate in multi-tenant mode using API keys.

    Lookup flow:
    1. Validate token format (starts with "runtm_")
    2. Extract 16-char prefix for near-O(1) DB lookup
    3. Query candidates by prefix (non-revoked keys)
    4. Verify HMAC hash with versioned peppers
    5. Check expiration
    6. Update last_used_at (throttled)

    Args:
        token: Bearer token from request
        db: Database session
        settings: Application settings

    Returns:
        AuthContext with tenant, principal, and scopes

    Raises:
        HTTPException: If token is invalid, expired, or revoked
    """
    # Validate token format
    if not validate_token_format(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError(message="Invalid token format").to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check pepper configuration
    if not settings.peppers:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Token pepper not configured for multi-tenant mode"},
        )

    # Extract prefix for lookup
    prefix = token[:PREFIX_LENGTH]

    # Query candidates by prefix (only non-revoked)
    candidates = (
        db.query(ApiKey)
        .filter(
            ApiKey.key_prefix == prefix,
            ApiKey.is_revoked == False,  # noqa: E712
        )
        .all()
    )

    if not candidates:
        # No matching keys - return 401 (not 404 to prevent enumeration)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify hash with versioned HMAC
    api_key = None
    for candidate in candidates:
        if verify_key(
            raw_token=token,
            stored_hash=candidate.key_hash,
            stored_pepper_version=candidate.pepper_version,
            peppers=settings.peppers,
            migration_window_versions=settings.migration_versions,
        ):
            api_key = candidate
            break

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check expiration
    now = datetime.now(timezone.utc)
    if api_key.expires_at and api_key.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError(message="Token expired").to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Throttled last_used_at update (avoid write amplification)
    if api_key.last_used_at is None:
        api_key.last_used_at = now
        db.commit()
    else:
        # Ensure both datetimes are timezone-aware for comparison
        last_used = api_key.last_used_at
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)

        seconds_since_last_use = (now - last_used).total_seconds()
        if seconds_since_last_use > LAST_USED_UPDATE_THRESHOLD_SECONDS:
            api_key.last_used_at = now
            db.commit()

    return AuthContext(
        token=token,
        tenant_id=api_key.tenant_id,
        principal_id=api_key.principal_id,
        api_key_id=str(api_key.id),
        scopes=set(api_key.scopes) if api_key.scopes else set(),
    )


def require_scope(scope: ApiKeyScope):
    """Dependency factory to enforce scope on a route.

    Usage:
        @router.post("", dependencies=[require_scope(ApiKeyScope.DEPLOY)])
        async def create_deployment(...):
            ...

    Args:
        scope: Required scope for the route

    Returns:
        FastAPI dependency that checks the scope
    """
    from runtm_shared.types import has_scope

    async def checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not has_scope(auth.scopes, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": f"Missing required scope: {scope.value}"},
            )
        return auth

    return Depends(checker)


# Dependency for requiring authentication (any valid token)
RequireAuth = Depends(get_auth_context)
