"""Telemetry API routes.

Provides endpoints for:
- Ingesting telemetry batches from CLI/Worker
- Querying traces and spans
- Querying metrics and events
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from runtm_api.auth import get_auth_context
from runtm_api.db import get_db
from runtm_api.services.telemetry import TelemetryService
from runtm_shared.types import AuthContext

router = APIRouter(prefix="/v0/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class SpanData(BaseModel):
    """Span data for ingestion."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    status: str = "unset"
    start_time_ns: int
    end_time_ns: Optional[int] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventData(BaseModel):
    """Event data for ingestion."""

    name: str
    timestamp_ns: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


class MetricData(BaseModel):
    """Metric data for ingestion."""

    name: str
    value: float
    metric_type: str = "counter"
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp_ns: int = 0


class TelemetryBatchRequest(BaseModel):
    """Request model for telemetry batch ingestion."""

    spans: List[SpanData] = Field(default_factory=list)
    events: List[EventData] = Field(default_factory=list)
    metrics: List[MetricData] = Field(default_factory=list)


class IngestResponse(BaseModel):
    """Response model for telemetry ingestion."""

    status: str = "ok"
    spans_ingested: int = 0
    events_ingested: int = 0
    metrics_ingested: int = 0


class SpanResponse(BaseModel):
    """Response model for a span."""

    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    service_name: Optional[str] = None


class EventResponse(BaseModel):
    """Response model for an event."""

    name: str
    timestamp: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    deployment_id: Optional[str] = None
    service_name: Optional[str] = None


class TraceResponse(BaseModel):
    """Response model for a trace."""

    trace_id: str
    spans: List[SpanResponse]
    events: List[EventResponse] = Field(default_factory=list)
    duration_ms: Optional[float] = None
    status: str
    service_name: Optional[str] = None


class TraceSummaryResponse(BaseModel):
    """Response model for a trace summary."""

    trace_id: str
    name: Optional[str] = None
    start_time: Optional[str] = None
    duration_ms: Optional[float] = None
    span_count: int = 0
    service_name: Optional[str] = None


class TracesListResponse(BaseModel):
    """Response model for list of traces."""

    traces: List[TraceSummaryResponse]


class MetricResponse(BaseModel):
    """Response model for a metric."""

    name: str
    metric_type: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: str
    created_at: Optional[str] = None


class MetricsListResponse(BaseModel):
    """Response model for list of metrics."""

    metrics: List[MetricResponse]


class EventsListResponse(BaseModel):
    """Response model for list of events."""

    events: List[EventResponse]


class MetricsSummaryResponse(BaseModel):
    """Response model for metrics summary."""

    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    avg_deploy_time_ms: float = 0.0
    avg_time_to_value_ms: float = 0.0
    commands_by_type: dict[str, int] = Field(default_factory=dict)
    errors_by_type: dict[str, int] = Field(default_factory=dict)
    deployments_by_template: dict[str, int] = Field(default_factory=dict)
    period_days: int = 7


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    batch: TelemetryBatchRequest,
    x_service_name: Optional[str] = Header(None, alias="X-Service-Name"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> IngestResponse:
    """Ingest a batch of telemetry data.

    Accepts spans, events, and metrics in a single batch.
    Used by CLI and Worker to send telemetry to the control plane.

    Headers:
    - X-Service-Name: Optional source service name (e.g., "runtm-cli", "runtm-worker")
    """
    service = TelemetryService(db)

    # Convert batch to dict for service
    batch_dict = batch.model_dump()

    result = service.ingest_batch(
        batch=batch_dict,
        owner_id=auth.owner_id,
        service_name=x_service_name,
    )

    return IngestResponse(
        status="ok",
        spans_ingested=result["spans"],
        events_ingested=result["events"],
        metrics_ingested=result["metrics"],
    )


@router.get("/traces", response_model=TracesListResponse)
async def list_traces(
    limit: int = Query(50, ge=1, le=100),
    service_name: Optional[str] = Query(None, alias="service"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TracesListResponse:
    """List recent traces.

    Query params:
    - limit: Maximum number of traces (default: 50, max: 100)
    - service: Filter by service name
    """
    service = TelemetryService(db)

    traces = service.get_recent_traces(
        owner_id=auth.owner_id,
        limit=limit,
        service_name=service_name,
    )

    return TracesListResponse(
        traces=[TraceSummaryResponse(**t) for t in traces]
    )


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TraceResponse:
    """Get a full trace with all spans and events.

    Returns the complete trace including all spans and any events
    attached to the trace.
    """
    service = TelemetryService(db)

    trace = service.get_trace(
        trace_id=trace_id,
        owner_id=auth.owner_id,
    )

    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": f"Trace not found: {trace_id}"},
        )

    return TraceResponse(
        trace_id=trace["trace_id"],
        spans=[SpanResponse(**s) for s in trace["spans"]],
        events=[EventResponse(**e) for e in trace.get("events", [])],
        duration_ms=trace.get("duration_ms"),
        status=trace["status"],
        service_name=trace.get("service_name"),
    )


@router.get("/metrics", response_model=MetricsListResponse)
async def list_metrics(
    name: Optional[str] = Query(None),
    metric_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MetricsListResponse:
    """List raw metrics.

    Query params:
    - name: Filter by metric name
    - type: Filter by metric type (counter, histogram, gauge)
    - limit: Maximum number of metrics (default: 100, max: 500)
    """
    service = TelemetryService(db)

    metrics = service.get_metrics(
        name=name,
        metric_type=metric_type,
        owner_id=auth.owner_id,
        limit=limit,
    )

    return MetricsListResponse(
        metrics=[MetricResponse(**m) for m in metrics]
    )


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MetricsSummaryResponse:
    """Get aggregated metrics summary for dashboard.

    Returns summary statistics including:
    - Deployment counts (total, successful, failed)
    - Average deployment time
    - Command counts by type
    - Error counts by type
    - Deployments by template

    Query params:
    - days: Number of days to look back (default: 7, max: 90)
    """
    service = TelemetryService(db)

    summary = service.get_metrics_summary(
        owner_id=auth.owner_id,
        days=days,
    )

    return MetricsSummaryResponse(**summary)


@router.get("/events", response_model=EventsListResponse)
async def list_events(
    name: Optional[str] = Query(None),
    deployment_id: Optional[str] = Query(None, alias="deployment"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> EventsListResponse:
    """List telemetry events.

    Query params:
    - name: Filter by event name
    - deployment: Filter by deployment ID
    - limit: Maximum number of events (default: 100, max: 500)
    """
    service = TelemetryService(db)

    events = service.get_events(
        name=name,
        deployment_id=deployment_id,
        owner_id=auth.owner_id,
        limit=limit,
    )

    return EventsListResponse(
        events=[EventResponse(**e) for e in events]
    )


# =============================================================================
# Deployment-specific trace endpoint (added to deployments router scope)
# =============================================================================


@router.get("/deployments/{deployment_id}/traces", response_model=TracesListResponse)
async def get_deployment_traces(
    deployment_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TracesListResponse:
    """Get traces for a specific deployment.

    Returns traces that have spans linked to this deployment.

    Query params:
    - limit: Maximum number of traces (default: 50, max: 100)
    """
    service = TelemetryService(db)

    traces = service.get_traces_for_deployment(
        deployment_id=deployment_id,
        owner_id=auth.owner_id,
        limit=limit,
    )

    return TracesListResponse(
        traces=[TraceSummaryResponse(**t) for t in traces]
    )

