"""Info command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..extractor import PDFFormError
from ..hooks import hookimpl
from .utils import create_extractor


@click.command(name="info")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def info_command(ctx: click.Context, pdf_path: Path) -> None:  # noqa: ARG001
    """Check if a PDF contains a form.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms info form.pdf
    """
    extractor = create_extractor()

    try:
        has_form = extractor.has_form(pdf_path)
        if has_form:
            click.echo(f"✓ {pdf_path} contains a form")
        else:
            click.echo(f"✗ {pdf_path} does not contain a form")
    except PDFFormError as e:
        raise click.ClickException("Failed to get form info.") from e


@hookimpl
def register_commands() -> list[click.Command]:
    """Register info command."""
    return [info_command]
