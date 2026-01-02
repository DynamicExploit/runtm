"""Telemetry exporter implementations.

Provides NoopExporter (disabled), ConsoleExporter (debug), and OTLPExporter (production).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import httpx

from .base import BaseExporter, TelemetryBatch

logger = logging.getLogger(__name__)


class NoopExporter(BaseExporter):
    """No-op exporter that discards all telemetry.

    Used when telemetry is disabled.
    """

    def export(self, batch: TelemetryBatch) -> bool:
        """Discard the batch.

        Args:
            batch: The telemetry batch (ignored)

        Returns:
            Always True
        """
        return True

    def shutdown(self) -> None:
        """No-op shutdown."""
        pass


class ConsoleExporter(BaseExporter):
    """Console exporter for debugging.

    Prints telemetry data to stderr in a human-readable format.
    """

    def __init__(self, pretty: bool = True) -> None:
        """Initialize the console exporter.

        Args:
            pretty: Whether to pretty-print JSON
        """
        self._pretty = pretty

    def export(self, batch: TelemetryBatch) -> bool:
        """Print batch to console.

        Args:
            batch: The telemetry batch

        Returns:
            Always True
        """
        if batch.is_empty():
            return True

        output_lines = ["[telemetry] Batch:"]

        # Spans
        for span in batch.spans:
            duration = span.duration_ms or 0
            status = span.status.value
            output_lines.append(
                f"  [span] {span.name} "
                f"(trace={span.trace_id[:8]}... span={span.span_id[:8]}... "
                f"status={status} duration={duration:.1f}ms)"
            )
            for key, value in span.attributes.items():
                output_lines.append(f"    {key}: {value}")
            for event in span.events:
                ts = datetime.fromtimestamp(event.timestamp_ns / 1e9).isoformat()
                output_lines.append(f"    [event] {event.name} at {ts}")

        # Events
        for event in batch.events:
            ts = datetime.fromtimestamp(event.timestamp_ns / 1e9).isoformat()
            output_lines.append(f"  [event] {event.name} at {ts}")
            for key, value in event.attributes.items():
                output_lines.append(f"    {key}: {value}")

        # Metrics
        for metric in batch.metrics:
            labels = ", ".join(f"{k}={v}" for k, v in metric.labels.items())
            output_lines.append(f"  [metric] {metric.name}{{{labels}}} = {metric.value}")

        output = "\n".join(output_lines)
        print(output, file=sys.stderr)

        return True

    def shutdown(self) -> None:
        """Flush stderr."""
        sys.stderr.flush()


class OTLPExporter(BaseExporter):
    """OTLP HTTP exporter for production use.

    Sends telemetry to an OTLP-compatible endpoint using HTTP/JSON.
    Uses httpx for HTTP requests with tight timeouts.
    """

    DEFAULT_ENDPOINT = "https://api.runtm.dev/v0/telemetry"
    DEFAULT_TIMEOUT = 0.5  # 500ms

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize the OTLP exporter.

        Args:
            endpoint: OTLP endpoint URL
            timeout: Request timeout in seconds
            headers: Additional headers (e.g., Authorization)
        """
        self._endpoint = endpoint or self.DEFAULT_ENDPOINT
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client.

        Returns:
            httpx.Client instance
        """
        if self._client is None:
            import httpx

            self._client = httpx.Client(
                timeout=self._timeout,
                headers={
                    "Content-Type": "application/json",
                    **self._headers,
                },
            )
        return self._client

    def export(self, batch: TelemetryBatch) -> bool:
        """Export batch to OTLP endpoint.

        Args:
            batch: The telemetry batch

        Returns:
            True if export succeeded
        """
        if batch.is_empty():
            return True

        try:
            client = self._get_client()
            response = client.post(
                self._endpoint,
                json=batch.to_dict(),
            )
            return response.status_code < 400

        except ImportError:
            logger.debug("httpx not installed, cannot export telemetry")
            return False
        except Exception as e:
            logger.debug(f"Failed to export telemetry: {e}")
            return False

    def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


class BufferedFileExporter(BaseExporter):
    """File exporter for local testing and debugging.

    Writes telemetry to a newline-delimited JSON file.
    """

    def __init__(self, file_path: str) -> None:
        """Initialize the file exporter.

        Args:
            file_path: Path to output file
        """
        self._file_path = file_path
        self._file = None

    def export(self, batch: TelemetryBatch) -> bool:
        """Write batch to file.

        Args:
            batch: The telemetry batch

        Returns:
            True if export succeeded
        """
        if batch.is_empty():
            return True

        try:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(batch.to_dict()) + "\n")
            return True
        except Exception as e:
            logger.debug(f"Failed to write telemetry to file: {e}")
            return False

    def shutdown(self) -> None:
        """No-op for file exporter."""
        pass


class ControlPlaneExporter(BaseExporter):
    """Control Plane exporter for sending telemetry to the Runtm API.

    Sends telemetry batches to the control plane API for storage and
    dashboard visualization. Uses the same format as the ingest endpoint.
    """

    DEFAULT_TIMEOUT = 2.0  # 2 seconds (more lenient than OTLP)

    def __init__(
        self,
        api_url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT,
        service_name: Optional[str] = None,
    ) -> None:
        """Initialize the control plane exporter.

        Args:
            api_url: Base URL of the Runtm API (e.g., "http://localhost:8000")
            token: API authentication token
            timeout: Request timeout in seconds
            service_name: Optional source service name
        """
        # Ensure endpoint ends with /v0/telemetry
        api_url = api_url.rstrip("/")
        if not api_url.endswith("/v0/telemetry"):
            self._endpoint = f"{api_url}/v0/telemetry"
        else:
            self._endpoint = api_url

        self._token = token
        self._timeout = timeout
        self._service_name = service_name
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client.

        Returns:
            httpx.Client instance
        """
        if self._client is None:
            import httpx

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            }
            if self._service_name:
                headers["X-Service-Name"] = self._service_name

            self._client = httpx.Client(
                timeout=self._timeout,
                headers=headers,
            )
        return self._client

    def export(self, batch: TelemetryBatch) -> bool:
        """Export batch to control plane API.

        Args:
            batch: The telemetry batch

        Returns:
            True if export succeeded
        """
        if batch.is_empty():
            return True

        try:
            client = self._get_client()
            response = client.post(
                self._endpoint,
                json=batch.to_dict(),
            )

            if response.status_code >= 400:
                logger.debug(
                    "Control plane telemetry export failed: %s %s",
                    response.status_code,
                    response.text[:200] if response.text else "",
                )
                return False

            return True

        except ImportError:
            logger.debug("httpx not installed, cannot export telemetry")
            return False
        except Exception as e:
            logger.debug(f"Failed to export telemetry to control plane: {e}")
            return False

    def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


def create_exporter(
    endpoint: Optional[str] = None,
    debug: bool = False,
    disabled: bool = False,
    token: Optional[str] = None,
) -> BaseExporter:
    """Create the appropriate exporter based on configuration.

    Args:
        endpoint: Custom OTLP endpoint
        debug: Enable console output
        disabled: Disable telemetry entirely
        token: API token for authorization

    Returns:
        Configured exporter instance
    """
    if disabled:
        return NoopExporter()

    if debug:
        return ConsoleExporter()

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return OTLPExporter(endpoint=endpoint, headers=headers)


def create_controlplane_exporter(
    api_url: str,
    token: str,
    service_name: Optional[str] = None,
    timeout: float = ControlPlaneExporter.DEFAULT_TIMEOUT,
) -> ControlPlaneExporter:
    """Create a control plane exporter for sending telemetry to Runtm API.

    Args:
        api_url: Base URL of the Runtm API (e.g., "http://localhost:8000")
        token: API authentication token
        service_name: Optional source service name (e.g., "runtm-cli")
        timeout: Request timeout in seconds

    Returns:
        Configured ControlPlaneExporter instance
    """
    return ControlPlaneExporter(
        api_url=api_url,
        token=token,
        service_name=service_name,
        timeout=timeout,
    )
