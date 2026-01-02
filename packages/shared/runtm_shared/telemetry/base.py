"""Base models and protocols for telemetry.

Defines TelemetryEvent, TelemetrySpan, and TelemetryExporter protocol.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


class SpanStatus(Enum):
    """Status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class EventType(Enum):
    """Type of telemetry event."""

    # Lifecycle events
    FIRST_RUN = "cli.first_run"
    UPGRADE = "cli.upgrade"
    CONFIG_LOADED = "cli.config.loaded"

    # Auth events
    LOGIN_STARTED = "cli.login.started"
    LOGIN_COMPLETED = "cli.login.completed"
    AUTH_FAILED = "cli.auth.failed"

    # Init events
    INIT_TEMPLATE_SELECTED = "cli.init.template_selected"
    INIT_COMPLETED = "cli.init.completed"

    # Deploy events
    DEPLOY_STARTED = "cli.deploy.started"
    DEPLOY_VALIDATION_FAILED = "cli.deploy.validation_failed"
    DEPLOY_COMPLETED = "cli.deploy.completed"
    DEPLOY_FAILED = "cli.deploy.failed"

    # Destroy events
    DESTROY_COMPLETED = "cli.destroy.completed"

    # Run events
    RUN_STARTED = "cli.run.started"
    RUN_COMPLETED = "cli.run.completed"

    # Domain events
    DOMAIN_ADDED = "cli.domain.added"
    DOMAIN_REMOVED = "cli.domain.removed"

    # Phase events (inside spans)
    PHASE_STARTED = "runtm.phase.started"
    PHASE_COMPLETED = "runtm.phase.completed"
    PHASE_FAILED = "runtm.phase.failed"

    # Server-side events (for API/Worker)
    CONTROLPLANE_DEPLOYMENT_CREATED = "controlplane.deployment.created"
    CONTROLPLANE_DEPLOYMENT_FAILED = "controlplane.deployment.failed"
    WORKER_BUILD_STARTED = "worker.build.started"
    WORKER_BUILD_COMPLETED = "worker.build.completed"
    WORKER_DEPLOY_STARTED = "worker.deploy.started"
    WORKER_DEPLOY_COMPLETED = "worker.deploy.completed"
    WORKER_DEPLOY_FAILED = "worker.deploy.failed"
    ARTIFACT_UPLOAD_COMPLETED = "artifact.upload.completed"


# Allowed attribute keys (for privacy enforcement)
ALLOWED_SPAN_ATTRIBUTES = frozenset(
    {
        # Command attributes (low-cardinality)
        "runtm.command.name",
        "runtm.command.exit_code",
        "runtm.template",
        "runtm.tier",
        "runtm.runtime",
        # Identity (for correlation, not metrics)
        "runtm.install_id",
        "runtm.session_id",
        # Phase
        "runtm.phase",
        # Error type (low-cardinality categories)
        "runtm.error_type",
    }
)

ALLOWED_EVENT_ATTRIBUTES = frozenset(
    {
        # Identifiers
        "install_id",
        "session_id",
        "cli_version",
        # System info
        "os",
        "arch",
        "python_version",
        # Version
        "from_version",
        "to_version",
        # Config
        "config_source",
        # Auth
        "auth_method",
        "error_type",
        # Template/deploy
        "template",
        "has_existing_files",
        "is_redeploy",
        "tier",
        "artifact_size_mb",
        "error_count",
        "warning_count",
        "duration_ms",
        "version",
        "state_reached",
        # Run
        "runtime",
        "has_bun",
        # Domain
        "has_ssl",
        # Phase
        "phase",
        # Outcome
        "outcome",
        # Deployment ID (trace field only, not for metrics)
        "deployment_id",
    }
)


def _time_ns() -> int:
    """Get current time in nanoseconds."""
    return time.time_ns()


