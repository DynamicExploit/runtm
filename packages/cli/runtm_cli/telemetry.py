"""CLI telemetry integration.

Provides a global telemetry service instance for the CLI,
with Typer integration for automatic command tracking.
"""

from __future__ import annotations

import atexit
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from runtm_cli import __version__
from runtm_cli.config import get_api_url, get_token
from runtm_shared.telemetry import (
    EventType,
    TelemetryConfig,
    TelemetryService,
    TelemetrySpan,
    create_command_span_attributes,
    create_controlplane_exporter,
    create_exporter,
)

# Global telemetry service instance
_telemetry: TelemetryService | None = None
_command_start_time: float | None = None
_current_command: str | None = None


def get_telemetry() -> TelemetryService:
    """Get the global telemetry service instance.

    Returns:
        The telemetry service (initializes if needed)
    """
    global _telemetry

    if _telemetry is None:
        _telemetry = _create_telemetry_service()

    return _telemetry


def _create_telemetry_service() -> TelemetryService:
    """Create and configure the telemetry service.

    Returns:
        Configured TelemetryService
    """
    # Determine config source (also ensures config is loaded)
    config_source = _determine_config_source()

    # Create telemetry config from environment
    telemetry_config = TelemetryConfig.from_env()
    telemetry_config.service_name = "runtm-cli"
    telemetry_config.service_version = __version__

    # Create exporter based on configuration
    # Use ControlPlaneExporter when API is configured (local or production)
    # Use OTLPExporter only when no API is configured (fallback to default endpoint)
    api_url = get_api_url()
    token = get_token()

    if not telemetry_config.enabled:
        # Telemetry disabled
        exporter = create_exporter(disabled=True)
    elif telemetry_config.debug:
        # Debug mode - console output
        exporter = create_exporter(debug=True)
    elif telemetry_config.endpoint:
        # Custom endpoint specified - use OTLP exporter
        exporter = create_exporter(
            endpoint=telemetry_config.endpoint,
            token=token,
        )
    elif api_url and token:
        # Send telemetry to the configured control plane API
        # Works for both local development and production (app.runtm.com)
        exporter = create_controlplane_exporter(
            api_url=api_url,
            token=token,
            service_name="runtm-cli",
        )
    else:
        # No API configured - use default OTLP exporter as fallback
        exporter = create_exporter(token=token)

    # Create service
    service = TelemetryService(
        exporter=exporter,
        config=telemetry_config,
    )

    # Start the service
    service.start()

    # Check for first run and upgrades
    service.check_first_run(__version__)
    service.check_upgrade(__version__)

    # Emit config loaded event
    service.emit_config_loaded(config_source)

    # Register shutdown handler
    atexit.register(_shutdown_telemetry)

    return service


def _determine_config_source() -> str:
    """Determine the source of CLI configuration.

    Returns:
        "env" if environment variables override, "file" if config file exists,
        "default" otherwise
    """
    if (
        os.environ.get("RUNTM_API_URL")
        or os.environ.get("RUNTM_API_KEY")
        or os.environ.get("RUNTM_TOKEN")
    ):
        return "env"

    from runtm_cli.config import get_config_file

    if get_config_file().exists():
        return "file"

    return "default"


def _shutdown_telemetry() -> None:
    """Shutdown the telemetry service on exit."""
    global _telemetry
    if _telemetry is not None:
        _telemetry.shutdown()
        _telemetry = None


# === Command Tracking ===


def start_command(command_name: str) -> None:
    """Start tracking a command execution.

    Args:
        command_name: Name of the command being executed
    """
    global _command_start_time, _current_command
    _command_start_time = time.time()
    _current_command = command_name


def end_command(
    command_name: str,
    outcome: str = "success",
    error_type: str | None = None,
) -> None:
    """End tracking a command execution.

    Args:
        command_name: Name of the command
        outcome: "success", "failure", or "timeout"
        error_type: Optional error category if failed
    """
    global _command_start_time, _current_command

    telemetry = get_telemetry()

    # Calculate duration
    duration_ms = 0.0
    if _command_start_time is not None:
        duration_ms = (time.time() - _command_start_time) * 1000

    # Record metrics
    telemetry.record_command(command_name, outcome, duration_ms)

    if outcome == "failure" and error_type:
        telemetry.record_error(command_name, error_type)

    _command_start_time = None
    _current_command = None


