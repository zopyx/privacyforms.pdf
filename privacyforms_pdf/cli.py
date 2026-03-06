"""Command-line interface for privacyforms-pdf."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .extractor import (
    PDFCPUError,
    PDFCPUExecutionError,
    PDFFormExtractor,
    PDFFormNotFoundError,
)


def create_extractor() -> PDFFormExtractor:
    """Create a PDFFormExtractor instance, handling errors gracefully.

    Returns:
        Configured PDFFormExtractor instance.

    Raises:
        click.ClickException: If pdfcpu is not found.
    """
    try:
        return PDFFormExtractor()
    except PDFCPUError as e:
        raise click.ClickException(str(e)) from e


@click.group()
@click.version_option(version="0.1.0", prog_name="pdf-forms")
def main() -> None:
    """PDF Form extraction and manipulation tools using pdfcpu.

    This CLI provides commands to extract, list, and fill PDF forms.
    Requires pdfcpu to be installed on your system.

    Visit https://pdfcpu.io/install for installation instructions.
    """
    pass


@main.command()
def check() -> None:
    """Check if pdfcpu is installed and working."""
    try:
        extractor = PDFFormExtractor()
        version = extractor.get_pdfcpu_version()
        click.echo(f"✓ pdfcpu is installed: {version}")
    except PDFCPUError as e:
        click.echo(f"✗ pdfcpu not found: {e}", err=True)
        click.echo("Please install pdfcpu: https://pdfcpu.io/install", err=True)
        sys.exit(1)


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output JSON file path (optional, prints to stdout if not provided)",
)
def extract(pdf_path: Path, output: Path | None) -> None:
    """Extract form data from a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Examples:
        pdf-forms extract form.pdf
        pdf-forms extract form.pdf -o data.json
    """
    extractor = create_extractor()

    try:
        if output:
            extractor.extract_to_json(pdf_path, output)
            click.echo(f"Form data extracted to: {output}")
        else:
            form_data = extractor.extract(pdf_path)
            # Output as formatted JSON
            json_output = json.dumps(form_data.raw_data, indent=2)
            click.echo(json_output)
    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException(f"Failed to extract form: {e.stderr or str(e)}") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
def list_fields(pdf_path: Path) -> None:
    """List all form fields in a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms list-fields form.pdf
    """
    extractor = create_extractor()

    try:
        fields = extractor.list_fields(pdf_path)

        if not fields:
            click.echo("No form fields found.")
            return

        # Calculate column widths for alignment
        type_width = max(len(f.field_type) for f in fields) + 2
        name_width = max(len(f.name) for f in fields) + 2

        # Print header
        header = f"{'Type':<{type_width}} {'Name':<{name_width}} Value"
        click.echo(header)
        click.echo("=" * len(header) * 2)

        # Print fields
        for field in fields:
            value_str = str(field.value)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            click.echo(f"{field.field_type:<{type_width}} {field.name:<{name_width}} {value_str}")

        click.echo(f"\nTotal fields: {len(fields)}")

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException(f"Failed to list fields: {e.stderr or str(e)}") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("field_name")
def get_value(pdf_path: Path, field_name: str) -> None:
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
    except PDFCPUExecutionError as e:
        raise click.ClickException(f"Failed to get value: {e.stderr or str(e)}") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
def info(pdf_path: Path) -> None:
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
    except PDFCPUExecutionError as e:
        raise click.ClickException(f"Failed to get info: {e.stderr or str(e)}") from e


if __name__ == "__main__":
    main()
