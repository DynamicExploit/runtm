"""Atomic tracking of concurrent deploys per tenant.

Uses Redis INCR as atomic reservation gate:
- INCR first, then check if over limit
- If over limit, DECR immediately and deny

This prevents race conditions in check-then-act patterns where two
concurrent requests could both pass the limit check before either
increments the counter.

OWNERSHIP MODEL:
- API reserves slot when deploy is accepted (reserve_concurrent_deploy)
- API releases slot ONLY on pre-enqueue failures
- Worker releases slot in finally block (owns release after successful enqueue)
- Do NOT double-release: after successful enqueue, only worker releases

Usage:
    # In API (create_deployment):
    allowed, count = reserve_concurrent_deploy(redis, tenant_id, limit, deployment_id)
    if not allowed:
        raise HTTPException(403, "Concurrent limit reached")

    try:
        # ... create deployment, enqueue job ...
        # SUCCESS: Do NOT release - worker owns release
    except Exception:
        # FAILURE: Release since worker won't run
        release_concurrent_deploy(redis, tenant_id, deployment_id)
        raise

    # In Worker (process_deployment):
    try:
        # ... build and deploy ...
    finally:
        release_concurrent_deploy(redis, tenant_id, deployment_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from redis import Redis

# TTL for concurrent deploy keys: 6 hours
# - Long enough for slowest deploys (build timeout 10m + deploy 5m + buffer)
# - Short enough to recover from orphaned keys if worker crashes without cleanup
CONCURRENT_DEPLOY_TTL_SECONDS = 6 * 60 * 60


def reserve_concurrent_deploy(
    redis: Redis,
    tenant_id: str,
    limit: Optional[int],
    deployment_id: Optional[str] = None,
) -> Tuple[bool, int]:
    """Atomically reserve a concurrent deploy slot.

    Uses INCR-then-check pattern for race-safe admission control.
    The increment IS the reservation - if over limit, we immediately
    decrement and deny.

    Args:
        redis: Redis client
        tenant_id: Tenant to reserve for
        limit: Max concurrent deploys (None = unlimited)
        deployment_id: Optional deployment ID for debugging/tracking

    Returns:
        Tuple of (allowed, current_count):
        - If allowed=True, slot is reserved and count is the new count
        - If allowed=False, slot was NOT reserved (already decremented),
          count is the current count (at limit)
    """
    if limit is None:
        return True, 0  # Unlimited

    key = f"concurrent_deploys:{tenant_id}"

    # Atomic increment - THIS is the reservation
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, CONCURRENT_DEPLOY_TTL_SECONDS)
    results = pipe.execute()
    count = results[0]

    # Check if over limit AFTER incrementing
    if count > limit:
        # Over limit - release reservation immediately
        redis.decr(key)
        return False, count - 1

    # Optional: track which deployment holds this slot (for debugging)
    if deployment_id:
        slot_key = f"concurrent_deploy_slot:{tenant_id}:{deployment_id}"
        redis.setex(slot_key, CONCURRENT_DEPLOY_TTL_SECONDS, "1")

    return True, count


def release_concurrent_deploy(
    redis: Redis,
    tenant_id: str,
    deployment_id: Optional[str] = None,
) -> int:
    """Release a concurrent deploy slot.

    IMPORTANT: Only call this from:
    - API: if enqueue FAILS after reservation
    - Worker: in finally block when job completes (success or failure)

    Do NOT call from API after successful enqueue - worker owns release.

    Args:
        redis: Redis client
        tenant_id: Tenant to release for
        deployment_id: Optional deployment ID for cleanup

    Returns:
        New count after decrement
    """
    key = f"concurrent_deploys:{tenant_id}"
    count = redis.decr(key)

    # Ensure non-negative (defensive against bugs or race conditions)
    if count < 0:
        redis.set(key, 0)
        count = 0

    # Clean up slot tracker if we tracked it
    if deployment_id:
        slot_key = f"concurrent_deploy_slot:{tenant_id}:{deployment_id}"
        redis.delete(slot_key)

    return count


def get_concurrent_deploy_count(redis: Redis, tenant_id: str) -> int:
    """Get current concurrent deploy count (read-only).

    Args:
        redis: Redis client
        tenant_id: Tenant to check

    Returns:
        Current count of in-progress deploys
    """
    key = f"concurrent_deploys:{tenant_id}"
    count = redis.get(key)
    return int(count) if count else 0
