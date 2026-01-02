"""Telemetry service layer.

Provides services for:
- Ingesting telemetry batches from CLI/Worker
- Querying traces and spans
- Aggregating and querying metrics
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import Float, and_, func
from sqlalchemy.orm import Session

from runtm_api.db import TelemetryEvent, TelemetryMetric, TelemetrySpan

logger = logging.getLogger(__name__)


class TelemetryService:
    """Service for telemetry operations."""

    def __init__(self, db: Session) -> None:
        """Initialize the telemetry service.

        Args:
            db: Database session
        """
        self._db = db

    # =========================================================================
    # Ingestion
    # =========================================================================

    def ingest_batch(
        self,
        batch: dict[str, Any],
        owner_id: Optional[str] = None,
        service_name: Optional[str] = None,
    ) -> dict[str, int]:
        """Ingest a telemetry batch.

        Args:
            batch: Telemetry batch with spans, events, and metrics
            owner_id: Owner ID for multi-tenant mode
            service_name: Source service name

        Returns:
            Dict with counts of ingested items
        """
        spans_count = 0
        events_count = 0
        metrics_count = 0

        # Ingest spans
        for span_data in batch.get("spans", []):
            try:
                span = TelemetrySpan(
                    trace_id=span_data["trace_id"],
                    span_id=span_data["span_id"],
                    parent_span_id=span_data.get("parent_span_id"),
                    name=span_data["name"],
                    status=span_data.get("status", "unset"),
                    start_time_ns=span_data["start_time_ns"],
                    end_time_ns=span_data.get("end_time_ns"),
                    attributes=span_data.get("attributes", {}),
                    deployment_id=self._extract_deployment_id(span_data),
                    service_name=service_name,
                    owner_id=owner_id,
                )
                self._db.add(span)
                spans_count += 1
            except Exception as e:
                logger.warning("Failed to ingest span: %s", e)

        # Ingest events
        for event_data in batch.get("events", []):
            try:
                event = TelemetryEvent(
                    name=event_data["name"],
                    timestamp_ns=event_data.get("timestamp_ns", 0),
                    attributes=event_data.get("attributes", {}),
                    trace_id=event_data.get("trace_id"),
                    span_id=event_data.get("span_id"),
                    deployment_id=self._extract_deployment_id(event_data),
                    service_name=service_name,
                    owner_id=owner_id,
                )
                self._db.add(event)
                events_count += 1
            except Exception as e:
                logger.warning("Failed to ingest event: %s", e)

        # Ingest metrics
        for metric_data in batch.get("metrics", []):
            try:
                metric = TelemetryMetric(
                    name=metric_data["name"],
                    metric_type=metric_data.get("metric_type", "counter"),
                    value=metric_data["value"],
                    labels=metric_data.get("labels", {}),
                    timestamp_ns=metric_data.get("timestamp_ns", 0),
                    bucket_period="raw",
                    service_name=service_name,
                    owner_id=owner_id,
                )
                self._db.add(metric)
                metrics_count += 1
            except Exception as e:
                logger.warning("Failed to ingest metric: %s", e)

        self._db.commit()

        return {
            "spans": spans_count,
            "events": events_count,
            "metrics": metrics_count,
        }

    def _extract_deployment_id(self, data: dict[str, Any]) -> Optional[str]:
        """Extract deployment_id from attributes if present.

        Args:
            data: Span or event data

        Returns:
            Deployment ID if found
        """
        attributes = data.get("attributes", {})
        return attributes.get("deployment_id")

    # =========================================================================
    # Trace Queries
    # =========================================================================

    def get_trace(
        self,
        trace_id: str,
        owner_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get a full trace with all spans.

        Args:
            trace_id: Trace ID
            owner_id: Owner ID for filtering

        Returns:
            Trace with spans or None if not found
        """
        query = self._db.query(TelemetrySpan).filter(TelemetrySpan.trace_id == trace_id)

        if owner_id:
            query = query.filter(TelemetrySpan.owner_id == owner_id)

        spans = query.order_by(TelemetrySpan.start_time_ns).all()

        if not spans:
            return None

        # Get events for this trace
        events_query = self._db.query(TelemetryEvent).filter(TelemetryEvent.trace_id == trace_id)
        if owner_id:
            events_query = events_query.filter(TelemetryEvent.owner_id == owner_id)
        events = events_query.order_by(TelemetryEvent.timestamp_ns).all()

        # Build trace response
        root_span = next((s for s in spans if s.parent_span_id is None), spans[0])
        duration_ms = root_span.duration_ms if root_span else None

        # Determine overall status
        statuses = [s.status for s in spans]
        overall_status = "error" if "error" in statuses else "ok"

        return {
            "trace_id": trace_id,
            "spans": [self._span_to_dict(s) for s in spans],
            "events": [self._event_to_dict(e) for e in events],
            "duration_ms": duration_ms,
            "status": overall_status,
            "service_name": root_span.service_name if root_span else None,
        }

    def get_traces_for_deployment(
        self,
        deployment_id: str,
        owner_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get traces for a specific deployment.

        Args:
            deployment_id: Deployment ID
            owner_id: Owner ID for filtering
            limit: Maximum number of traces

        Returns:
            List of trace summaries
        """
        # Get unique trace IDs for this deployment
        query = self._db.query(
                TelemetrySpan.trace_id,
                func.min(TelemetrySpan.start_time_ns).label("start_time"),
                func.max(TelemetrySpan.end_time_ns).label("end_time"),
                func.count(TelemetrySpan.id).label("span_count"),
        ).filter(TelemetrySpan.deployment_id == deployment_id)

        if owner_id:
            query = query.filter(TelemetrySpan.owner_id == owner_id)

        # Apply grouping, ordering, and limit AFTER all filters
        query = (
            query.group_by(TelemetrySpan.trace_id)
            .order_by(func.min(TelemetrySpan.start_time_ns).desc())
            .limit(limit)
        )

        traces = query.all()

        result = []
        for trace in traces:
            duration_ms = None
            if trace.start_time and trace.end_time:
                duration_ms = (trace.end_time - trace.start_time) / 1_000_000

            result.append(
                {
                    "trace_id": trace.trace_id,
                    "start_time": datetime.fromtimestamp(trace.start_time / 1e9).isoformat()
                    if trace.start_time
                    else None,
                    "duration_ms": duration_ms,
                    "span_count": trace.span_count,
                }
            )

        return result

    def get_recent_traces(
        self,
        owner_id: Optional[str] = None,
        limit: int = 50,
        service_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get recent traces.

        Args:
            owner_id: Owner ID for filtering
            limit: Maximum number of traces
            service_name: Filter by service name

        Returns:
            List of trace summaries
        """
        query = self._db.query(
                TelemetrySpan.trace_id,
                func.min(TelemetrySpan.name).label("root_name"),
                func.min(TelemetrySpan.start_time_ns).label("start_time"),
                func.max(TelemetrySpan.end_time_ns).label("end_time"),
                func.count(TelemetrySpan.id).label("span_count"),
                func.min(TelemetrySpan.service_name).label("service"),
        )

        if owner_id:
            query = query.filter(TelemetrySpan.owner_id == owner_id)

        if service_name:
            query = query.filter(TelemetrySpan.service_name == service_name)

        # Apply grouping, ordering, and limit AFTER all filters
        query = (
            query.group_by(TelemetrySpan.trace_id)
            .order_by(func.min(TelemetrySpan.start_time_ns).desc())
            .limit(limit)
        )

        traces = query.all()

        result = []
        for trace in traces:
            duration_ms = None
            if trace.start_time and trace.end_time:
                duration_ms = (trace.end_time - trace.start_time) / 1_000_000

            result.append(
                {
                    "trace_id": trace.trace_id,
                    "name": trace.root_name,
                    "start_time": datetime.fromtimestamp(trace.start_time / 1e9).isoformat()
                    if trace.start_time
                    else None,
                    "duration_ms": duration_ms,
                    "span_count": trace.span_count,
                    "service_name": trace.service,
                }
            )

        return result

    # =========================================================================
    # Metrics Queries
    # =========================================================================

    def get_metrics_summary(
        self,
        owner_id: Optional[str] = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get aggregated metrics summary for dashboard.

        Args:
            owner_id: Owner ID for filtering
            days: Number of days to look back

        Returns:
            Summary metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Base query filter
        base_filter = TelemetryMetric.created_at >= cutoff
        if owner_id:
            base_filter = and_(base_filter, TelemetryMetric.owner_id == owner_id)

        # Count commands by type
        commands_query = (
            self._db.query(
                TelemetryMetric.labels["command"].astext.label("command"),
                func.sum(TelemetryMetric.value).label("count"),
            )
            .filter(base_filter)
            .filter(TelemetryMetric.name == "runtm_cli_commands_total")
            .group_by(TelemetryMetric.labels["command"].astext)
        )
        commands_by_type = {
            row.command: int(row.count) for row in commands_query.all() if row.command
        }

        # Count errors by type
        errors_query = (
            self._db.query(
                TelemetryMetric.labels["error_type"].astext.label("error_type"),
                func.sum(TelemetryMetric.value).label("count"),
            )
            .filter(base_filter)
            .filter(TelemetryMetric.name == "runtm_cli_errors_total")
            .group_by(TelemetryMetric.labels["error_type"].astext)
        )
        errors_by_type = {
            row.error_type: int(row.count) for row in errors_query.all() if row.error_type
        }

        # Get deployment counts from events
        events_filter = TelemetryEvent.created_at >= cutoff
        if owner_id:
            events_filter = and_(events_filter, TelemetryEvent.owner_id == owner_id)

        deploy_events = (
            self._db.query(
                TelemetryEvent.name,
                func.count(TelemetryEvent.id).label("count"),
            )
            .filter(events_filter)
            .filter(
                TelemetryEvent.name.in_(
                    [
                        "cli.deploy.completed",
                        "cli.deploy.failed",
                        "cli.deploy.started",
                    ]
                )
            )
            .group_by(TelemetryEvent.name)
        )
        deploy_counts = {row.name: row.count for row in deploy_events.all()}

        # Get deployments by template (from started events to count all attempts)
        template_query = (
            self._db.query(
                TelemetryEvent.attributes["template"].astext.label("template"),
                func.count(TelemetryEvent.id).label("count"),
            )
            .filter(events_filter)
            .filter(TelemetryEvent.name == "cli.deploy.started")
            .group_by(TelemetryEvent.attributes["template"].astext)
        )
        deployments_by_template = {
            row.template: row.count for row in template_query.all() if row.template
        }

        # Calculate average deploy duration
        duration_query = (
            self._db.query(func.avg(TelemetryEvent.attributes["duration_ms"].astext.cast(Float)))
            .filter(events_filter)
            .filter(TelemetryEvent.name == "cli.deploy.completed")
            .filter(TelemetryEvent.attributes["duration_ms"].isnot(None))
        )
        avg_duration = duration_query.scalar() or 0.0

        # Calculate avg time-to-value (init to first deploy)
        # This looks for pairs of init.completed and deploy.completed events
        # with matching templates
        avg_time_to_value_ms = self._calculate_avg_time_to_value(owner_id, cutoff)

        return {
            "total_deployments": deploy_counts.get("cli.deploy.started", 0),
            "successful_deployments": deploy_counts.get("cli.deploy.completed", 0),
            "failed_deployments": deploy_counts.get("cli.deploy.failed", 0),
            "avg_deploy_time_ms": round(avg_duration, 2),
            "avg_time_to_value_ms": round(avg_time_to_value_ms, 2),
            "commands_by_type": commands_by_type,
            "errors_by_type": errors_by_type,
            "deployments_by_template": deployments_by_template,
            "period_days": days,
        }

    def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get raw metrics.

        Args:
            name: Filter by metric name
            metric_type: Filter by metric type
            owner_id: Owner ID for filtering
            limit: Maximum number of metrics

        Returns:
            List of metrics
        """
        query = self._db.query(TelemetryMetric)

        if name:
            query = query.filter(TelemetryMetric.name == name)
        if metric_type:
            query = query.filter(TelemetryMetric.metric_type == metric_type)
        if owner_id:
            query = query.filter(TelemetryMetric.owner_id == owner_id)

        metrics = query.order_by(TelemetryMetric.created_at.desc()).limit(limit).all()

        return [
            {
                "name": m.name,
                "metric_type": m.metric_type,
                "value": m.value,
                "labels": m.labels,
                "timestamp": datetime.fromtimestamp(m.timestamp_ns / 1e9).isoformat(),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in metrics
        ]

    def get_events(
        self,
        name: Optional[str] = None,
        deployment_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get telemetry events.

        Args:
            name: Filter by event name
            deployment_id: Filter by deployment ID
            owner_id: Owner ID for filtering
            limit: Maximum number of events

        Returns:
            List of events
        """
        query = self._db.query(TelemetryEvent)

        if name:
            query = query.filter(TelemetryEvent.name == name)
        if deployment_id:
            query = query.filter(TelemetryEvent.deployment_id == deployment_id)
        if owner_id:
            query = query.filter(TelemetryEvent.owner_id == owner_id)

        events = query.order_by(TelemetryEvent.created_at.desc()).limit(limit).all()

        return [self._event_to_dict(e) for e in events]

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup_old_data(
        self,
        spans_days: int = 7,
        events_days: int = 7,
        metrics_days: int = 30,
    ) -> dict[str, int]:
        """Clean up old telemetry data.

        Args:
            spans_days: Delete spans older than this
            events_days: Delete events older than this
            metrics_days: Delete metrics older than this

        Returns:
            Dict with counts of deleted items
        """
        now = datetime.utcnow()

        # Delete old spans
        spans_cutoff = now - timedelta(days=spans_days)
        spans_deleted = (
            self._db.query(TelemetrySpan).filter(TelemetrySpan.created_at < spans_cutoff).delete()
        )

        # Delete old events
        events_cutoff = now - timedelta(days=events_days)
        events_deleted = (
            self._db.query(TelemetryEvent)
            .filter(TelemetryEvent.created_at < events_cutoff)
            .delete()
        )

        # Delete old metrics
        metrics_cutoff = now - timedelta(days=metrics_days)
        metrics_deleted = (
            self._db.query(TelemetryMetric)
            .filter(TelemetryMetric.created_at < metrics_cutoff)
            .delete()
        )

        self._db.commit()

        return {
            "spans_deleted": spans_deleted,
            "events_deleted": events_deleted,
            "metrics_deleted": metrics_deleted,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _calculate_avg_time_to_value(
        self,
        owner_id: Optional[str],
        cutoff: datetime,
    ) -> float:
        """Calculate average time from init to first successful deploy.

        This measures the "time to value" - how long it takes users to go
        from initializing a project to having it deployed.

        Args:
            owner_id: Owner ID for filtering
            cutoff: Cutoff date for events

        Returns:
            Average time in milliseconds (0 if no data)
        """
        # Get init events
        events_filter = TelemetryEvent.created_at >= cutoff
        if owner_id:
            events_filter = and_(events_filter, TelemetryEvent.owner_id == owner_id)

        init_events = (
            self._db.query(TelemetryEvent)
            .filter(events_filter)
            .filter(TelemetryEvent.name == "cli.init.completed")
            .order_by(TelemetryEvent.created_at)
            .all()
        )

        deploy_events = (
            self._db.query(TelemetryEvent)
            .filter(events_filter)
            .filter(TelemetryEvent.name == "cli.deploy.completed")
            .order_by(TelemetryEvent.created_at)
            .all()
        )

        if not init_events or not deploy_events:
            return 0.0

        # Calculate time differences for matching template pairs
        time_diffs = []

        for init_event in init_events:
            init_template = init_event.attributes.get("template")
            init_time = init_event.created_at

            # Find the first deploy after this init with matching template
            for deploy_event in deploy_events:
                deploy_template = deploy_event.attributes.get("template")
                deploy_time = deploy_event.created_at

                if deploy_time > init_time:
                    # Template match or no template info (fallback)
                    if init_template == deploy_template or not init_template or not deploy_template:
                        diff_ms = (deploy_time - init_time).total_seconds() * 1000
                        # Only count reasonable durations (< 1 hour for init-to-deploy)
                        if diff_ms < 3600000:
                            time_diffs.append(diff_ms)
                        break

        if not time_diffs:
            return 0.0

        return sum(time_diffs) / len(time_diffs)

    def _span_to_dict(self, span: TelemetrySpan) -> dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "status": span.status,
            "start_time": datetime.fromtimestamp(span.start_time_ns / 1e9).isoformat(),
            "end_time": datetime.fromtimestamp(span.end_time_ns / 1e9).isoformat()
            if span.end_time_ns
            else None,
            "duration_ms": span.duration_ms,
            "attributes": span.attributes,
            "service_name": span.service_name,
        }

    def _event_to_dict(self, event: TelemetryEvent) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "name": event.name,
            "timestamp": datetime.fromtimestamp(event.timestamp_ns / 1e9).isoformat(),
            "attributes": event.attributes,
            "trace_id": event.trace_id,
            "span_id": event.span_id,
            "deployment_id": event.deployment_id,
            "service_name": event.service_name,
        }
