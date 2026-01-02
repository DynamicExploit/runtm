"""Domain command - add custom domains to deployments."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from runtm_shared.errors import RuntmError

from ..api_client import APIClient
from ..config import get_token

console = Console()


def domain_add_command(
    deployment_id: str,
    hostname: str,
) -> None:
    """Add a custom domain to a deployment.

    One command to configure a custom domain with automatic SSL.

    Example:
        runtm domain add dep_abc123 api.example.com
    """
    from runtm_cli.telemetry import command_span, emit_domain_added

    with command_span("domain_add"):
        # Check auth
        token = get_token()
        if not token:
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
            raise typer.Exit(1)

        client = APIClient()

        # First verify deployment exists and is ready
        try:
            deployment = client.get_deployment(deployment_id)
        except RuntmError as e:
            console.print(f"[red]✗[/red] {e.message}")
            if e.recovery_hint:
                console.print(f"    {e.recovery_hint}")
            raise typer.Exit(1)

        if deployment.state != "ready":
            console.print(f"[red]✗[/red] Deployment is not ready (state: {deployment.state})")
            console.print("    Custom domains can only be added to running deployments.")
            raise typer.Exit(1)

        # Add custom domain
        console.print(
            f"[dim]Adding custom domain [cyan]{hostname}[/cyan] to [cyan]{deployment.name}[/cyan]...[/dim]"
        )

        try:
            domain_info = client.add_custom_domain(deployment_id, hostname)
        except RuntmError as e:
            console.print(f"[red]✗[/red] {e.message}")
            if e.recovery_hint:
                console.print(f"    {e.recovery_hint}")
            raise typer.Exit(1)

        if domain_info.error:
            console.print(f"[red]✗[/red] Failed to add domain: {domain_info.error}")
            raise typer.Exit(1)

        # For root domains (e.g., example.com), also add www subdomain automatically
        www_domain_info = None
        is_root_domain = hostname.count(".") == 1  # e.g., "example.com" has 1 dot
        www_hostname = f"www.{hostname}"

        if is_root_domain:
            console.print(f"[dim]Also adding [cyan]{www_hostname}[/cyan]...[/dim]")
            try:
                www_domain_info = client.add_custom_domain(deployment_id, www_hostname)
            except RuntmError:
                # Non-fatal: www is optional
                console.print(
                    "[yellow]⚠[/yellow] [dim]Could not add www subdomain automatically[/dim]"
                )
                www_domain_info = None

        # Success! Show DNS configuration
        console.print()
        if is_root_domain and www_domain_info:
            console.print(
                f"[green]✓[/green] Domains [cyan]{hostname}[/cyan] and [cyan]{www_hostname}[/cyan] added!"
            )
        else:
            console.print(f"[green]✓[/green] Domain [cyan]{hostname}[/cyan] added!")

        # Emit domain added event
        has_ssl = domain_info.certificate_status == "issued"
        emit_domain_added(has_ssl)

        console.print()

        # Collect all DNS records (including www if added)
        all_records = list(domain_info.dns_records) if domain_info.dns_records else []

        # Add www records if we have them
        if www_domain_info and www_domain_info.dns_records:
            all_records.extend(www_domain_info.dns_records)

        # Show DNS records to configure
        if all_records:
            # Sort records: A first (required), then AAAA (optional), then CNAME
            # Within each type, sort by name (@ first, then www)
            def record_priority(record):
                type_priority = {"A": 0, "AAAA": 1, "CNAME": 2}.get(record.record_type, 99)
                # @ comes before www
                name_priority = 0 if record.name == "@" else 1
                return (type_priority, name_priority)

            sorted_records = sorted(all_records, key=record_priority)

            dns_table = Table(title="Configure these DNS records", show_header=True)
            dns_table.add_column("Type", style="cyan")
            dns_table.add_column("Name", style="yellow")
            dns_table.add_column("Value", style="green")
            dns_table.add_column("Required", style="dim")

            has_ipv4 = any(r.record_type == "A" for r in sorted_records)
            has_ipv6 = any(r.record_type == "AAAA" for r in sorted_records)

            for record in sorted_records:
                if record.record_type == "A":
                    required = "[green]Yes[/green]"
                elif record.record_type == "AAAA":
                    required = "[yellow]Optional[/yellow]"
                elif record.record_type == "CNAME":
                    required = "[green]Yes[/green]"
                else:
                    required = "[green]Yes[/green]"

                dns_table.add_row(record.record_type, record.name, record.value, required)

            console.print(dns_table)
            console.print()

            # Show helpful note if only IPv6 is available
            if has_ipv6 and not has_ipv4:
                console.print(
                    "[yellow]⚠[/yellow] [dim]Note: Only IPv6 (AAAA) records are available. "
                    "Some DNS providers (like Squarespace) don't support IPv6.[/dim]"
                )
                console.print()
                console.print("[dim]To allocate a shared IPv4 address, run:[/dim]")
                # Get app name from deployment (preferred) or extract from URL
                app_name = deployment.app_name
                if not app_name and deployment.url:
                    # Fallback: extract from URL (works for both fly.dev and custom domains)
                    # https://runtm-abc123.fly.dev -> runtm-abc123
                    # https://runtm-abc123.runtm.com -> runtm-abc123
                    try:
                        from urllib.parse import urlparse

                        parsed = urlparse(deployment.url)
                        if parsed.hostname:
                            app_name = parsed.hostname.split(".")[0]
                    except Exception:
                        pass
                if app_name:
                    console.print(f"[cyan]  fly ips allocate-v4 --shared -a {app_name}[/cyan]")
                else:
                    console.print("[cyan]  fly ips allocate-v4 --shared -a <app-name>[/cyan]")
                console.print()
                console.print(
                    "[dim]Then run [cyan]runtm domain status[/cyan] again to see the IPv4 address.[/dim]"
                )
                console.print()

        # Show status
        status_color = {
            "issued": "green",
            "pending": "yellow",
            "awaiting_dns": "yellow",
            "error": "red",
        }.get(domain_info.certificate_status, "dim")

        status_text = {
            "issued": "✓ Certificate issued! Your domain is ready.",
            "pending": "⏳ Certificate pending... DNS validated, issuing certificate.",
            "awaiting_dns": "⏳ Awaiting DNS configuration. Add the records above.",
            "error": f"✗ Error: {domain_info.error}",
        }.get(domain_info.certificate_status, domain_info.certificate_status)

        console.print(f"[{status_color}]{status_text}[/{status_color}]")
        console.print()

        # Quick instructions
        instructions = """[dim]Next steps:[/dim]
