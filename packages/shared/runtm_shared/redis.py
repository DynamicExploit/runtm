"""Shared Redis client factory.

Both API and worker should use this to ensure consistent connection config
(TLS, auth, cluster mode, etc.).

Usage:
    from runtm_shared.redis import get_redis_client

    redis = get_redis_client()
    if redis:
        redis.set("key", "value")
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from redis import Redis


@lru_cache
def get_redis_url() -> Optional[str]:
    """Get Redis URL from environment.

    Returns:
        Redis URL or None if not configured.
    """
    return os.environ.get("REDIS_URL")


def get_redis_client() -> Optional[Redis]:
    """Get a Redis client with consistent configuration.

    Returns None if REDIS_URL is not configured.
    Both API and worker should use this function to ensure
    consistent connection settings (TLS, auth, cluster mode, etc.).

    Returns:
        Redis client or None if not configured.
    """
    url = get_redis_url()
    if not url:
        return None

    import redis

    return redis.from_url(url)


# Track whether we've logged the "no Redis" warning
_logged_no_redis = False


def get_redis_client_or_warn() -> Optional[Redis]:
    """Get Redis client, logging once if not configured.

    Use this in code paths where Redis is optional but its absence
    should be noted for operational visibility.

    Returns:
        Redis client or None if not configured (logs warning once).
    """
    global _logged_no_redis

    client = get_redis_client()
    if client is None and not _logged_no_redis:
        import logging

        logging.getLogger(__name__).warning(
            "REDIS_URL not configured. Concurrent deploy limits will not be enforced."
        )
        _logged_no_redis = True
    return client


def reset_redis_warning() -> None:
    """Reset the "no Redis" warning flag. Call in tests."""
    global _logged_no_redis
    _logged_no_redis = False