@contextmanager
def command_span(
    command_name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[TelemetrySpan, None, None]:
    """Context manager for tracking a command with a span.

    Automatically records metrics and handles errors.

    Args:
        command_name: Name of the command
        attributes: Additional span attributes

    Yields:
        The command span
    """
    telemetry = get_telemetry()
    start_time = time.time()

    # Merge command attributes
    span_attrs = create_command_span_attributes(command_name)
    if attributes:
        span_attrs.update(attributes)

    outcome = "success"
    error_type: str | None = None

    try:
        with telemetry.span(f"cli.command.{command_name}", span_attrs) as span:
            yield span
            span.set_attribute("runtm.command.exit_code", 0)

    except KeyboardInterrupt:
        outcome = "cancelled"
        raise

    except SystemExit as e:
        if e.code != 0:
            outcome = "failure"
            error_type = "exit_error"
        raise

    except Exception as e:
        outcome = "failure"
        error_type = type(e).__name__
        raise

    finally:
        # Record metrics
        duration_ms = (time.time() - start_time) * 1000
        telemetry.record_command(command_name, outcome, duration_ms)

        if outcome == "failure" and error_type:
            telemetry.record_error(command_name, error_type)


# === Phase Tracking ===


@contextmanager
def phase_span(
    phase_name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[TelemetrySpan, None, None]:
    """Context manager for tracking a command phase.

    Args:
        phase_name: Name of the phase (validate, upload, deploy, poll)
        attributes: Additional span attributes

    Yields:
        The phase span
    """
    telemetry = get_telemetry()
    start_time = time.time()

    # Emit phase started event
    telemetry.add_span_event("runtm.phase.started", {"phase": phase_name})

    try:
        with telemetry.span(f"cli.command.{phase_name}", attributes) as span:
            span.set_attribute("runtm.phase", phase_name)
            yield span

        # Emit phase completed event
        duration_ms = (time.time() - start_time) * 1000
        telemetry.add_span_event(
            "runtm.phase.completed",
            {"phase": phase_name, "duration_ms": duration_ms},
        )

    except Exception as e:
        # Emit phase failed event
        telemetry.add_span_event(
            "runtm.phase.failed",
            {"phase": phase_name, "error_type": type(e).__name__},
        )
        raise


# === Event Helpers ===


def emit_login_started(auth_method: str = "token") -> None:
    """Emit login started event.

    Args:
        auth_method: Authentication method (token, device_flow)
    """
    get_telemetry().emit_event(
        EventType.LOGIN_STARTED,
        {"auth_method": auth_method},
    )


def emit_login_completed(auth_method: str = "token") -> None:
    """Emit login completed event.

    Args:
        auth_method: Authentication method
    """
    get_telemetry().emit_event(
        EventType.LOGIN_COMPLETED,
        {"auth_method": auth_method},
    )


def emit_auth_failed(error_type: str) -> None:
    """Emit auth failed event.

    Args:
        error_type: Type of auth error
    """
    get_telemetry().emit_event(
        EventType.AUTH_FAILED,
        {"error_type": error_type},
    )


def emit_init_template_selected(template: str, has_existing_files: bool = False) -> None:
    """Emit init template selected event.

    Args:
        template: Selected template name
        has_existing_files: Whether directory had existing files
    """
    get_telemetry().emit_event(
        EventType.INIT_TEMPLATE_SELECTED,
        {"template": template, "has_existing_files": has_existing_files},
    )


def emit_init_completed(template: str, duration_ms: float) -> None:
    """Emit init completed event.

    Args:
        template: Template name
        duration_ms: Duration in milliseconds
    """
    get_telemetry().emit_event(
        EventType.INIT_COMPLETED,
        {"template": template, "duration_ms": duration_ms},
    )


def emit_deploy_started(
    is_redeploy: bool = False,
    tier: str | None = None,
    artifact_size_mb: float | None = None,
    template: str | None = None,
) -> None:
    """Emit deploy started event.

    Args:
        is_redeploy: Whether this is a redeployment
        tier: Machine tier
        artifact_size_mb: Artifact size in MB
        template: Template type (backend-service, static-site, web-app)
    """
    attrs: dict[str, Any] = {"is_redeploy": is_redeploy}
    if tier:
        attrs["tier"] = tier
    if artifact_size_mb is not None:
        attrs["artifact_size_mb"] = artifact_size_mb
    if template:
        attrs["template"] = template

    get_telemetry().emit_event(EventType.DEPLOY_STARTED, attrs)


def emit_deploy_validation_failed(error_count: int, warning_count: int = 0) -> None:
    """Emit deploy validation failed event.

    Args:
        error_count: Number of validation errors
        warning_count: Number of validation warnings
    """
    get_telemetry().emit_event(
        EventType.DEPLOY_VALIDATION_FAILED,
        {"error_count": error_count, "warning_count": warning_count},
    )


def emit_deploy_completed(
    duration_ms: float,
    version: int = 1,
    template: str | None = None,
) -> None:
    """Emit deploy completed event.

    Args:
        duration_ms: Deploy duration in milliseconds
        version: Deployment version number
        template: Template type (backend-service, static-site, web-app)
    """
    attrs: dict[str, Any] = {"duration_ms": duration_ms, "version": version}
    if template:
        attrs["template"] = template
    get_telemetry().emit_event(EventType.DEPLOY_COMPLETED, attrs)


def emit_deploy_failed(error_type: str, state_reached: str | None = None) -> None:
    """Emit deploy failed event.

    Args:
        error_type: Type of error
        state_reached: Last deployment state reached
    """
    attrs: dict[str, Any] = {"error_type": error_type}
    if state_reached:
        attrs["state_reached"] = state_reached

    get_telemetry().emit_event(EventType.DEPLOY_FAILED, attrs)


def emit_run_started(runtime: str, has_bun: bool = False) -> None:
    """Emit run started event.

    Args:
        runtime: Runtime type (python, node, fullstack)
        has_bun: Whether Bun is available
    """
    get_telemetry().emit_event(
        EventType.RUN_STARTED,
        {"runtime": runtime, "has_bun": has_bun},
    )


def emit_destroy_completed() -> None:
    """Emit destroy completed event."""
    get_telemetry().emit_event(EventType.DESTROY_COMPLETED)


def emit_domain_added(has_ssl: bool = False) -> None:
    """Emit domain added event.

    Args:
        has_ssl: Whether SSL is configured
    """
    get_telemetry().emit_event(
        EventType.DOMAIN_ADDED,
        {"has_ssl": has_ssl},
    )


def emit_domain_removed() -> None:
    """Emit domain removed event."""
    get_telemetry().emit_event(EventType.DOMAIN_REMOVED)


# === Trace Propagation ===


def get_traceparent() -> str | None:
    """Get the current traceparent header value.

    Returns:
        W3C traceparent header value or None
    """
    return get_telemetry().get_traceparent()
