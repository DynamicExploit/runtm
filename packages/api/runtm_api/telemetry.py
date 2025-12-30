"""API telemetry integration (scaffold).

Provides telemetry for the API control plane with:
- Trace context extraction from incoming requests
- Span creation for API operations
- Events for deployment lifecycle
- Metrics for API performance

TODO: Full implementation pending. This scaffold provides the interface
for future implementation with FastAPI middleware integration.
"""

from __future__ import annotations

from typing import Any, Optional

from runtm_shared.telemetry import (
    BaseExporter,
    EventType,
    SpanManager,
    TelemetryConfig,
    TelemetryService,
    create_exporter,
)

# Global telemetry service instance (initialized in app startup)
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
) -> TelemetryService:
    """Initialize the API telemetry service.

    Call this during FastAPI app startup.

    Args:
        endpoint: Custom OTLP endpoint
        debug: Enable console output
        disabled: Disable telemetry entirely

    Returns:
        Configured TelemetryService
    """
    global _telemetry

    config = TelemetryConfig.from_env()
    config.service_name = "runtm-api"

    exporter = create_exporter(
        endpoint=endpoint or config.endpoint,
        debug=debug or config.debug,
        disabled=disabled or not config.enabled,
    )

    _telemetry = TelemetryService(exporter=exporter, config=config)
    _telemetry.start()

    return _telemetry


def shutdown_telemetry() -> None:
    """Shutdown the telemetry service.

    Call this during FastAPI app shutdown.
    """
    global _telemetry
    if _telemetry is not None:
        _telemetry.shutdown()
        _telemetry = None


# === Middleware Support ===

def extract_trace_context(traceparent: Optional[str]) -> Optional[tuple[str, str]]:
    """Extract trace context from incoming request.

    Args:
        traceparent: W3C traceparent header value

    Returns:
        Tuple of (trace_id, parent_span_id) or None
    """
    return SpanManager.parse_traceparent(traceparent) if traceparent else None


# === Event Helpers ===

def emit_deployment_created(deployment_id: str) -> None:
    """Emit deployment created event.

    Args:
        deployment_id: The deployment ID
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.CONTROLPLANE_DEPLOYMENT_CREATED,
        {"deployment_id": deployment_id},
    )


def emit_deployment_failed(deployment_id: str, error_type: str) -> None:
    """Emit deployment failed event.

    Args:
        deployment_id: The deployment ID
        error_type: Type of error
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.CONTROLPLANE_DEPLOYMENT_FAILED,
        {"deployment_id": deployment_id, "error_type": error_type},
    )


def emit_artifact_upload(deployment_id: str, size_bytes: int, duration_ms: float) -> None:
    """Emit artifact upload completed event.

    Args:
        deployment_id: The deployment ID
        size_bytes: Artifact size in bytes
        duration_ms: Upload duration in milliseconds
    """
    telemetry = get_telemetry()
    telemetry.emit_event(
        EventType.ARTIFACT_UPLOAD_COMPLETED,
        {
            "deployment_id": deployment_id,
            "artifact_size_mb": size_bytes / (1024 * 1024),
            "duration_ms": duration_ms,
        },
    )

