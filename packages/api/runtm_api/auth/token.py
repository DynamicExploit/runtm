"""Token-based authentication for Runtm API.

Supports two modes:
- SINGLE_TENANT: Simple static token from environment (for self-hosting)
- MULTI_TENANT: API keys stored in database with versioned HMAC hashing

Multi-tenant mode features:
- HMAC-SHA256 with server-side pepper (not plain SHA256)
- Versioned peppers for rotation without breaking existing keys
- 16-character prefix for near-O(1) database lookup
- Throttled last_used_at updates (max every 5 minutes)
- Rate limiting on failed auth attempts per IP (fail-closed in production)
- Client IP tracking for audit
- Structured audit logging for security monitoring

Security Notes:
- Rate limiting prevents prefix enumeration attacks
- Constant-time comparison used throughout
- Failed auths return identical errors (no enumeration)
- All auth events logged for security monitoring
"""

from __future__ import annotations

import hmac
import json
import logging
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

# Structured logger for auth events
_audit_logger = logging.getLogger("runtm.auth.audit")


def _log_auth_event(
    event: str,
    ip: str,
    success: bool,
    reason: str = "",
    identifier: str = "",
    tenant_id: str = "",
) -> None:
    """Log auth events for security monitoring.

    SECURITY: Logs structured auth events for:
    - Security monitoring and alerting
    - Incident investigation and forensics
    - Compliance and audit trails

    Never logs full tokens - only the first 16 chars (identifier) which
    is the same prefix stored in the database.

    Args:
        event: Event type (e.g., "auth_success", "auth_failed", "rate_limited")
        ip: Client IP address
        success: Whether authentication succeeded
        reason: Failure reason if applicable
        identifier: Token prefix (first 16 chars) or username
        tenant_id: Tenant ID if known (on success)
    """
    # Build structured log entry as JSON
    log_entry = {
        "event": event,
        "ip": ip,
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if reason:
        log_entry["reason"] = reason
    if identifier:
        # Never log more than 16 chars of token/identifier
        log_entry["identifier"] = identifier[:16]
    if tenant_id:
        log_entry["tenant_id"] = tenant_id

    # Log as JSON for easy parsing by log aggregators
    _audit_logger.info(json.dumps(log_entry))


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies.

    Note: This is a basic implementation. For production with untrusted
    networks, use the trusted proxy middleware from runtm_api.middleware.proxy.

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


def _check_auth_rate_limit(ip: str, identifier: str = "") -> bool:
    """Check auth rate limit using Redis. Fails CLOSED in production.

    SECURITY: This function fails closed in production - if Redis is
    unavailable, authentication requests are rejected with 503.
    In debug mode, it fails open to allow local development.

    Args:
        ip: Client IP address
        identifier: Token prefix for rate limiting (first 16 chars)

    Returns:
        True if allowed, False if rate limited

    Raises:
        HTTPException: 503 if rate limiter unavailable in production
    """
    from runtm_api.services.rate_limit import get_rate_limiter

    settings = get_settings()
    limiter = get_rate_limiter()

    if limiter is None:
        if settings.debug:
            # Dev mode: allow if Redis unavailable
            return True
        # Production: fail closed - no Redis = no auth
        raise HTTPException(
            status_code=503,
            detail={"error": "Rate limiter unavailable. Try again later."},
        )

    allowed, _remaining, _reset_at = limiter.check_auth_rate_limit(ip, identifier)
    return allowed


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

    In single-tenant mode, validates against RUNTM_API_SECRET.
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
        return _authenticate_single_tenant(token, settings, request)

    if settings.auth_mode == AuthMode.MULTI_TENANT:
        return await _authenticate_multi_tenant(token, db, settings, request)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": f"Unsupported auth mode: {settings.auth_mode}"},
    )


def _authenticate_single_tenant(token: str, settings: Settings, request: Request) -> AuthContext:
    """Authenticate in single-tenant mode using static token.

    SECURITY: In production, RUNTM_API_SECRET must be set. The insecure
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

    if not settings.api_secret:
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
                "error": "RUNTM_API_SECRET not configured",
                "hint": "Set RUNTM_API_SECRET environment variable",
            },
        )

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(token, settings.api_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Determine tenant_id and principal_id
    tenant_id = "default"
    principal_id = "default"

    if settings.trust_tenant_header:
        # Trust headers from authenticated internal proxy
        header_tenant_id = request.headers.get("X-Tenant-Id")
        header_user_id = request.headers.get("X-User-Id")
        if header_tenant_id:
            tenant_id = header_tenant_id
        if header_user_id:
            principal_id = header_user_id

    return AuthContext(
        token=token,
        tenant_id=tenant_id,
        principal_id=principal_id,
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
    1. Check rate limit for client IP + token prefix
    2. Validate token format (starts with "runtm_")
    3. Extract prefix for near-O(1) DB lookup
    4. Query candidates by prefix (non-revoked keys)
    5. Verify HMAC hash with versioned peppers (constant-time)
    6. Check expiration
    7. Update last_used_at and last_used_ip (throttled)

    Security:
    - Rate limiting prevents prefix enumeration attacks (uses Redis, fail-closed)
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

    # Extract identifier from token prefix for rate limiting
    # (We don't have username at this point, but prefix is unique enough)
    identifier = token[:16] if len(token) >= 16 else ""

    # Check rate limit first (fail-closed in production)
    if not _check_auth_rate_limit(client_ip, identifier):
        _log_auth_event(
            "rate_limited",
            client_ip,
            False,
            reason="too_many_attempts",
            identifier=identifier,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Too many authentication attempts. Try again later."},
        )

    # Helper to raise auth error with logging
    def _auth_failed(reason: str = "invalid_token") -> None:
        _log_auth_event(
            "auth_failed",
            client_ip,
            False,
            reason=reason,
            identifier=identifier,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidTokenError().to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token format
    if not validate_token_format(token):
        _auth_failed("invalid_format")

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
        _auth_failed("no_matching_key")

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
        _auth_failed("hash_mismatch")

    # Check expiration
    now = datetime.now(timezone.utc)
    if api_key.expires_at and api_key.expires_at < now:
        _auth_failed("token_expired")

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

    # Log successful authentication
    _log_auth_event(
        "auth_success",
        client_ip,
        True,
        identifier=identifier,
        tenant_id=api_key.tenant_id,
    )

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
