"""Worker entrypoint - processes deployment jobs from Redis queue."""

from __future__ import annotations

import atexit
import os
from typing import Optional

# Ensure .env is loaded from project root before reading environment
from runtm_shared.env import ensure_env_loaded  # noqa: F401

ensure_env_loaded()

from redis import Redis
from rq import Queue, Worker

from runtm_worker.jobs import process_deployment
from runtm_worker.telemetry import init_telemetry, shutdown_telemetry


def get_redis_connection() -> Redis:
    """Get Redis connection from environment."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return Redis.from_url(redis_url)


def create_queue(redis_conn: Optional[Redis] = None) -> Queue:
    """Create the deployment queue.

    Args:
        redis_conn: Optional Redis connection

    Returns:
        RQ Queue instance
    """
    if redis_conn is None:
        redis_conn = get_redis_connection()
    return Queue("deployments", connection=redis_conn)


def enqueue_deployment(deployment_id: str) -> str:
    """Enqueue a deployment job.

    Args:
        deployment_id: Deployment ID to process

    Returns:
        Job ID
    """
    queue = create_queue()
    job = queue.enqueue(
        process_deployment,
        deployment_id,
        job_timeout="20m",  # 20 minutes max
        result_ttl=86400,  # Keep result for 24 hours
    )
    return job.id


def run_worker() -> None:
    """Run the worker process.

    This is the main entrypoint for the worker container.
    """
    print("Starting Runtm Worker...")
    print(f"Redis URL: {os.environ.get('REDIS_URL', 'redis://localhost:6379')}")

    # Initialize telemetry
    # Worker runs inside Docker, so API is accessible at http://api:8000
    api_url = os.environ.get("RUNTM_API_URL", "http://api:8000")
    api_token = os.environ.get("RUNTM_API_SECRET", "dev-token")
    init_telemetry(api_url=api_url, api_token=api_token)
    atexit.register(shutdown_telemetry)
    print(f"Telemetry initialized (sending to {api_url})")

    redis_conn = get_redis_connection()
    queue = create_queue(redis_conn)

    # Create and run worker
    worker = Worker(
        [queue],
        connection=redis_conn,
        name=f"runtm-worker-{os.getpid()}",
    )

    print(f"Worker {worker.name} started, listening on queue: {queue.name}")
    worker.work()


if __name__ == "__main__":
    run_worker()
