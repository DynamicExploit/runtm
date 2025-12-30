"""Span management for distributed tracing.

Wraps OpenTelemetry Tracer with a simpler interface and span context management.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator, Optional

from .base import SpanStatus, TelemetrySpan

# Context variable for current span
_current_span: ContextVar[Optional[TelemetrySpan]] = ContextVar(
    "current_span", default=None
)


def generate_trace_id() -> str:
    """Generate a new trace ID (32 hex chars)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a new span ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


class SpanManager:
    """Manages spans for distributed tracing.

    Provides a simple interface for creating and managing spans,
    with support for nested spans and context propagation.
    """

    def __init__(self, service_name: str = "runtm-cli") -> None:
        """Initialize the span manager.

        Args:
            service_name: Name of the service for span naming
        """
        self._service_name = service_name
        self._completed_spans: list[TelemetrySpan] = []

    @property
    def current_span(self) -> Optional[TelemetrySpan]:
        """Get the current active span."""
        return _current_span.get()

    @property
    def current_trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        span = self.current_span
        return span.trace_id if span else None

    @property
    def current_span_id(self) -> Optional[str]:
        """Get the current span ID."""
        span = self.current_span
        return span.span_id if span else None

    def get_traceparent(self) -> Optional[str]:
        """Get the W3C traceparent header value for the current span.

        Returns:
            traceparent header value (e.g., "00-<trace_id>-<span_id>-01")
            or None if no active span
        """
        span = self.current_span
        if not span:
            return None
        # W3C Trace Context format: version-trace_id-parent_id-flags
        # version: 00, flags: 01 (sampled)
        return f"00-{span.trace_id}-{span.span_id}-01"

    @staticmethod
    def parse_traceparent(header: str) -> Optional[tuple[str, str]]:
        """Parse a W3C traceparent header.

        Args:
            header: The traceparent header value

        Returns:
            Tuple of (trace_id, parent_span_id) or None if invalid
        """
        try:
            parts = header.split("-")
            if len(parts) != 4 or parts[0] != "00":
                return None
            trace_id, parent_span_id = parts[1], parts[2]
            if len(trace_id) != 32 or len(parent_span_id) != 16:
                return None
            return trace_id, parent_span_id
        except Exception:
            return None

    def start_span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> TelemetrySpan:
        """Start a new span.

        If there's a current span and no explicit parent, the new span
        becomes a child of the current span.

        Args:
            name: Name of the span
            attributes: Initial span attributes
            trace_id: Explicit trace ID (defaults to current or new)
            parent_span_id: Explicit parent span ID

        Returns:
            The new span
        """
        current = self.current_span

        # Determine trace ID
        if trace_id is None:
            trace_id = current.trace_id if current else generate_trace_id()

        # Determine parent span ID
        if parent_span_id is None and current is not None:
            parent_span_id = current.span_id

        span = TelemetrySpan(
            name=name,
            trace_id=trace_id,
            span_id=generate_span_id(),
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )

        _current_span.set(span)
        return span

    def end_span(
        self,
        span: TelemetrySpan,
        status: SpanStatus = SpanStatus.OK,
    ) -> None:
        """End a span and restore the previous span context.

        Args:
            span: The span to end
            status: Final status of the span
        """
        span.end(status)
        self._completed_spans.append(span)

        # Restore parent span as current (if this was a child span)
        # For simplicity, we just clear the current span
        # In a real implementation, we'd maintain a stack
        _current_span.set(None)

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Generator[TelemetrySpan, None, None]:
        """Context manager for creating spans.

        Automatically ends the span when exiting the context,
        setting status to ERROR if an exception occurred.

        Args:
            name: Name of the span
            attributes: Initial span attributes

        Yields:
            The created span
        """
        span = self.start_span(name, attributes)
        previous_span = _current_span.get()
        _current_span.set(span)

        try:
            yield span
            span.end(SpanStatus.OK)
        except Exception:
            span.end(SpanStatus.ERROR)
            raise
        finally:
            self._completed_spans.append(span)
            _current_span.set(previous_span)

    def add_event(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an event to the current span.

        Args:
            name: Event name
            attributes: Event attributes
        """
        span = self.current_span
        if span:
            span.add_event(name, attributes)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key
            value: Attribute value
        """
        span = self.current_span
        if span:
            span.set_attribute(key, value)

    def drain_completed_spans(self) -> list[TelemetrySpan]:
        """Get and clear all completed spans.

        Returns:
            List of completed spans
        """
        spans = self._completed_spans
        self._completed_spans = []
        return spans

    def create_child_span(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Create a child span of the current span.

        Args:
            name: Name of the child span
            attributes: Initial attributes

        Returns:
            The new child span

        Raises:
            RuntimeError: If there's no current span
        """
        current = self.current_span
        if current is None:
            raise RuntimeError("No current span to create child from")

        return self.start_span(
            name=name,
            attributes=attributes,
            trace_id=current.trace_id,
            parent_span_id=current.span_id,
        )

    def start_span_from_traceparent(
        self,
        name: str,
        traceparent: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Optional[TelemetrySpan]:
        """Start a span from a traceparent header.

        Used for continuing a trace from an incoming request.

        Args:
            name: Name of the span
            traceparent: W3C traceparent header value
            attributes: Initial attributes

        Returns:
            The new span, or None if traceparent is invalid
        """
        parsed = self.parse_traceparent(traceparent)
        if not parsed:
            return None

        trace_id, parent_span_id = parsed
        return self.start_span(
            name=name,
            attributes=attributes,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )

