"""Deploy command - deploy project to live URL."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from runtm_shared.errors import RuntmError
from runtm_shared.lockfiles import check_lockfile, fix_lockfile
from runtm_shared.manifest import Manifest
from runtm_shared.types import MachineTier, MACHINE_TIER_SPECS

from ..api_client import APIClient, create_artifact_zip
from ..config import get_token
from .validate import validate_project

console = Console()


def deploy_command(
    path: Path = Path("."),
    wait: bool = True,
    timeout: int = 300,
    new: bool = False,
    tier: Optional[str] = None,
    yes: bool = False,
) -> None:
    """Deploy a project to a live URL.

    By default, if a deployment with the same name already exists,
    this will redeploy (update) the existing deployment. The URL
    stays the same across versions.

    Use --new to force creation of a completely new deployment.
    Use --yes to auto-fix lockfile issues without prompting.

    Machine tiers (all use auto-stop for cost savings):
      - starter: 1 shared CPU, 256MB RAM (~$2/month, much less with auto-stop)
      - standard: 1 shared CPU, 512MB RAM (~$5/month, much less with auto-stop)
      - performance: 2 shared CPUs, 1GB RAM (~$10/month, much less with auto-stop)
    """
    from runtm_cli.telemetry import (
        command_span,
        emit_auth_failed,
        emit_deploy_completed,
        emit_deploy_failed,
        emit_deploy_started,
        emit_deploy_validation_failed,
        phase_span,
    )

    deploy_start_time = time.time()
    artifact_size: Optional[float] = None

    with command_span("deploy", {"runtm.tier": tier or "default"}) as span:
        # Validate tier if provided
        if tier is not None:
            try:
                tier_enum = MachineTier(tier)
                tier_spec = MACHINE_TIER_SPECS[tier_enum]
            except ValueError:
                valid_tiers = ", ".join(t.value for t in MachineTier)
                console.print(f"[red]✗[/red] Invalid tier: {tier}")
                console.print(f"    Valid tiers: {valid_tiers}")
                raise typer.Exit(1)

        # Check auth
        token = get_token()
        if not token:
            emit_auth_failed("missing_token")
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
            console.print()
            console.print("Or set RUNTM_TOKEN environment variable.")
            raise typer.Exit(1)

        # Validate first
        with phase_span("validate"):
            console.print("Validating project...")
            is_valid, errors, warnings = validate_project(path)

            for warning in warnings:
                console.print(f"[yellow]⚠[/yellow] {warning}")

            if not is_valid:
                emit_deploy_validation_failed(len(errors), len(warnings))
                for error in errors:
                    console.print(f"[red]✗[/red] {error}")
                console.print()
                console.print("Fix validation errors and try again.")
                raise typer.Exit(1)

            console.print("[green]✓[/green] Project validated")

        # Check lockfile (prod must be reproducible)
        with phase_span("lockfile_check"):
            try:
                manifest = Manifest.from_file(path / "runtm.yaml")
                lockfile_status = check_lockfile(path, manifest.runtime)
                
                if lockfile_status.needs_fix:
                    if yes:
                        action = "Creating" if not lockfile_status.exists else "Fixing"
                        console.print(
                            f"[yellow]{action} lockfile via {lockfile_status.install_cmd}...[/yellow]"
                        )
                        if fix_lockfile(path, lockfile_status):
                            console.print("[green]✓[/green] Lockfile fixed")
                        else:
                            console.print(f"[red]✗[/red] Failed to fix lockfile")
                            console.print(f"    Run manually: {lockfile_status.install_cmd}")
                            raise typer.Exit(1)
                    else:
                        issue = "missing" if not lockfile_status.exists else "out of sync"
                        console.print(f"[red]✗[/red] Lockfile {issue}")
                        console.print(f"    Run: [bold]{lockfile_status.install_cmd}[/bold]")
                        console.print(f"    Or deploy with: [bold]runtm deploy --yes[/bold]")
                        raise typer.Exit(1)
                else:
                    console.print("[green]✓[/green] Lockfile in sync")
            except typer.Exit:
                raise
            except Exception as e:
                # Don't block deploy on lockfile check errors, just warn
                console.print(f"[yellow]⚠[/yellow] Could not check lockfile: {e}")

        # Validate env vars (if env_schema is defined)
        resolved_secrets: dict = {}
        with phase_span("env_validation"):
            if manifest.env_schema:
                from runtm_cli.commands.secrets import resolve_env_vars

                resolved, missing_required, env_warnings = resolve_env_vars(path, manifest)

                for warning in env_warnings:
                    console.print(f"[yellow]⚠[/yellow] {warning}")

                if missing_required:
                    emit_deploy_validation_failed(len(missing_required), 0)
                    console.print("[red]✗[/red] Missing required environment variables:")
                    for name in missing_required:
                        console.print(f"    - {name}")
                    console.print()
                    console.print("Set them with:")
                    for name in missing_required:
                        console.print(f"  runtm secrets set {name}=<value>")
                    raise typer.Exit(1)

                # Extract secrets for injection (values marked as secret: true)
                secret_names = {ev.name for ev in manifest.get_secret_env_vars()}
                resolved_secrets = {k: v for k, v in resolved.items() if k in secret_names}

                if resolved:
                    console.print(f"[green]✓[/green] Environment variables resolved ({len(resolved)} vars)")
                    if resolved_secrets:
                        console.print(f"    [dim]{len(resolved_secrets)} secrets will be injected[/dim]")

        # Check for discovery metadata (optional, just warn)
        discovery_path = path / "runtm.discovery.yaml"
        if not discovery_path.exists():
            console.print(
                "[yellow]⚠[/yellow] No runtm.discovery.yaml found. "
                "Consider adding app metadata for discoverability."
            )
        else:
            # Check if discovery file has unfilled TODO placeholders
            try:
                discovery_content = discovery_path.read_text()
                if "# TODO:" in discovery_content or "TODO:" in discovery_content:
                    console.print(
                        "[yellow]⚠[/yellow] runtm.discovery.yaml has unfilled TODO placeholders. "
                        "Fill them in for better app discoverability."
                    )
            except Exception:
                pass  # Don't block on read errors

        # Create artifact
        with phase_span("artifact_create"):
            console.print("Creating artifact...")
            manifest_path = path / "runtm.yaml"

            # If tier is specified via CLI, update the manifest temporarily
            original_manifest_content = None
            if tier is not None:
                try:
                    import yaml

                    original_manifest_content = manifest_path.read_text()
                    manifest_data = yaml.safe_load(original_manifest_content)
                    manifest_data["tier"] = tier
                    manifest_path.write_text(yaml.safe_dump(manifest_data, default_flow_style=False, sort_keys=False))
                    console.print(f"[dim]Using tier: {tier_spec.description}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Could not update manifest tier: {e}")

            try:
                artifact_path = create_artifact_zip(path)
                artifact_size = artifact_path.stat().st_size / (1024 * 1024)
                console.print(f"[green]✓[/green] Artifact created ({artifact_size:.1f} MB)")
            except Exception as e:
                # Restore original manifest if we modified it
                if original_manifest_content is not None:
                    manifest_path.write_text(original_manifest_content)
                emit_deploy_failed("artifact_error")
                console.print(f"[red]✗[/red] Failed to create artifact: {e}")
                raise typer.Exit(1)
            finally:
                # Restore original manifest after creating artifact
                if original_manifest_content is not None:
                    manifest_path.write_text(original_manifest_content)

        # Deploy
        client = APIClient()

        with phase_span("api_call"):
            # Emit deploy started event
            is_redeploy = not new  # Will be updated after API call
            emit_deploy_started(
                is_redeploy=False,
                tier=tier,
                artifact_size_mb=artifact_size,
                template=manifest.template,
            )

            try:
                if new:
                    console.print("Creating new deployment...")
                else:
                    console.print("Creating deployment (will redeploy if name exists)...")

                deployment = client.create_deployment(
                    manifest_path, artifact_path, force_new=new, tier=tier, secrets=resolved_secrets
                )

                if deployment.version > 1:
                    console.print(
                        f"[green]✓[/green] Redeployment created: {deployment.deployment_id} "
                        f"(v{deployment.version})"
                    )
                    console.print(f"    Updating from: {deployment.previous_deployment_id}")
                else:
                    console.print(f"[green]✓[/green] Deployment created: {deployment.deployment_id}")
            except RuntmError as e:
                emit_deploy_failed("api_error")
                console.print(f"[red]✗[/red] {e.message}")
                if e.recovery_hint:
                    console.print(f"    {e.recovery_hint}")
                raise typer.Exit(1)

        if not wait:
            console.print()
            console.print(f"Deployment ID: {deployment.deployment_id}")
            console.print(f"Status: {deployment.state}")
            console.print()
            console.print("Check status with:")
            console.print(f"  runtm status {deployment.deployment_id}")
            return

        # Wait for completion
        with phase_span("poll_status"):
            poll_start_time = time.time()
            last_state = deployment.state

            with Live(console=console, refresh_per_second=4) as live:
                while True:
                    elapsed = time.time() - poll_start_time
                    if elapsed > timeout:
                        live.stop()
                        emit_deploy_failed("timeout", state_reached=deployment.state)
                        console.print(f"[red]✗[/red] Deployment timed out after {timeout}s")
                        console.print()
                        console.print("Check status with:")
                        console.print(f"  runtm status {deployment.deployment_id}")
                        raise typer.Exit(1)

                    # Update display
                    spinner = Spinner("dots", text=f" Deploying... ({deployment.state})")
                    live.update(spinner)

                    # Check status
                    try:
                        deployment = client.get_deployment(deployment.deployment_id)
                    except RuntmError:
                        pass  # Keep polling

                    if deployment.state != last_state:
                        last_state = deployment.state

                    # Check terminal states
                    if deployment.state == "ready":
                        live.stop()
                        break
                    elif deployment.state == "failed":
                        live.stop()
                        emit_deploy_failed("deployment_failed", state_reached="failed")
                        console.print(f"[red]✗[/red] Deployment failed")
                        if deployment.error_message:
                            console.print(f"    {deployment.error_message}")
                        console.print()
                        console.print("View logs with:")
                        console.print(f"  runtm logs {deployment.deployment_id}")
                        raise typer.Exit(1)

                    time.sleep(2)

        # Success!
        duration_ms = (time.time() - deploy_start_time) * 1000
        duration_secs = duration_ms / 1000
        emit_deploy_completed(duration_ms, version=deployment.version, template=manifest.template)

        console.print(f"[green]✓[/green] Deployed in {duration_secs:.1f}s")
        console.print()
        console.print(f"  URL: {deployment.url}")
        console.print(f"  ID:  {deployment.deployment_id}")
        console.print()
        console.print("Next steps:")
        console.print(f"  runtm status {deployment.deployment_id}")
        console.print(f"  runtm logs {deployment.deployment_id}")
        console.print(f"  curl {deployment.url}/health")

