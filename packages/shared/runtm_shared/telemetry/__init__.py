"""Telemetry module for Runtm.

Provides production-grade telemetry with:
- Identity management (install_id, session_id)
- Distributed tracing with spans
- Metrics (counters, histograms)
- Batched export with backpressure
- Disk spooling for reliability
- Multiple exporters (OTLP, Console, Noop)
"""

from runtm_shared.telemetry.base import (
    ALLOWED_EVENT_ATTRIBUTES,
    ALLOWED_SPAN_ATTRIBUTES,
    BaseExporter,
    EventType,
    SpanStatus,
    TelemetryBatch,
    TelemetryEvent,
    TelemetryExporter,
    TelemetryMetric,
    TelemetrySpan,
)
from runtm_shared.telemetry.exporter import (
    BatchExporter,
    ExporterConfig,
)
from runtm_shared.telemetry.identity import (
    IdentityManager,
    TelemetryIdentity,
)
from runtm_shared.telemetry.metrics import (
    Counter,
    Histogram,
    MetricsManager,
    MetricsRegistry,
)
from runtm_shared.telemetry.providers import (
    BufferedFileExporter,
    ConsoleExporter,
    ControlPlaneExporter,
    NoopExporter,
    OTLPExporter,
    create_controlplane_exporter,
    create_exporter,
)
from runtm_shared.telemetry.service import (
    TelemetryConfig,
    TelemetryService,
    create_command_span_attributes,
)
from runtm_shared.telemetry.spans import (
    SpanManager,
    generate_span_id,
    generate_trace_id,
)
from runtm_shared.telemetry.spool import (
    DiskSpool,
    SpoolConfig,
)

__all__ = [
    # Base types
    "TelemetryEvent",
    "TelemetrySpan",
    "TelemetryMetric",
    "TelemetryBatch",
    "TelemetryExporter",
    "BaseExporter",
    "SpanStatus",
    "EventType",
    "ALLOWED_EVENT_ATTRIBUTES",
    "ALLOWED_SPAN_ATTRIBUTES",
    # Identity
    "IdentityManager",
    "TelemetryIdentity",
    # Spans
    "SpanManager",
    "generate_trace_id",
    "generate_span_id",
    # Metrics
    "Counter",
    "Histogram",
    "MetricsManager",
    "MetricsRegistry",
    # Exporter
    "BatchExporter",
    "ExporterConfig",
    # Spool
    "DiskSpool",
    "SpoolConfig",
    # Providers
    "NoopExporter",
    "ConsoleExporter",
    "OTLPExporter",
    "BufferedFileExporter",
    "ControlPlaneExporter",
    "create_exporter",
    "create_controlplane_exporter",
    # Service
    "TelemetryConfig",
    "TelemetryService",
    "create_command_span_attributes",
]
