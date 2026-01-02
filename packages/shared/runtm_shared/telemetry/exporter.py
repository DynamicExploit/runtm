"""Batch exporter with backpressure and reliability features.

Implements:
- Bounded queue with overflow protection
- Background flush thread
- Exponential backoff with jitter on failures
- Tight timeouts to never block CLI
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Union

from .base import (
    BaseExporter,
    TelemetryBatch,
    TelemetryEvent,
    TelemetryMetric,
    TelemetrySpan,
)

logger = logging.getLogger(__name__)


@dataclass
class ExporterConfig:
    """Configuration for the batch exporter."""

    # Queue limits
    max_queue_size: int = 1000
    batch_size: int = 50
    flush_interval_seconds: float = 5.0

    # Timeout limits
    flush_timeout_seconds: float = 0.5
    shutdown_timeout_seconds: float = 2.0

    # Backoff configuration
    backoff_initial_seconds: float = 0.1
    backoff_max_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    backoff_jitter: float = 0.1


TelemetryItem = Union[TelemetrySpan, TelemetryEvent, TelemetryMetric]


class BatchExporter:
    """Batched telemetry exporter with backpressure.

    Features:
    - Bounded queue (drops + counts on overflow)
    - Background flush thread
    - Exponential backoff with jitter on failures
    - Graceful shutdown with timeout
    """

    def __init__(
        self,
        exporter: BaseExporter,
        config: ExporterConfig | None = None,
        on_dropped: Callable[[int], None] | None = None,
        on_flush_failure: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the batch exporter.

        Args:
            exporter: The underlying exporter to use
            config: Exporter configuration
            on_dropped: Callback when events are dropped (receives count)
            on_flush_failure: Callback when flush fails
        """
        self._exporter = exporter
        self._config = config or ExporterConfig()
        self._on_dropped = on_dropped
        self._on_flush_failure = on_flush_failure

        # Bounded queue
        self._queue: queue.Queue[TelemetryItem] = queue.Queue(maxsize=self._config.max_queue_size)

        # Tracking
        self._dropped_count = 0
        self._consecutive_failures = 0
        self._current_backoff = self._config.backoff_initial_seconds

        # Background thread
        self._shutdown_event = threading.Event()
        self._flush_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """Start the background flush thread."""
        with self._lock:
            if self._started:
                return

            self._shutdown_event.clear()
            self._flush_thread = threading.Thread(
                target=self._flush_loop,
                name="runtm-telemetry-flush",
                daemon=True,
            )
            self._flush_thread.start()
            self._started = True

            # Register shutdown handler
            atexit.register(self.shutdown)

    def enqueue_span(self, span: TelemetrySpan) -> bool:
        """Enqueue a span for export.

        Args:
            span: The span to export

        Returns:
            True if enqueued, False if dropped
        """
        return self._enqueue(span)

    def enqueue_event(self, event: TelemetryEvent) -> bool:
        """Enqueue an event for export.

        Args:
            event: The event to export

        Returns:
            True if enqueued, False if dropped
        """
        return self._enqueue(event)

    def enqueue_metric(self, metric: TelemetryMetric) -> bool:
        """Enqueue a metric for export.

        Args:
            metric: The metric to export

        Returns:
            True if enqueued, False if dropped
        """
        return self._enqueue(metric)

    def enqueue_batch(self, batch: TelemetryBatch) -> int:
        """Enqueue a batch of telemetry data.

        Args:
            batch: The batch to enqueue

        Returns:
            Number of items successfully enqueued
        """
        enqueued = 0
        for span in batch.spans:
            if self._enqueue(span):
                enqueued += 1
        for event in batch.events:
            if self._enqueue(event):
                enqueued += 1
        for metric in batch.metrics:
            if self._enqueue(metric):
                enqueued += 1
        return enqueued

    def _enqueue(self, item: TelemetryItem) -> bool:
        """Enqueue an item, dropping if queue is full.

        Args:
            item: The item to enqueue

        Returns:
            True if enqueued, False if dropped
        """
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            self._dropped_count += 1
            if self._on_dropped:
                with contextlib.suppress(Exception):
                    self._on_dropped(1)
            return False

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes the queue."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for flush interval or shutdown
                self._shutdown_event.wait(timeout=self._config.flush_interval_seconds)

                # Flush if we have items
                self._flush_batch()

            except Exception as e:
                logger.debug(f"Error in flush loop: {e}")

    def _flush_batch(self) -> bool:
        """Flush a batch of items.

        Returns:
            True if flush succeeded, False otherwise
        """
        # Collect items up to batch size
        items: list[TelemetryItem] = []
        try:
            while len(items) < self._config.batch_size:
                item = self._queue.get_nowait()
                items.append(item)
        except queue.Empty:
            pass

        if not items:
            return True

        # Build batch
        batch = TelemetryBatch()
        for item in items:
            if isinstance(item, TelemetrySpan):
                batch.spans.append(item)
            elif isinstance(item, TelemetryEvent):
                batch.events.append(item)
            elif isinstance(item, TelemetryMetric):
                batch.metrics.append(item)

        # Try to export with timeout
        success = self._export_with_backoff(batch)

        if not success:
            # Re-queue items if export failed (best effort)
            for item in items:
                try:
                    self._queue.put_nowait(item)
                except queue.Full:
                    self._dropped_count += 1

        return success

    def _export_with_backoff(self, batch: TelemetryBatch) -> bool:
        """Export batch with exponential backoff on failure.

        Args:
            batch: The batch to export

        Returns:
            True if export succeeded
        """
        # Check if we need to wait due to backoff
        if self._consecutive_failures > 0:
            # Calculate backoff with jitter
            jitter = random.uniform(0, self._config.backoff_jitter * self._current_backoff)
            wait_time = min(
                self._current_backoff + jitter,
                self._config.flush_timeout_seconds,
            )
            time.sleep(wait_time)

        try:
            success = self._exporter.export(batch)

            if success:
                # Reset backoff on success
                self._consecutive_failures = 0
                self._current_backoff = self._config.backoff_initial_seconds
                return True
            else:
                self._handle_failure()
                return False

        except Exception as e:
            logger.debug(f"Export failed: {e}")
            self._handle_failure()
            return False

    def _handle_failure(self) -> None:
        """Handle export failure, updating backoff state."""
        self._consecutive_failures += 1

        # Increase backoff
        self._current_backoff = min(
            self._current_backoff * self._config.backoff_multiplier,
            self._config.backoff_max_seconds,
        )

        if self._on_flush_failure:
            with contextlib.suppress(Exception):
                self._on_flush_failure()

    def flush(self, timeout: float | None = None) -> bool:
        """Flush all pending items.

        Args:
            timeout: Maximum time to wait (defaults to shutdown_timeout)

        Returns:
            True if all items were flushed
        """
        timeout = timeout or self._config.shutdown_timeout_seconds
        deadline = time.time() + timeout

        while time.time() < deadline and not self._queue.empty():
            if not self._flush_batch():
                break

        return self._queue.empty()

    def shutdown(self) -> None:
        """Shutdown the exporter, flushing remaining data."""
        with self._lock:
            if not self._started:
                return

            # Signal shutdown
            self._shutdown_event.set()

            # Wait for flush thread to complete
            if self._flush_thread and self._flush_thread.is_alive():
                self._flush_thread.join(timeout=self._config.shutdown_timeout_seconds)

            # Final flush attempt
            self.flush(timeout=self._config.shutdown_timeout_seconds)

            # Shutdown underlying exporter
            try:
                self._exporter.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down exporter: {e}")

            self._started = False

            # Unregister atexit handler
            with contextlib.suppress(Exception):
                atexit.unregister(self.shutdown)

    @property
    def dropped_count(self) -> int:
        """Get the total number of dropped items."""
        return self._dropped_count

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        """Check if the exporter is running."""
        return self._started and not self._shutdown_event.is_set()
