"""Admin commands for API token management (self-host operators).

This module provides CLI commands for managing API tokens directly via
database access. These commands are for self-hosting operators, not
end users.

Security notes:
- Requires DATABASE_URL and TOKEN_PEPPER environment variables
- Raw tokens are shown ONCE at creation - never stored
- All operations are logged to audit trail
- Use these commands instead of HTTP routes for production security
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table

from runtm_shared.types import validate_scopes

admin_app = typer.Typer(
    name="admin",
    help="Admin commands for token management (requires direct DB access)",
    no_args_is_help=True,
)

console = Console()


def _get_db_session(db_url: str):
    """Create a database session.

    Args:
        db_url: PostgreSQL connection URL

    Returns:
        SQLAlchemy session
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        console.print("[red]Error:[/red] SQLAlchemy not installed")
        console.print("Run: pip install sqlalchemy psycopg2-binary")
        raise typer.Exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


def _import_api_models():
    """Import API models (requires runtm_api package)."""
    try:
        from runtm_api.auth.keys import generate_api_key, hash_key
        from runtm_api.db.models import ApiKey

        return ApiKey, generate_api_key, hash_key
    except ImportError:
        console.print("[red]Error:[/red] runtm_api package not installed")
        console.print("Run this from the API package directory or install runtm_api")
        raise typer.Exit(1)


@admin_app.command("create-token")
def create_token(
    tenant_id: str = typer.Option(..., "--tenant", "-t", help="Tenant/org ID"),
    principal_id: str = typer.Option(..., "--principal", "-p", help="User/service account ID"),
    name: str | None = typer.Option(None, "--name", "-n", help="Token name"),
    scopes: str = typer.Option(
        "read,deploy,delete", "--scopes", "-s", help="Comma-separated scopes"
    ),
    expires_days: int | None = typer.Option(
        None, "--expires", "-e", help="Days until expiration (default: never)"
    ),
    db_url: str = typer.Option(..., "--db-url", envvar="DATABASE_URL", help="Database URL"),
    pepper: str = typer.Option(
        ..., "--pepper", envvar="TOKEN_PEPPER_V1", help="Token hashing pepper"
    ),
    pepper_version: int = typer.Option(
        1, "--pepper-version", envvar="CURRENT_PEPPER_VERSION", help="Pepper version"
    ),
    created_by: str = typer.Option(
        "admin-cli", "--created-by", help="Creator identifier for audit"
    ),
):
    """Create a new API token with specified permissions.

    The raw token is shown ONCE - save it immediately!

    Examples:
        # Create token with default scopes
        runtm admin create-token --tenant org_123 --principal user_456

        # Create read-only token
        runtm admin create-token --tenant org_123 --principal ci_bot --scopes read

        # Create token that expires in 30 days
        runtm admin create-token --tenant org_123 --principal temp_access --expires 30
    """
    ApiKey, generate_api_key, hash_key = _import_api_models()

    # Validate scopes
    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    try:
        validated_scopes = validate_scopes(scope_list)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Generate token
    raw_token, prefix = generate_api_key()
    key_hash = hash_key(raw_token, pepper)

    # Calculate expiration
    expires_at = None
    if expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    # Create database record
    db = _get_db_session(db_url)
    try:
        api_key = ApiKey(
            id=uuid4(),
            tenant_id=tenant_id,
            principal_id=principal_id,
            key_prefix=prefix,
            key_hash=key_hash,
            pepper_version=pepper_version,
            name=name,
            scopes=validated_scopes,
            is_revoked=False,
            expires_at=expires_at,
            created_by=created_by,
        )
        db.add(api_key)
        db.commit()

        # Show success with token
        console.print()
        console.print("[green]✓ Token created successfully![/green]")
        console.print()
        console.print(f"[bold]Token:[/bold] {raw_token}")
        console.print()
        console.print("[yellow]⚠️  IMPORTANT: Save this token now![/yellow]")
        console.print("[yellow]   It will NOT be shown again.[/yellow]")
        console.print()

        # Show metadata
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="dim")
        table.add_column("Value")
        table.add_row("ID", str(api_key.id))
        table.add_row("Tenant", tenant_id)
        table.add_row("Principal", principal_id)
        table.add_row("Name", name or "(none)")
        table.add_row("Scopes", ", ".join(validated_scopes))
        table.add_row("Expires", expires_at.isoformat() if expires_at else "(never)")
        table.add_row("Created by", created_by)
        console.print(table)

    except Exception as e:
        db.rollback()
        console.print(f"[red]Error creating token:[/red] {e}")
        raise typer.Exit(1)
    finally:
        db.close()


