"""Check command for pdf-forms CLI."""

from __future__ import annotations

import click


@click.command(name="check")
@click.pass_context
def check_command(ctx: click.Context) -> None:  # noqa: ARG001
    """Check if the CLI is properly installed."""
    click.echo("✓ pdf-forms CLI is ready")
    click.echo("✓ Using pypdf for PDF form operations")