1. Add the DNS records above to your domain registrar
2. Wait for DNS propagation (usually 1-5 minutes)
3. Check status: [cyan]runtm domain status {deployment_id} {hostname}[/cyan]

[dim]Once DNS is configured, runtm will automatically issue an SSL certificate.[/dim]"""

        console.print(instructions.format(deployment_id=deployment_id, hostname=hostname))


def domain_status_command(
    deployment_id: str,
    hostname: str,
) -> None:
    """Check status of a custom domain.

    Shows certificate status and any required DNS configuration.

    Example:
        runtm domain status dep_abc123 api.example.com
    """
    from runtm_cli.telemetry import command_span

    with command_span("domain_status"):
        # Check auth
        token = get_token()
        if not token:
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
            raise typer.Exit(1)

        client = APIClient()

        try:
            domain_info = client.get_custom_domain_status(deployment_id, hostname)
        except RuntmError as e:
            console.print(f"[red]✗[/red] {e.message}")
            if e.recovery_hint:
                console.print(f"    {e.recovery_hint}")
            raise typer.Exit(1)

        # Display status
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Domain", hostname)

        # Certificate status with color
        status = domain_info.certificate_status
        if status == "issued":
            status_display = f"[green]✓ {status}[/green]"
        elif status in ("pending", "awaiting_dns"):
            status_display = f"[yellow]⏳ {status}[/yellow]"
        else:
            status_display = f"[red]✗ {status}[/red]"

        table.add_row("Certificate", status_display)
        table.add_row(
            "Configured", "[green]Yes[/green]" if domain_info.configured else "[yellow]No[/yellow]"
        )

        if domain_info.error:
            table.add_row("Error", f"[red]{domain_info.error}[/red]")

        console.print(table)
        console.print()

        # Show DNS records if not fully configured
        if domain_info.dns_records and not domain_info.configured:
            # Sort records: A first (required), then AAAA (optional), then CNAME
            def record_priority(record):
                priority = {"A": 1, "AAAA": 2, "CNAME": 3}.get(record.record_type, 99)
                return priority

            sorted_records = sorted(domain_info.dns_records, key=record_priority)

            dns_table = Table(title="Required DNS records", show_header=True)
            dns_table.add_column("Type", style="cyan")
            dns_table.add_column("Name", style="yellow")
            dns_table.add_column("Value", style="green")
            dns_table.add_column("Required", style="dim")

            has_ipv4 = any(r.record_type == "A" for r in sorted_records)
            has_ipv6 = any(r.record_type == "AAAA" for r in sorted_records)

            for record in sorted_records:
                if record.record_type == "A":
                    required = "[green]Yes[/green]"
                elif record.record_type == "AAAA":
                    required = "[yellow]Optional[/yellow]"
                elif record.record_type == "CNAME":
                    required = "[green]Yes[/green]"
                else:
                    required = "[green]Yes[/green]"

                dns_table.add_row(record.record_type, record.name, record.value, required)

            console.print(dns_table)
            console.print()

            # Show helpful note if only IPv6 is available
            if has_ipv6 and not has_ipv4:
                console.print(
                    "[yellow]⚠[/yellow] [dim]Note: Only IPv6 (AAAA) records are available. "
                    "Some DNS providers (like Squarespace) don't support IPv6.[/dim]"
                )
                console.print()
                console.print("[dim]To allocate a shared IPv4 address, run:[/dim]")
                # Get deployment to extract app name
                try:
                    deployment = client.get_deployment(deployment_id)
                    app_name = deployment.app_name
                    if not app_name and deployment.url:
                        # Fallback: extract from URL
                        try:
                            from urllib.parse import urlparse

                            parsed = urlparse(deployment.url)
                            if parsed.hostname:
                                app_name = parsed.hostname.split(".")[0]
                        except Exception:
                            pass
                    if app_name:
                        console.print(f"[cyan]  fly ips allocate-v4 --shared -a {app_name}[/cyan]")
                    else:
                        console.print("[cyan]  fly ips allocate-v4 --shared -a <app-name>[/cyan]")
                except Exception:
                    console.print("[cyan]  fly ips allocate-v4 --shared -a <app-name>[/cyan]")
                console.print()
                console.print(
                    "[dim]Then run [cyan]runtm domain status[/cyan] again to see the IPv4 address.[/dim]"
                )
                console.print()

        # Success message if ready
        if domain_info.certificate_status == "issued":
            console.print("[green]✓[/green] Your domain is ready!")
            console.print(f"  [cyan]https://{hostname}[/cyan]")


def domain_remove_command(
    deployment_id: str,
    hostname: str,
    force: bool = False,
) -> None:
    """Remove a custom domain from a deployment.

    Example:
        runtm domain remove dep_abc123 api.example.com
    """
    from runtm_cli.telemetry import command_span, emit_domain_removed

    with command_span("domain_remove"):
        # Check auth
        token = get_token()
        if not token:
            console.print("[red]✗[/red] Not authenticated. Run `runtm login` first.")
            raise typer.Exit(1)

        # Confirm unless forced
        if not force:
            confirm = typer.confirm(f"Remove custom domain {hostname}?")
            if not confirm:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)

        client = APIClient()

        try:
            success = client.remove_custom_domain(deployment_id, hostname)
        except RuntmError as e:
            console.print(f"[red]✗[/red] {e.message}")
            if e.recovery_hint:
                console.print(f"    {e.recovery_hint}")
            raise typer.Exit(1)

        if success:
            emit_domain_removed()
            console.print(f"[green]✓[/green] Domain [cyan]{hostname}[/cyan] removed.")
        else:
            console.print("[red]✗[/red] Failed to remove domain.")
            raise typer.Exit(1)