@dataclass
class TelemetryEvent:
    """A telemetry event to be exported.

    Events are discrete occurrences with a timestamp and attributes.
    They are typically attached to spans for context.
    """

    name: str
    timestamp_ns: int = field(default_factory=_time_ns)
    attributes: dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate attributes against allowlist."""
        self.attributes = {
            k: v for k, v in self.attributes.items() if k in ALLOWED_EVENT_ATTRIBUTES
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "timestamp_ns": self.timestamp_ns,
            "attributes": self.attributes,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryEvent:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            timestamp_ns=data.get("timestamp_ns", time.time_ns()),
            attributes=data.get("attributes", {}),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
        )


@dataclass
class TelemetrySpan:
    """A telemetry span representing an operation.

    Spans have a start time, end time, and can contain child spans and events.
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time_ns: int = field(default_factory=_time_ns)
    end_time_ns: Optional[int] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[TelemetryEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate attributes against allowlist."""
        self.attributes = {k: v for k, v in self.attributes.items() if k in ALLOWED_SPAN_ATTRIBUTES}

    def end(self, status: SpanStatus = SpanStatus.OK) -> None:
        """End the span with a status."""
        self.end_time_ns = time.time_ns()
        self.status = status

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        event = TelemetryEvent(
            name=name,
            attributes=attributes or {},
            trace_id=self.trace_id,
            span_id=self.span_id,
        )
        self.events.append(event)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute (if allowed)."""
        if key in ALLOWED_SPAN_ATTRIBUTES:
            self.attributes[key] = value

    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.end_time_ns is None:
            return None
        return (self.end_time_ns - self.start_time_ns) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetrySpan:
        """Create from dictionary."""
        span = cls(
            name=data["name"],
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            start_time_ns=data.get("start_time_ns", time.time_ns()),
            end_time_ns=data.get("end_time_ns"),
            status=SpanStatus(data.get("status", "unset")),
            attributes=data.get("attributes", {}),
        )
        for event_data in data.get("events", []):
            span.events.append(TelemetryEvent.from_dict(event_data))
        return span


@dataclass
class TelemetryMetric:
    """A telemetry metric data point."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp_ns: int = field(default_factory=_time_ns)
    metric_type: str = "counter"  # counter, histogram, gauge

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp_ns": self.timestamp_ns,
            "metric_type": self.metric_type,
        }


@dataclass
class TelemetryBatch:
    """A batch of telemetry data to export."""

    spans: list[TelemetrySpan] = field(default_factory=list)
    events: list[TelemetryEvent] = field(default_factory=list)
    metrics: list[TelemetryMetric] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if the batch is empty."""
        return not self.spans and not self.events and not self.metrics

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "spans": [s.to_dict() for s in self.spans],
            "events": [e.to_dict() for e in self.events],
            "metrics": [m.to_dict() for m in self.metrics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryBatch:
        """Create from dictionary."""
        return cls(
            spans=[TelemetrySpan.from_dict(s) for s in data.get("spans", [])],
            events=[TelemetryEvent.from_dict(e) for e in data.get("events", [])],
            metrics=[
                TelemetryMetric(
                    name=m["name"],
                    value=m["value"],
                    labels=m.get("labels", {}),
                    timestamp_ns=m.get("timestamp_ns", time.time_ns()),
                    metric_type=m.get("metric_type", "counter"),
                )
                for m in data.get("metrics", [])
            ],
        )


@runtime_checkable
class TelemetryExporter(Protocol):
    """Protocol for telemetry exporters.

    Exporters are responsible for sending telemetry data to a backend.
    """

    def export(self, batch: TelemetryBatch) -> bool:
        """Export a batch of telemetry data.

        Args:
            batch: The telemetry batch to export

        Returns:
            True if export succeeded, False otherwise
        """

    def shutdown(self) -> None:
        """Shutdown the exporter, flushing any remaining data."""


class BaseExporter(ABC):
    """Abstract base class for telemetry exporters."""

    @abstractmethod
    def export(self, batch: TelemetryBatch) -> bool:
        """Export a batch of telemetry data."""

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the exporter."""
