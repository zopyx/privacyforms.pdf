"""Get-value command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..extractor import PDFFormError, PDFFormNotFoundError
from .utils import create_extractor


@click.command(name="get-value")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("field_name")
@click.pass_context
def get_value_command(
    ctx: click.Context,
    pdf_path: Path,
    field_name: str,  # noqa: ARG001
) -> None:
    """Get the value of a specific form field.

    PDF_PATH is the path to the PDF file to process.
    FIELD_NAME is the name of the field to retrieve.

    Example:
        pdf-forms get-value form.pdf "Candidate Name"
    """
    extractor = create_extractor()

    try:
        value = extractor.get_field_value(pdf_path, field_name)

        if value is None:
            raise click.ClickException(f"Field '{field_name}' not found")

        click.echo(value)

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFFormError as e:
        raise click.ClickException("Failed to get field value.") from e