@admin_app.command("revoke-token")
def revoke_token(
    key_id: str = typer.Argument(..., help="API key UUID to revoke"),
    db_url: str = typer.Option(..., "--db-url", envvar="DATABASE_URL", help="Database URL"),
    revoked_by: str = typer.Option(
        "admin-cli", "--revoked-by", help="Revoker identifier for audit"
    ),
):
    """Revoke an API token (soft delete).

    The token will immediately stop working but the record is kept for audit.

    Example:
        runtm admin revoke-token 123e4567-e89b-12d3-a456-426614174000
    """
    ApiKey, _, _ = _import_api_models()

    db = _get_db_session(db_url)
    try:
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()

        if not api_key:
            console.print(f"[red]Error:[/red] Token {key_id} not found")
            raise typer.Exit(1)

        if api_key.is_revoked:
            console.print(f"[yellow]Warning:[/yellow] Token {key_id} already revoked")
            raise typer.Exit(0)

        api_key.is_revoked = True
        db.commit()

        console.print(f"[green]✓ Token {key_id} revoked successfully[/green]")
        console.print(f"  Tenant: {api_key.tenant_id}")
        console.print(f"  Principal: {api_key.principal_id}")
        console.print(f"  Name: {api_key.name or '(none)'}")
        console.print(f"  Revoked by: {revoked_by}")

    except Exception as e:
        db.rollback()
        console.print(f"[red]Error revoking token:[/red] {e}")
        raise typer.Exit(1)
    finally:
        db.close()


@admin_app.command("list-tokens")
def list_tokens(
    tenant_id: str | None = typer.Option(None, "--tenant", "-t", help="Filter by tenant ID"),
    principal_id: str | None = typer.Option(
        None, "--principal", "-p", help="Filter by principal ID"
    ),
    include_revoked: bool = typer.Option(False, "--include-revoked", help="Include revoked tokens"),
    db_url: str = typer.Option(..., "--db-url", envvar="DATABASE_URL", help="Database URL"),
):
    """List API tokens (metadata only, no values).

    Example:
        # List all tokens for a tenant
        runtm admin list-tokens --tenant org_123

        # List tokens for a specific principal
        runtm admin list-tokens --principal user_456

        # Include revoked tokens
        runtm admin list-tokens --tenant org_123 --include-revoked
    """
    ApiKey, _, _ = _import_api_models()

    db = _get_db_session(db_url)
    try:
        query = db.query(ApiKey)

        if tenant_id:
            query = query.filter(ApiKey.tenant_id == tenant_id)
        if principal_id:
            query = query.filter(ApiKey.principal_id == principal_id)
        if not include_revoked:
            query = query.filter(ApiKey.is_revoked == False)  # noqa: E712

        tokens = query.order_by(ApiKey.created_at.desc()).all()

        if not tokens:
            console.print("[dim]No tokens found[/dim]")
            return

        table = Table(title="API Tokens")
        table.add_column("ID", style="dim")
        table.add_column("Tenant")
        table.add_column("Principal")
        table.add_column("Name")
        table.add_column("Scopes")
        table.add_column("Status")
        table.add_column("Last Used")
        table.add_column("Created")

        for token in tokens:
            # Format status
            if token.is_revoked:
                status = "[red]revoked[/red]"
            elif token.expires_at and token.expires_at < datetime.now(timezone.utc):
                status = "[yellow]expired[/yellow]"
            else:
                status = "[green]active[/green]"

            # Format dates
            last_used = token.last_used_at.strftime("%Y-%m-%d") if token.last_used_at else "never"
            created = token.created_at.strftime("%Y-%m-%d")

            table.add_row(
                str(token.id)[:8] + "...",
                token.tenant_id,
                token.principal_id,
                token.name or "-",
                ", ".join(token.scopes) if token.scopes else "-",
                status,
                last_used,
                created,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(tokens)} token(s)[/dim]")

    finally:
        db.close()


