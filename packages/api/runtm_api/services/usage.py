"""Usage tracking service with full audit trail.

This service provides:
- Append-only event logging for audit/reconciliation/billing disputes
- Race-safe counter upserts for fast quota checks
- Full attribution (who did it, which API key, request correlation)

Design decisions:
- Events are NEVER deleted (audit trail)
- Counters use SQL UPSERT for race-safe increments
- Attribution includes principal_id, api_key_id, request_id
- Tenant isolation is enforced on all queries
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from runtm_api.db.models import UsageCounter, UsageEvent
from runtm_shared.types import AuthContext


class UsageService:
    """Service for tracking usage events and quota consumption.

    Usage:
        usage = UsageService(db)
        usage.record(auth, "deploy", deployment_id="dep_abc123")
        allowed, current = usage.check_quota(auth.tenant_id, "deploy", limit=100)
    """

    def __init__(self, db: Session):
        """Initialize usage service.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def record(
        self,
        auth: AuthContext,
        event_type: str,
        deployment_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> UsageEvent:
        """Record a usage event with full attribution.

        This creates both:
        1. An append-only event record (for audit trail)
        2. A counter increment (for fast quota checks)

        Args:
            auth: Auth context (provides tenant, principal, api_key)
            event_type: Type of event (deploy, destroy, etc.)
            deployment_id: Optional deployment ID for correlation
            request_id: Optional request ID for correlation
            metadata: Optional additional metadata

        Returns:
            Created UsageEvent
        """
        # 1. Create append-only event (audit trail with full attribution)
        event = UsageEvent(
            id=uuid4(),
            tenant_id=auth.tenant_id,
            principal_id=auth.principal_id,
            api_key_id=auth.api_key_id or "unknown",
            request_id=request_id,
            deployment_id=deployment_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
        self.db.add(event)

        # 2. Upsert counter (race-safe with ON CONFLICT)
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        self.db.execute(
            text(
                """
            INSERT INTO usage_counters (id, tenant_id, resource_type, period, count)
            VALUES (gen_random_uuid(), :tenant_id, :resource_type, :period, 1)
            ON CONFLICT (tenant_id, resource_type, period)
            DO UPDATE SET count = usage_counters.count + 1
        """
            ),
            {
                "tenant_id": auth.tenant_id,
                "resource_type": event_type,
                "period": period,
            },
        )

        self.db.commit()
        return event

    def check_quota(
        self,
        tenant_id: str,
        resource_type: str,
        limit: int,
    ) -> tuple[bool, int]:
        """Check if tenant is under quota for a resource type.

        Args:
            tenant_id: Tenant to check
            resource_type: Type of resource (matches event_type)
            limit: Maximum allowed count

        Returns:
            Tuple of (is_allowed, current_count)
        """
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        counter = (
            self.db.query(UsageCounter)
            .filter_by(
                tenant_id=tenant_id,
                resource_type=resource_type,
                period=period,
            )
            .first()
        )
        current = counter.count if counter else 0
        return current < limit, current

    def get_current_usage(
        self,
        tenant_id: str,
        resource_type: Optional[str] = None,
    ) -> dict[str, int]:
        """Get current period usage for a tenant.

        Args:
            tenant_id: Tenant to query
            resource_type: Optional filter by resource type

        Returns:
            Dict of resource_type -> count
        """
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        query = self.db.query(UsageCounter).filter(
            UsageCounter.tenant_id == tenant_id,
            UsageCounter.period == period,
        )
        if resource_type:
            query = query.filter(UsageCounter.resource_type == resource_type)

        return {c.resource_type: c.count for c in query.all()}

    def get_events(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        deployment_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[UsageEvent]:
        """Get usage events for audit/billing (tenant-scoped).

        Args:
            tenant_id: Tenant to query
            event_type: Optional filter by event type
            deployment_id: Optional filter by deployment
            since: Optional filter by created_at >= since
            limit: Maximum events to return

        Returns:
            List of usage events, newest first
        """
        query = self.db.query(UsageEvent).filter(UsageEvent.tenant_id == tenant_id)

        if event_type:
            query = query.filter(UsageEvent.event_type == event_type)
        if deployment_id:
            query = query.filter(UsageEvent.deployment_id == deployment_id)
        if since:
            query = query.filter(UsageEvent.created_at >= since)

        return query.order_by(UsageEvent.created_at.desc()).limit(limit).all()

    def get_events_for_billing(
        self,
        tenant_id: str,
        period: str,  # e.g., "2025-01"
    ) -> list[UsageEvent]:
        """Get all events for a billing period.

        Used for generating invoices and reconciliation.

        Args:
            tenant_id: Tenant to query
            period: Billing period (YYYY-MM format)

        Returns:
            All events in the period
        """
        # Parse period to get date range
        year, month = map(int, period.split("-"))
        start = datetime(year, month, 1, tzinfo=timezone.utc)

        # Calculate end of month
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        return (
            self.db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.created_at >= start,
                UsageEvent.created_at < end,
            )
            .order_by(UsageEvent.created_at)
            .all()
        )

