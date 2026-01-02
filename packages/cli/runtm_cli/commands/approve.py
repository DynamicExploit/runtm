"""Approve command - apply agent-proposed changes from runtm.requests.yaml.

In v1, this is informational (applies requests but doesn't block deploys).
In org mode (future), approval may be required before deploy.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from runtm_shared.manifest import Connection, EnvVar, Features, Manifest
from runtm_shared.requests import RequestedFeatures, RequestsFile

console = Console()


def load_requests(path: Path) -> RequestsFile | None:
    """Load runtm.requests.yaml if it exists.

    Args:
        path: Project directory

    Returns:
        RequestsFile or None if not found
    """
    requests_path = path / "runtm.requests.yaml"
    if not requests_path.exists():
        return None

    try:
        return RequestsFile.from_file(requests_path)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not parse runtm.requests.yaml: {e}")
        return None


def merge_env_vars(
    existing: list[EnvVar],
    requested: list[EnvVar],
) -> tuple[list[EnvVar], list[str]]:
    """Merge requested env vars into existing list.

    Args:
        existing: Current env_schema
        requested: Requested env vars

    Returns:
        Tuple of (merged list, list of added names)
    """
    existing_names = {ev.name for ev in existing}
    merged = list(existing)
    added = []

    for req in requested:
        if req.name not in existing_names:
            merged.append(req)
            added.append(req.name)

    return merged, added


def merge_connections(
    existing: list[Connection],
    requested: list[Connection],
) -> tuple[list[Connection], list[str]]:
    """Merge requested connections into existing list.

    Args:
        existing: Current connections
        requested: Requested connections

    Returns:
        Tuple of (merged list, list of added names)
    """
    existing_names = {c.name for c in existing}
    merged = list(existing)
    added = []

    for req in requested:
        if req.name not in existing_names:
            merged.append(req)
            added.append(req.name)

    return merged, added


def merge_features(
    existing: Features,
    requested: RequestedFeatures,
) -> tuple[Features, list[str]]:
    """Merge requested features into existing features.

    Args:
        existing: Current features
        requested: Requested features

    Returns:
        Tuple of (merged features, list of changes)
    """
    changes = []
    new_database = existing.database
    new_auth = existing.auth

    if requested.database is not None and requested.database != existing.database:
        new_database = requested.database
        changes.append(f"database: {requested.database}")

    if requested.auth is not None and requested.auth != existing.auth:
        new_auth = requested.auth
        changes.append(f"auth: {requested.auth}")

    merged = Features(database=new_database, auth=new_auth)
    return merged, changes


def approve_command(
    path: Path = Path("."),
    dry_run: bool = False,
) -> None:
    """Apply agent-proposed changes from runtm.requests.yaml.

    Merges requested env vars, connections, and egress allowlist into
    runtm.yaml. After approval, the requests file is deleted.

    In v1, this is informational - deploys work without approval.
    In org mode (future), approval may be required.
    """
    # Load manifest
    manifest_path = path / "runtm.yaml"
    if not manifest_path.exists():
        console.print("[red]✗[/red] No runtm.yaml found. Run `runtm init` first.")
        raise typer.Exit(1)

    try:
        manifest = Manifest.from_file(manifest_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Invalid manifest: {e}")
        raise typer.Exit(1)

    # Load requests
    requests = load_requests(path)
    if requests is None:
        console.print("[dim]No runtm.requests.yaml found. Nothing to approve.[/dim]")
        return

    if requests.is_empty():
        console.print("[dim]runtm.requests.yaml has no pending requests.[/dim]")
        return

    # Show summary
    console.print(f"[bold]Pending requests:[/bold] {requests.get_summary()}")
    console.print()

    # Show features request
    if requests.requested.features and requests.requested.features.has_changes():
        console.print("[bold]Requested features:[/bold]")
        if requests.requested.features.database is not None:
            status = "✓ enable" if requests.requested.features.database else "✗ disable"
            console.print(f"  - database: {status}")
        if requests.requested.features.auth is not None:
            status = "✓ enable" if requests.requested.features.auth else "✗ disable"
            console.print(f"  - auth: {status}")
        if requests.requested.features.reason:
            console.print(f"    [dim]Reason: {requests.requested.features.reason}[/dim]")
        console.print()

    # Show details in a table
    if requests.requested.env_vars:
        table = Table(title="Requested Environment Variables")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Required")
        table.add_column("Secret")
        table.add_column("Reason")

        for ev in requests.requested.env_vars:
            table.add_row(
                ev.name,
                ev.type.value,
                "✓" if ev.required else "",
                "🔒" if ev.secret else "",
                ev.reason or "",
            )

        console.print(table)
        console.print()

    if requests.requested.egress_allowlist:
        console.print("[bold]Requested egress allowlist:[/bold]")
        for domain in requests.requested.egress_allowlist:
            console.print(f"  - {domain}")
        console.print()

    if requests.requested.connections:
        console.print("[bold]Requested connections:[/bold]")
        for conn in requests.requested.connections:
            console.print(f"  - {conn.name}: {', '.join(conn.env_vars)}")
            if conn.reason:
                console.print(f"    [dim]{conn.reason}[/dim]")
        console.print()

    if requests.notes:
        console.print("[bold]Notes from agent:[/bold]")
        for note in requests.notes:
            console.print(f"  • {note}")
        console.print()

    if dry_run:
        console.print("[yellow]Dry run - no changes made[/yellow]")
        return

    # Apply changes
    changes_made = []

    # Prepare all merged values first (before creating new Manifest)
    # This ensures dependent changes (e.g., auth + AUTH_SECRET) are applied together
    merged_features = manifest.features
    feature_changes: list[str] = []
    if requests.requested.features and requests.requested.features.has_changes():
        merged_features, feature_changes = merge_features(
            manifest.features, requests.requested.features
        )

    merged_env = manifest.env_schema
    added_env: list[str] = []
    if requests.requested.env_vars:
        new_env_vars = [ev.to_env_var() for ev in requests.requested.env_vars]
        merged_env, added_env = merge_env_vars(manifest.env_schema, new_env_vars)

    # Create new manifest with ALL changes together (features + env_vars)
    # This avoids validation errors from partial updates (e.g., auth=True without AUTH_SECRET)
    if feature_changes or added_env:
        manifest = Manifest(
            name=manifest.name,
            template=manifest.template,
            runtime=manifest.runtime,
            health_path=manifest.health_path,
            port=manifest.port,
            tier=manifest.tier,
            features=merged_features,
            volumes=manifest.volumes,
            env_schema=merged_env,
            connections=manifest.connections,
            policy=manifest.policy,
        )
        if feature_changes:
            changes_made.append(f"Updated features: {', '.join(feature_changes)}")
        if added_env:
            changes_made.append(f"Added {len(added_env)} env vars: {', '.join(added_env)}")

    # Merge connections
    if requests.requested.connections:
        new_connections = [
            Connection(name=c.name, env_vars=c.env_vars) for c in requests.requested.connections
        ]
        merged_conn, added_conn = merge_connections(manifest.connections, new_connections)
        if added_conn:
            manifest = Manifest(
                name=manifest.name,
                template=manifest.template,
                runtime=manifest.runtime,
                health_path=manifest.health_path,
                port=manifest.port,
                tier=manifest.tier,
                features=manifest.features,
                volumes=manifest.volumes,
                env_schema=manifest.env_schema,
                connections=merged_conn,
                policy=manifest.policy,
            )
            changes_made.append(f"Added {len(added_conn)} connections: {', '.join(added_conn)}")

    # Merge egress allowlist (into policy)
    if requests.requested.egress_allowlist:
        from runtm_shared.manifest import Policy

        current_policy = manifest.policy or Policy()
        existing_egress = set(current_policy.egress_allowlist)
        new_egress = [d for d in requests.requested.egress_allowlist if d not in existing_egress]

        if new_egress:
            updated_policy = Policy(
                mode=current_policy.mode,
                egress=current_policy.egress,
                egress_allowlist=list(existing_egress) + new_egress,
            )
            manifest = Manifest(
                name=manifest.name,
                template=manifest.template,
                runtime=manifest.runtime,
                health_path=manifest.health_path,
                port=manifest.port,
                tier=manifest.tier,
                features=manifest.features,
                volumes=manifest.volumes,
                env_schema=manifest.env_schema,
                connections=manifest.connections,
                policy=updated_policy,
            )
            changes_made.append(f"Added {len(new_egress)} egress domains")

    if not changes_made:
        console.print("[dim]All requested changes already exist in manifest.[/dim]")
    else:
        # Write updated manifest
        manifest_path.write_text(manifest.to_yaml())

        for change in changes_made:
            console.print(f"[green]✓[/green] {change}")

    # Delete requests file
    requests_path = path / "runtm.requests.yaml"
    if requests_path.exists():
        requests_path.unlink()
        console.print("[dim]Removed runtm.requests.yaml[/dim]")

    console.print()
    console.print("[green]✓[/green] Approval complete")

    # Remind about secrets
    secret_vars = [ev for ev in requests.requested.env_vars if ev.secret]
    if secret_vars:
        console.print()
        console.print("[bold]Next steps:[/bold] Set secret values:")
        for ev in secret_vars:
            console.print(f"  runtm secrets set {ev.name}=<value>")