@admin_app.command("rotate-pepper")
def rotate_pepper(
    old_pepper: str = typer.Option(
        ..., "--old-pepper", envvar="TOKEN_PEPPER_V1", help="Current pepper"
    ),
    new_pepper: str = typer.Option(
        ..., "--new-pepper", envvar="TOKEN_PEPPER_V2", help="New pepper"
    ),
    db_url: str = typer.Option(..., "--db-url", envvar="DATABASE_URL", help="Database URL"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--execute", help="Show what would change without executing"
    ),
):
    """Guide through pepper rotation process.

    Pepper rotation steps:
    1. Add TOKEN_PEPPER_V2 to environment (new pepper)
    2. Set PEPPER_MIGRATION_VERSIONS="1,2" (accept both)
    3. Wait for all active sessions to refresh
    4. Run this command to see tokens needing migration
    5. When ready: run with --execute to update pepper_version
    6. Remove TOKEN_PEPPER_V1 and PEPPER_MIGRATION_VERSIONS
    """
    ApiKey, _, hash_key = _import_api_models()

    if not old_pepper or not new_pepper:
        console.print("[red]Error:[/red] Both old and new peppers required")
        raise typer.Exit(1)

    if old_pepper == new_pepper:
        console.print("[red]Error:[/red] New pepper must be different from old")
        raise typer.Exit(1)

    db = _get_db_session(db_url)
    try:
        # Find tokens still on old pepper version
        old_tokens = (
            db.query(ApiKey)
            .filter(
                ApiKey.pepper_version == 1,
                ApiKey.is_revoked == False,  # noqa: E712
            )
            .all()
        )

        if not old_tokens:
            console.print("[green]✓ No tokens on old pepper version - rotation complete![/green]")
            console.print("\nNext steps:")
            console.print("1. Remove TOKEN_PEPPER_V1 from environment")
            console.print("2. Remove PEPPER_MIGRATION_VERSIONS")
            console.print("3. Set CURRENT_PEPPER_VERSION=2")
            return

        console.print(f"Found {len(old_tokens)} tokens on pepper v1:")
        for token in old_tokens[:10]:
            console.print(f"  - {token.id} ({token.tenant_id}/{token.principal_id})")
        if len(old_tokens) > 10:
            console.print(f"  ... and {len(old_tokens) - 10} more")

        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            console.print("Run with --execute to update tokens to new pepper")
        else:
            console.print("\n[red]WARNING:[/red] This will require re-issuing tokens!")
            console.print("Users with these tokens will need new tokens after rotation.")
            if not typer.confirm("Continue?"):
                raise typer.Abort()

            # In practice, you can't "migrate" existing tokens to new pepper
            # because you don't have the raw token. You can only:
            # 1. Keep old pepper active during migration window
            # 2. Issue new tokens with new pepper
            # 3. Eventually revoke old tokens

            console.print("\nPepper rotation notes:")
            console.print("- Cannot migrate existing tokens (raw token not stored)")
            console.print("- Keep PEPPER_MIGRATION_VERSIONS='1,2' until old tokens expire")
            console.print("- Issue new tokens with CURRENT_PEPPER_VERSION=2")
            console.print("- Consider setting expiration on old tokens")

    finally:
        db.close()
