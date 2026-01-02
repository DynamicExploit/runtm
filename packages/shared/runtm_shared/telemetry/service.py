"""Telemetry service facade.

Combines identity management, spans, metrics, and exporting into a single
cohesive interface for telemetry collection.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .base import (
    BaseExporter,
    EventType,
    SpanStatus,
    TelemetryBatch,
    TelemetryEvent,
    TelemetrySpan,
)
from .exporter import BatchExporter, ExporterConfig
from .identity import IdentityManager
from .metrics import MetricsManager
from .spans import SpanManager
from .spool import DiskSpool

logger = logging.getLogger(__name__)


@dataclass
class TelemetryConfig:
    """Configuration for telemetry service."""

    # Enable/disable
    enabled: bool = True
    debug: bool = False

    # Endpoint
    endpoint: Optional[str] = None

    # Sampling
    sample_rate: float = 1.0

    # Service info
    service_name: str = "runtm-cli"
    service_version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> TelemetryConfig:
        """Create config from environment variables.

        Environment variables:
        - RUNTM_TELEMETRY_DISABLED: Set to "1" to disable
        - RUNTM_TELEMETRY_DEBUG: Set to "1" for console output
        - RUNTM_TELEMETRY_ENDPOINT: Custom OTLP endpoint
        - RUNTM_TELEMETRY_SAMPLE_RATE: Trace sampling rate (0.0-1.0)
        """
        disabled = os.environ.get("RUNTM_TELEMETRY_DISABLED", "").lower() in ("1", "true", "yes")
        debug = os.environ.get("RUNTM_TELEMETRY_DEBUG", "").lower() in ("1", "true", "yes")
        endpoint = os.environ.get("RUNTM_TELEMETRY_ENDPOINT")

        sample_rate_str = os.environ.get("RUNTM_TELEMETRY_SAMPLE_RATE", "1.0")
        try:
            sample_rate = float(sample_rate_str)
            sample_rate = max(0.0, min(1.0, sample_rate))
        except ValueError:
            sample_rate = 1.0

        return cls(
            enabled=not disabled,
            debug=debug,
            endpoint=endpoint,
            sample_rate=sample_rate,
        )


class TelemetryService:
    """Main telemetry service facade.

    Provides a unified interface for:
    - Identity management (install_id, session_id)
    - Span creation and management
    - Metrics recording
    - Event emission
    - Batched export with disk spooling
    """

    def __init__(
        self,
        exporter: Optional[BaseExporter] = None,
        config: Optional[TelemetryConfig] = None,
        identity_path: Optional[Path] = None,
        spool_path: Optional[Path] = None,
    ) -> None:
        """Initialize the telemetry service.

        Args:
            exporter: The telemetry exporter to use
            config: Telemetry configuration
            identity_path: Path to identity file
            spool_path: Path to spool directory
        """
        self._config = config or TelemetryConfig.from_env()
        self._enabled = self._config.enabled

        # Components
        self._identity = IdentityManager(identity_path)
        self._spans = SpanManager(self._config.service_name)
        self._metrics = MetricsManager()
        self._spool = DiskSpool(spool_path)

        # Exporter (lazy initialization)
        self._exporter = exporter
        self._batch_exporter: Optional[BatchExporter] = None
        self._started = False

    @property
    def enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self._enabled

    @property
    def install_id(self) -> str:
        """Get the installation ID."""
        return self._identity.install_id

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._identity.session_id

    @property
    def trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        return self._spans.current_trace_id

    @property
    def span_id(self) -> Optional[str]:
        """Get the current span ID."""
        return self._spans.current_span_id

    def get_traceparent(self) -> Optional[str]:
        """Get the W3C traceparent header for the current span."""
        return self._spans.get_traceparent()

    def start(self) -> None:
        """Start the telemetry service.

        Initializes the batch exporter and starts background flushing.
        Also processes any spooled data from previous runs.
        """
        if not self._enabled or self._started:
            return

        if self._exporter is None:
            # Will be set by the caller (CLI, API, etc.)
            return

        # Create batch exporter with callbacks
        self._batch_exporter = BatchExporter(
            exporter=self._exporter,
            config=ExporterConfig(),
            on_dropped=lambda count: self._metrics.record_dropped_events(count),
            on_flush_failure=lambda: self._metrics.record_flush_failure(),
        )
        self._batch_exporter.start()
        self._started = True

        # Process spooled data
        self._process_spool()

    def shutdown(self) -> None:
        """Shutdown the telemetry service.

        Flushes remaining data and stops the background thread.
        Any unflushed data is spooled to disk.
        """
        if not self._enabled or not self._started:
            return

        # Flush remaining spans
        spans = self._spans.drain_completed_spans()
        for span in spans:
            if self._batch_exporter:
                self._batch_exporter.enqueue_span(span)

        # Flush remaining metrics
        metrics = self._metrics.drain()
        for metric in metrics:
            if self._batch_exporter:
                self._batch_exporter.enqueue_metric(metric)

        # Shutdown batch exporter
        if self._batch_exporter:
            self._batch_exporter.shutdown()

        self._started = False

    def set_exporter(self, exporter: BaseExporter) -> None:
        """Set the telemetry exporter.

        Args:
            exporter: The exporter to use
        """
        self._exporter = exporter

    # === Span API ===

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Generator[TelemetrySpan, None, None]:
        """Create a span context.

        Args:
            name: Span name
            attributes: Initial attributes

        Yields:
            The created span
        """
        if not self._enabled:
            # Return a dummy span
            yield TelemetrySpan(
                name=name,
                trace_id="0" * 32,
                span_id="0" * 16,
                attributes=attributes or {},
            )
            return

        with self._spans.span(name, attributes) as span:
            # Add identity to span
            span.set_attribute("runtm.install_id", self._identity.install_id)
            span.set_attribute("runtm.session_id", self._identity.session_id)
            yield span

        # Enqueue completed span
        if self._batch_exporter:
            self._batch_exporter.enqueue_span(span)

    def start_span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Start a span manually.

        Remember to call end_span() when done.

        Args:
            name: Span name
            attributes: Initial attributes

        Returns:
            The created span
        """
        if not self._enabled:
            return TelemetrySpan(
                name=name,
                trace_id="0" * 32,
                span_id="0" * 16,
                attributes=attributes or {},
            )

        span = self._spans.start_span(name, attributes)
        span.set_attribute("runtm.install_id", self._identity.install_id)
        span.set_attribute("runtm.session_id", self._identity.session_id)
        return span

    def end_span(
        self,
        span: TelemetrySpan,
        status: SpanStatus = SpanStatus.OK,
    ) -> None:
        """End a span and enqueue for export.

        Args:
            span: The span to end
            status: Final status
        """
        if not self._enabled:
            return

        self._spans.end_span(span, status)

        if self._batch_exporter:
            self._batch_exporter.enqueue_span(span)

    def add_span_event(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an event to the current span.

        Args:
            name: Event name
            attributes: Event attributes
        """
        if not self._enabled:
            return
        self._spans.add_event(name, attributes)

    def set_span_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key
            value: Attribute value
        """
        if not self._enabled:
            return
        self._spans.set_attribute(key, value)

    # === Event API ===

    def emit_event(
        self,
        event_type: EventType,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit a telemetry event.

        Args:
            event_type: Type of event
            attributes: Event attributes
        """
        if not self._enabled:
            return

        event = TelemetryEvent(
            name=event_type.value,
            attributes={
                "install_id": self._identity.install_id,
                "session_id": self._identity.session_id,
                **(attributes or {}),
            },
            trace_id=self._spans.current_trace_id,
            span_id=self._spans.current_span_id,
        )

        if self._batch_exporter:
            self._batch_exporter.enqueue_event(event)

        if self._config.debug:
            logger.info(f"[telemetry] {event_type.value}: {event.attributes}")

    # === Metrics API ===

    def record_command(
        self,
        command: str,
        outcome: str,
        duration_ms: float,
    ) -> None:
        """Record a command execution metric.

        Args:
            command: Command name
            outcome: success, failure, timeout
            duration_ms: Duration in milliseconds
        """
        if not self._enabled:
            return
        self._metrics.record_command(command, outcome, duration_ms)

    def record_error(
        self,
        command: str,
        error_type: str,
    ) -> None:
        """Record an error metric.

        Args:
            command: Command name
            error_type: Error category
        """
        if not self._enabled:
            return
        self._metrics.record_error(command, error_type)

    # === Lifecycle Events ===

    def check_first_run(self, cli_version: str) -> None:
        """Check and emit first_run event if needed.

        Args:
            cli_version: Current CLI version
        """
        if not self._enabled:
            return

        if self._identity.should_send_first_run():
            system_info = self._identity.get_system_info()
            self.emit_event(
                EventType.FIRST_RUN,
                attributes={
                    "cli_version": cli_version,
                    **system_info,
                },
            )
            self._identity.mark_first_run_sent()

    def check_upgrade(self, cli_version: str) -> None:
        """Check and emit upgrade event if needed.

        Args:
            cli_version: Current CLI version
        """
        if not self._enabled:
            return

        if self._identity.is_upgrade(cli_version):
            self.emit_event(
                EventType.UPGRADE,
                attributes={
                    "from_version": self._identity.previous_version,
                    "to_version": cli_version,
                },
            )
        self._identity.update_version(cli_version)

    def emit_config_loaded(self, config_source: str) -> None:
        """Emit config.loaded event.

        Args:
            config_source: Source of config (default, env, file)
        """
        self.emit_event(
            EventType.CONFIG_LOADED,
            attributes={"config_source": config_source},
        )

    # === Spool Management ===

    def _process_spool(self) -> None:
        """Process any spooled data from previous runs."""
        if not self._batch_exporter:
            return

        files_to_delete = []
        for file_path, batch in self._spool.read_all():
            enqueued = self._batch_exporter.enqueue_batch(batch)
            if enqueued > 0:
                files_to_delete.append(file_path)

        # Delete processed files
        for file_path in files_to_delete:
            self._spool.delete_file(file_path)

    def spool_remaining(self) -> None:
        """Spool any remaining data that couldn't be sent."""
        if not self._enabled:
            return

        # Collect remaining spans
        spans = self._spans.drain_completed_spans()

        # Collect remaining metrics
        metrics = self._metrics.drain()

        if spans or metrics:
            batch = TelemetryBatch(spans=spans, metrics=metrics)
            self._spool.write(batch)


# === Helper Functions ===


def create_command_span_attributes(
    command: str,
    exit_code: Optional[int] = None,
    template: Optional[str] = None,
    tier: Optional[str] = None,
    runtime: Optional[str] = None,
) -> dict[str, Any]:
    """Create standard span attributes for a command.

    Args:
        command: Command name
        exit_code: Exit code (0 for success)
        template: Template name if applicable
        tier: Machine tier if applicable
        runtime: Runtime if applicable

    Returns:
        Dict of span attributes
    """
    attrs: dict[str, Any] = {"runtm.command.name": command}

    if exit_code is not None:
        attrs["runtm.command.exit_code"] = exit_code
    if template:
        attrs["runtm.template"] = template
    if tier:
        attrs["runtm.tier"] = tier
    if runtime:
        attrs["runtm.runtime"] = runtime

    return attrs
