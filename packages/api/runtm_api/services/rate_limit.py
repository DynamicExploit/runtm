"""Atomic token bucket rate limiting with Lua script.

This module provides rate limiting using Redis with:
- Atomic operations via Lua script (no race conditions)
- Token bucket algorithm (vs ZSET sliding window)
- Per-tier limits (AUTH, DEPLOY, WRITE, READ)
- Standard rate limit headers (X-RateLimit-*, Retry-After)

Why Lua script instead of ZSET pipeline:
- ZSET approach has collision issues (same timestamp overwrites)
- Pipeline is not atomic (race conditions between ZCARD and ZADD)
- Lua script is atomic and handles edge cases correctly

Tier Design:
- AUTH: Authentication attempts (strictest, fail-closed in production)
- DEPLOY: Creating/deploying resources (expensive)
- WRITE: Modifying state (moderate)
- READ: Reading data (cheap)
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException

from runtm_api.auth.token import get_auth_context

if TYPE_CHECKING:
    from redis import Redis

    from runtm_shared.types import AuthContext


class RateLimitTier(str, Enum):
    """Rate limiting tiers with different limits.

    Choose tier based on resource cost of the operation:
    - AUTH: Authentication attempts (strictest)
    - DEPLOY: Creating/deploying resources (expensive)
    - WRITE: Modifying state (moderate)
    - READ: Reading data (cheap)
    """

    AUTH = "auth"
    DEPLOY = "deploy"
    WRITE = "write"
    READ = "read"


# Tier limits: (max_requests, window_seconds)
# These are starting values - adjust based on actual usage patterns
TIER_LIMITS: dict[RateLimitTier, tuple[int, int]] = {
    RateLimitTier.AUTH: (5, 60),  # 5 per minute per identifier (strictest)
    RateLimitTier.DEPLOY: (10, 3600),  # 10 per hour
    RateLimitTier.WRITE: (60, 3600),  # 60 per hour
    RateLimitTier.READ: (300, 3600),  # 300 per hour
}

# Atomic token bucket Lua script
# Returns: [allowed (0/1), remaining, reset_at_timestamp]
#
# This script is executed atomically in Redis, preventing race conditions
# that occur with multi-command approaches.
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Get current count and window start
local bucket = redis.call('HMGET', key, 'count', 'window_start')
local count = tonumber(bucket[1]) or 0
local window_start = tonumber(bucket[2]) or now

-- Check if window has expired (reset bucket)
if now - window_start >= window then
    count = 0
    window_start = now
end

-- Calculate reset time (end of current window)
local reset_at = window_start + window

-- Check if under limit
local allowed = 0
if count < limit then
    allowed = 1
    count = count + 1
    -- Update bucket atomically
    redis.call('HMSET', key, 'count', count, 'window_start', window_start)
    redis.call('EXPIRE', key, window)
end

local remaining = math.max(0, limit - count)
return {allowed, remaining, reset_at}
"""


