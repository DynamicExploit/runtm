"""Idempotency key handling for safe retries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from runtm_api.db.models import Deployment, IdempotencyKey
from runtm_shared.types import Limits


class IdempotencyService:
    """Service for handling idempotency keys.

    Ensures that retried requests with the same Idempotency-Key header
    return the same deployment instead of creating duplicates.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_existing_deployment(self, idempotency_key: str) -> Optional[Deployment]:
        """Check if an idempotency key already exists and return associated deployment.

        Args:
            idempotency_key: The Idempotency-Key header value

        Returns:
            The existing Deployment if key exists and hasn't expired, None otherwise
        """
        record = (
            self.db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == idempotency_key)
            .filter(IdempotencyKey.expires_at > datetime.now(timezone.utc))
            .first()
        )

        if record is None:
            return None

        deployment = self.db.query(Deployment).filter(Deployment.id == record.deployment_id).first()
        return deployment

    def store_key(self, idempotency_key: str, deployment_id: uuid.UUID) -> IdempotencyKey:
        """Store an idempotency key for a deployment.

        Args:
            idempotency_key: The Idempotency-Key header value
            deployment_id: The internal UUID of the deployment

        Returns:
            The created IdempotencyKey record
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=Limits.IDEMPOTENCY_KEY_TTL_HOURS)

        record = IdempotencyKey(
            key=idempotency_key,
            deployment_id=deployment_id,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.flush()  # Ensure ID is generated
        return record

    def cleanup_expired(self) -> int:
        """Delete expired idempotency keys.

        Returns:
            Number of keys deleted
        """
        result = (
            self.db.query(IdempotencyKey)
            .filter(IdempotencyKey.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        self.db.commit()
        return result


def get_idempotency_key(headers: dict) -> Optional[str]:
    """Extract idempotency key from request headers.

    Args:
        headers: Request headers dict

    Returns:
        Idempotency key if present, None otherwise
    """
    # Check both cases for header name
    key = headers.get("Idempotency-Key") or headers.get("idempotency-key")

    if key and len(key) <= 64:  # Validate length
        return key

    return None
