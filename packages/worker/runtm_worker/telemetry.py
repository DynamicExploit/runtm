"""Worker telemetry integration.

Provides telemetry for the worker with:
- Trace context propagation from API
- Span creation for build/deploy phases
- Events for worker lifecycle
- Metrics for build/deploy performance

The worker sends telemetry to the control plane API for storage and
dashboard visualization.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from runtm_shared.telemetry import (
    BaseExporter,
    EventType,
    SpanManager,
    TelemetryConfig,
    TelemetryService,
    TelemetrySpan,
    create_controlplane_exporter,
    create_exporter,
)

# Global telemetry service instance
_telemetry: Optional[TelemetryService] = None


def get_telemetry() -> TelemetryService:
    """Get the global telemetry service instance.

    Returns:
        The telemetry service

    Raises:
        RuntimeError: If telemetry not initialized
    """
    if _telemetry is None:
        raise RuntimeError("Telemetry not initialized. Call init_telemetry() first.")
    return _telemetry


def init_telemetry(
    endpoint: Optional[str] = None,
    debug: bool = False,
    disabled: bool = False,
    api_url: Optional[str] = None,
    api_token: Optional[str] = None,
) -> TelemetryService:
    """Initialize the worker telemetry service.

    Call this during worker startup.

    Args:
        endpoint: Custom OTLP endpoint (overrides control plane exporter)
        debug: Enable console output
        disabled: Disable telemetry entirely
        api_url: Control plane API URL (for ControlPlaneExporter)
        api_token: API token for authentication

    Returns:
        Configured TelemetryService
    """
    global _telemetry

    config = TelemetryConfig.from_env()
    config.service_name = "runtm-worker"

    # Determine API URL and token from args or environment
    api_url = api_url or os.environ.get("RUNTM_API_URL", "http://api:8000")
    api_token = api_token or os.environ.get("RUNTM_API_TOKEN", "dev-token")

    # Create exporter based on configuration
    if disabled or not config.enabled:
        exporter = create_exporter(disabled=True)
    elif debug or config.debug:
        exporter = create_exporter(debug=True)
    elif endpoint or config.endpoint:
        # Custom endpoint specified - use OTLP exporter
        exporter = create_exporter(
            endpoint=endpoint or config.endpoint,
            token=api_token,
        )
    else:
        # Default - send telemetry to control plane API
        exporter = create_controlplane_exporter(
            api_url=api_url,
            token=api_token,
            service_name="runtm-worker",
        )

    _telemetry = TelemetryService(exporter=exporter, config=config)
    _telemetry.start()

    return _telemetry


def shutdown_telemetry() -> None:
    """Shutdown the telemetry service.

    Call this during worker shutdown.
    """
    global _telemetry
    if _telemetry is not None:
        _telemetry.shutdown()
        _telemetry = None


# === Trace Context Propagation ===

def start_job_span(
    job_name: str,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    attributes: Optional[dict[str, Any]] = None,
) -> TelemetrySpan:
    """Start a span for a worker job, optionally continuing a trace.

    Args:
        job_name: Name of the job
        trace_id: Trace ID from API (for continuation)
        parent_span_id: Parent span ID from API
        attributes: Additional span attributes

    Returns:
        The created span
    """
    telemetry = get_telemetry()
    span = telemetry.start_span(job_name, attributes)

    # If we have trace context from API, we could update the span
    # For now, we just record it as attributes
    if trace_id:
        span.set_attribute("runtm.parent_trace_id", trace_id)
    if parent_span_id:
        span.set_attribute("runtm.parent_span_id", parent_span_id)

    return span


# === Event Helpers ===

def emit_build_started(deployment_id: str) -> None:
    """Emit build started event.

    Args:
        deployment_id: The deployment ID
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.WORKER_BUILD_STARTED,
        {"deployment_id": deployment_id},
    )


def emit_build_completed(deployment_id: str, duration_ms: float) -> None:
    """Emit build completed event.

    Args:
        deployment_id: The deployment ID
        duration_ms: Build duration in milliseconds
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.WORKER_BUILD_COMPLETED,
        {"deployment_id": deployment_id, "duration_ms": duration_ms},
    )


def emit_deploy_started(deployment_id: str) -> None:
    """Emit deploy started event.

    Args:
        deployment_id: The deployment ID
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.WORKER_DEPLOY_STARTED,
        {"deployment_id": deployment_id},
    )


def emit_deploy_completed(deployment_id: str, duration_ms: float) -> None:
    """Emit deploy completed event.

    Args:
        deployment_id: The deployment ID
        duration_ms: Deploy duration in milliseconds
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.WORKER_DEPLOY_COMPLETED,
        {"deployment_id": deployment_id, "duration_ms": duration_ms},
    )


def emit_deploy_failed(deployment_id: str, error_type: str) -> None:
    """Emit deploy failed event.

    Args:
        deployment_id: The deployment ID
        error_type: Type of error
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.WORKER_DEPLOY_FAILED,
        {"deployment_id": deployment_id, "error_type": error_type},
    )

