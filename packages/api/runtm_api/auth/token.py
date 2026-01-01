"""Token-based authentication for Runtm API.

Supports two modes:
- SINGLE_TENANT: Simple static token from environment (for self-hosting)
- MULTI_TENANT: API keys stored in database with versioned HMAC hashing

Multi-tenant mode features:
- HMAC-SHA256 with server-side pepper (not plain SHA256)
- Versioned peppers for rotation without breaking existing keys
- 16-character prefix for near-O(1) database lookup
- Throttled last_used_at updates (max every 5 minutes)
- Rate limiting on failed auth attempts per IP
- Client IP tracking for audit

Security Notes:
- Rate limiting prevents prefix enumeration attacks
- Constant-time comparison used throughout
- Failed auths return identical errors (no enumeration)
"""

from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from runtm_api.auth.keys import PREFIX_LENGTH, hash_key, validate_token_format, verify_key
from runtm_api.core.config import Settings, get_settings
from runtm_api.db.models import ApiKey
from runtm_api.db.session import get_db
from runtm_shared.errors import InvalidTokenError
from runtm_shared.types import ApiKeyScope, AuthContext, AuthMode

# Throttle last_used_at updates to avoid write amplification
# Only update if more than 5 minutes since last update
LAST_USED_UPDATE_THRESHOLD_SECONDS = 300

# Rate limiting: max failed attempts per IP per minute
# Note: In production, use Redis for distributed rate limiting
MAX_FAILED_ATTEMPTS_PER_MINUTE = 10
_failed_attempts: dict[str, list[float]] = {}  # In-memory for now


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies.

    Args:
        request: FastAPI request

    Returns:
        Client IP address
    """
    # Check common proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()

    # Fly.io specific header
    fly_client_ip = request.headers.get("Fly-Client-IP")
    if fly_client_ip:
        return fly_client_ip

    # Fall back to direct connection
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    """Check if IP is rate limited for auth attempts.

    Simple in-memory implementation. For production, use Redis.

    Args:
        ip: Client IP address

    Returns:
        True if allowed, False if rate limited
    """
    import time

    now = time.time()
    window_start = now - 60  # 1 minute window

    # Clean old entries and check count
    if ip in _failed_attempts:
        _failed_attempts[ip] = [t for t in _failed_attempts[ip] if t > window_start]
        if len(_failed_attempts[ip]) >= MAX_FAILED_ATTEMPTS_PER_MINUTE:
            return False
    return True


def _record_failed_attempt(ip: str) -> None:
    """Record a failed auth attempt for rate limiting.

    Args:
        ip: Client IP address
    """
    import time

    if ip not in _failed_attempts:
        _failed_attempts[ip] = []
    _failed_attempts[ip].append(time.time())


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
        return await _authenticate_multi_tenant(token, db, settings, request)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": f"Unsupported auth mode: {settings.auth_mode}"},
    )


def _authenticate_single_tenant(token: str, settings: Settings) -> AuthContext:
    """Authenticate in single-tenant mode using static token.

    SECURITY: In production, RUNTM_API_TOKEN must be set. The insecure
    bypass (accept any token) requires BOTH debug=True AND
    allow_insecure_dev_auth=True to prevent accidental exposure.

    Args:
        token: Bearer token from request
        settings: Application settings

    Returns:
        AuthContext for the default tenant with full permissions

    Raises:
        HTTPException: If token is invalid or not configured
    """
    import logging

    if not settings.api_token:
        # SECURITY: Only allow bypass if BOTH flags are explicitly set
        if settings.debug and settings.allow_insecure_dev_auth:
            logging.warning(
                "SECURITY WARNING: Running with ALLOW_INSECURE_DEV_AUTH=true. "
                "Any token will be accepted. DO NOT USE IN PRODUCTION."
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

        # In all other cases, fail with clear error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "RUNTM_API_TOKEN not configured",
                "hint": "Set RUNTM_API_TOKEN environment variable",
            },
        )

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(token, settings.api_token):
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
    request: Request,
) -> AuthContext:
    """Authenticate in multi-tenant mode using API keys.

    Lookup flow:
    1. Check rate limit for client IP
    2. Validate token format (starts with "runtm_")
    3. Extract prefix for near-O(1) DB lookup
    4. Query candidates by prefix (non-revoked keys)
    5. Verify HMAC hash with versioned peppers (constant-time)
    6. Check expiration
    7. Update last_used_at and last_used_ip (throttled)

    Security:
    - Rate limiting prevents prefix enumeration attacks
    - Constant-time comparison used even when no candidates
    - Identical error responses for all auth failures

    Args:
        token: Bearer token from request
        db: Database session
        settings: Application settings
        request: FastAPI request for IP extraction

    Returns:
        AuthContext with tenant, principal, and scopes

    Raises:
        HTTPException: If token is invalid, expired, or revoked
    """
    client_ip = _get_client_ip(request)

    # Check rate limit first
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Too many authentication attempts. Try again later."},
        )

    # Helper to raise auth error and record failed attempt
    def _auth_failed() -> None:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token format
    if not validate_token_format(token):
        _auth_failed()

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
        # No matching keys - perform constant-time fake check to prevent timing oracle
        # This ensures the response time is similar whether or not the prefix exists
        fake_hash = hash_key(token, list(settings.peppers.values())[0])
        hmac.compare_digest(fake_hash, "0" * 64)
        _auth_failed()

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
        _auth_failed()

    # Check expiration
    now = datetime.now(timezone.utc)
    if api_key.expires_at and api_key.expires_at < now:
        _auth_failed()

    # Throttled last_used_at update (avoid write amplification)
    should_update = False
    if api_key.last_used_at is None:
        should_update = True
    else:
        # Ensure both datetimes are timezone-aware for comparison
        last_used = api_key.last_used_at
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)

        seconds_since_last_use = (now - last_used).total_seconds()
        if seconds_since_last_use > LAST_USED_UPDATE_THRESHOLD_SECONDS:
            should_update = True

    if should_update:
        api_key.last_used_at = now
        # Track client IP for audit
        if hasattr(api_key, "last_used_ip"):
            api_key.last_used_ip = client_ip
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