class RateLimiter:
    """Rate limiter using Redis with atomic Lua script.

    Usage:
        limiter = RateLimiter(redis_client)
        allowed, remaining, reset_at = limiter.check("tenant_123", RateLimitTier.DEPLOY)
        if not allowed:
            raise HTTPException(429, headers={"Retry-After": str(reset_at - now)})
    """

    def __init__(self, redis: Redis):
        """Initialize rate limiter.

        Args:
            redis: Redis client instance
        """
        self.redis = redis
        self._script = redis.register_script(TOKEN_BUCKET_SCRIPT)

    def check(
        self,
        tenant_id: str,
        tier: RateLimitTier,
        resource: str | None = None,
    ) -> tuple[bool, int, int]:
        """Atomic token bucket rate limit check.

        Args:
            tenant_id: Tenant to rate limit
            tier: Rate limit tier (determines limits)
            resource: Optional resource identifier for finer-grained limiting

        Returns:
            Tuple of (allowed, remaining, reset_timestamp)
        """
        limit, window = TIER_LIMITS[tier]

        # Key format: rate:{tenant}:{tier}[:resource]
        if resource:
            key = f"rate:{tenant_id}:{tier.value}:{resource}"
        else:
            key = f"rate:{tenant_id}:{tier.value}"

        now = int(time.time())

        # Execute atomic Lua script
        result = self._script(keys=[key], args=[limit, window, now])
        allowed, remaining, reset_at = result

        return bool(allowed), int(remaining), int(reset_at)

    def get_limit_info(
        self,
        tenant_id: str,
        tier: RateLimitTier,
    ) -> dict[str, int]:
        """Get current rate limit info without consuming.

        Args:
            tenant_id: Tenant to check
            tier: Rate limit tier

        Returns:
            Dict with limit, remaining, and reset info
        """
        limit, window = TIER_LIMITS[tier]
        key = f"rate:{tenant_id}:{tier.value}"
        now = int(time.time())

        # Get current bucket state
        bucket = self.redis.hgetall(key)
        if not bucket:
            return {
                "limit": limit,
                "remaining": limit,
                "reset": now + window,
            }

        count = int(bucket.get(b"count", 0))
        window_start = int(bucket.get(b"window_start", now))

        # Check if window expired
        if now - window_start >= window:
            return {
                "limit": limit,
                "remaining": limit,
                "reset": now + window,
            }

        return {
            "limit": limit,
            "remaining": max(0, limit - count),
            "reset": window_start + window,
        }

    def _check_bucket(self, key: str, limit: int, window: int) -> tuple[bool, int, int]:
        """Low-level bucket check using Lua script.

        Args:
            key: Redis key for the bucket
            limit: Maximum requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed, remaining, reset_timestamp)
        """
        now = int(time.time())
        result = self._script(keys=[key], args=[limit, window, now])
        allowed, remaining, reset_at = result
        return bool(allowed), int(remaining), int(reset_at)

    def check_auth_rate_limit(
        self,
        ip: str,
        identifier: str = "",
    ) -> tuple[bool, int, int]:
        """Rate limit authentication attempts by IP + identifier.

        Uses a dual-bucket approach:
        - IP-only bucket: Prevents spray attacks across many tokens
        - IP+identifier bucket: Prevents targeted brute force on one token

        Keying on both prevents:
        - Single IP locking out NAT'd office (identifier spreads load)
        - Credential stuffing across many accounts from one IP

        Args:
            ip: Client IP address
            identifier: Token prefix or username (first 16 chars)

        Returns:
            Tuple of (allowed, remaining, reset_timestamp)
        """
        limit, window = TIER_LIMITS[RateLimitTier.AUTH]

        # Check IP-only bucket (prevents spray attacks)
        # Allow 3x the per-identifier limit for the IP as a whole
        ip_key = f"auth:ip:{ip}"
        ip_allowed, ip_remaining, ip_reset = self._check_bucket(ip_key, limit * 3, window)

        # Check IP+identifier bucket (prevents targeted brute force)
        if identifier:
            combo_key = f"auth:combo:{ip}:{identifier}"
            combo_allowed, combo_remaining, combo_reset = self._check_bucket(
                combo_key, limit, window
            )

            # Both must pass
            if not ip_allowed or not combo_allowed:
                return False, min(ip_remaining, combo_remaining), max(ip_reset, combo_reset)
            return True, min(ip_remaining, combo_remaining), max(ip_reset, combo_reset)

        return ip_allowed, ip_remaining, ip_reset


# Global rate limiter instance (set during app startup)
_rate_limiter: RateLimiter | None = None


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter instance.

    Called during app startup after Redis is initialized.
    """
    global _rate_limiter
    _rate_limiter = limiter


def get_rate_limiter() -> RateLimiter | None:
    """Get the global rate limiter instance.

    Returns:
        RateLimiter instance or None if not initialized
    """
    return _rate_limiter


def rate_limit(tier: RateLimitTier, resource: str | None = None):
    """Route dependency factory for rate limiting.

    Usage:
        @router.post("", dependencies=[rate_limit(RateLimitTier.DEPLOY)])
        async def create_deployment(...):
            ...

    Args:
        tier: Rate limit tier to apply
        resource: Optional resource identifier for finer-grained limits

    Returns:
        FastAPI dependency that enforces rate limiting
    """

    async def checker(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        limiter = get_rate_limiter()
        if limiter is None:
            # Rate limiting not configured - allow request
            return auth

        allowed, remaining, reset_at = limiter.check(auth.tenant_id, tier, resource)

        if not allowed:
            limit, _ = TIER_LIMITS[tier]
            now = int(time.time())
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "tier": tier.value,
                    "retry_after": max(0, reset_at - now),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(max(0, reset_at - now)),
                },
            )

        return auth

    return Depends(checker)
