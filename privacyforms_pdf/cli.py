"""Command-line interface for privacyforms-pdf."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .extractor import (
    FormValidationError,
    PDFCPUError,
    PDFCPUExecutionError,
    PDFFormExtractor,
    PDFFormNotFoundError,
)


def create_extractor(geometry_backend: str = "auto") -> PDFFormExtractor:
    """Create a PDFFormExtractor instance, handling errors gracefully.

    Args:
        geometry_backend: Geometry extraction backend to use.

    Returns:
        Configured PDFFormExtractor instance.

    Raises:
        click.ClickException: If pdfcpu is not found.
    """
    try:
        return PDFFormExtractor(geometry_backend=geometry_backend)
    except PDFCPUError as e:
        raise click.ClickException(str(e)) from e


@click.group()
@click.version_option(version="0.1.2", prog_name="pdf-forms")
@click.option(
    "--geometry-backend",
    type=click.Choice(["auto", "pymupdf", "pdfplumber", "none"], case_sensitive=False),
    default="auto",
    help="Geometry extraction backend (default: auto)",
)
@click.pass_context
def main(ctx: click.Context, geometry_backend: str) -> None:
    """PDF Form extraction and manipulation tools using pdfcpu.

    This CLI provides commands to extract, list, and fill PDF forms.
    Requires pdfcpu to be installed on your system.

    Geometry extraction (field positions and sizes) is automatically
    performed if pymupdf or pdfplumber is installed.

    Visit https://pdfcpu.io/install for installation instructions.
    """
    # Store geometry_backend in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["geometry_backend"] = geometry_backend


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Check if pdfcpu is installed and working."""
    try:
        geometry_backend = ctx.obj["geometry_backend"]
        extractor = PDFFormExtractor(geometry_backend=geometry_backend)
        version = extractor.get_pdfcpu_version()
        click.echo(f"✓ pdfcpu is installed: {version}")

        # Check geometry support
        from .extractor import get_available_geometry_backends

        backends = get_available_geometry_backends()
        if backends:
            click.echo(f"✓ Geometry extraction available: {', '.join(backends)}")
        else:
            click.echo("ℹ Geometry extraction not available (install pymupdf or pdfplumber)")
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
@click.option(
    "--raw/--unified",
    default=False,
    help="Output raw pdfcpu data (default: unified PDFField format)",
)
@click.pass_context
def extract(ctx: click.Context, pdf_path: Path, output: Path | None, raw: bool) -> None:
    """Extract form data from a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Examples:
        pdf-forms extract form.pdf
        pdf-forms extract form.pdf -o data.json
        pdf-forms extract form.pdf --raw -o raw.json
    """
    geometry_backend = ctx.obj["geometry_backend"]
    extractor = create_extractor(geometry_backend)

    try:
        if raw and output:
            # Raw mode: use pdfcpu's native export
            extractor.extract_to_json(pdf_path, output)
            click.echo(f"Raw form data extracted to: {output}")
        elif raw:
            # Raw mode to stdout
            form_data = extractor.extract(pdf_path)
            json_output = json.dumps(form_data.raw_data, indent=2)
            click.echo(json_output)
        elif output:
            # Unified mode with file output
            form_data = extractor.extract(pdf_path)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(form_data.to_dict(), f, indent=2)
            click.echo(f"Unified form data extracted to: {output}")
        else:
            # Unified mode to stdout
            form_data = extractor.extract(pdf_path)
            click.echo(form_data.to_json())
    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException("Failed to extract form.") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--geometry/--no-geometry",
    default=True,
    help="Show geometry information (default: true)",
)
@click.pass_context
def list_fields(ctx: click.Context, pdf_path: Path, geometry: bool) -> None:
    """List all form fields in a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms list-fields form.pdf
        pdf-forms list-fields form.pdf --no-geometry
    """
    geometry_backend = ctx.obj["geometry_backend"]
    if not geometry:
        geometry_backend = "none"

    extractor = create_extractor(geometry_backend)

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
        if geometry:
            header += "     Page  Position (x, y)     Size (w×h)"
        click.echo(header)
        click.echo("=" * len(header) * 2)

        # Print fields
        for field in fields:
            value_str = str(field.value)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            line = f"{field.field_type:<{type_width}} {field.name:<{name_width}} {value_str}"

            if geometry and field.geometry:
                geom = field.geometry
                pos = f"({geom.x:.1f}, {geom.y:.1f})"
                size = f"{geom.width:.1f}×{geom.height:.1f}"
                line += f"    {geom.page:>3}  {pos:<18}  {size}"
            elif geometry:
                line += "    N/A"

            click.echo(line)

        click.echo(f"\nTotal fields: {len(fields)}")

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException("Failed to list fields.") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("field_name")
@click.pass_context
def get_value(ctx: click.Context, pdf_path: Path, field_name: str) -> None:
    """Get the value of a specific form field.

    PDF_PATH is the path to the PDF file to process.
    FIELD_NAME is the name of the field to retrieve.

    Example:
        pdf-forms get-value form.pdf "Candidate Name"
    """
    geometry_backend = ctx.obj["geometry_backend"]
    extractor = create_extractor(geometry_backend)

    try:
        value = extractor.get_field_value(pdf_path, field_name)

        if value is None:
            raise click.ClickException(f"Field '{field_name}' not found")

        click.echo(value)

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException("Failed to get field value.") from e


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def info(ctx: click.Context, pdf_path: Path) -> None:
    """Check if a PDF contains a form.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms info form.pdf
    """
    geometry_backend = ctx.obj["geometry_backend"]
    extractor = create_extractor(geometry_backend)

    try:
        has_form = extractor.has_form(pdf_path)
        if has_form:
            click.echo(f"✓ {pdf_path} contains a form")
        else:
            click.echo(f"✗ {pdf_path} does not contain a form")
    except PDFCPUExecutionError as e:
        raise click.ClickException("Failed to get form info.") from e


@main.command("fill-form")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("json_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output PDF file path (modifies input if not provided)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate JSON data against form fields before filling (default: validate)",
)
@click.option(
    "--strict/--no-strict",
    default=False,
    help="Require all form fields to be provided (default: not strict)",
)
@click.pass_context
def fill_form(
    ctx: click.Context,
    pdf_path: Path,
    json_path: Path,
    output: Path | None,
    validate: bool,
    strict: bool,
) -> None:
    """Fill a PDF form with data from a JSON file.

    PDF_PATH is the path to the PDF form file.
    JSON_PATH is the path to the JSON file with form data.

    The JSON file must contain simple key:value pairs where keys are field names
    and values are the values to fill:

        {"Candidate Name": "John Smith", "Full time": true}

    Examples:
        pdf-forms fill-form form.pdf data.json -o filled.pdf
        pdf-forms fill-form form.pdf data.json -o filled.pdf --strict
        pdf-forms fill-form form.pdf data.json -o filled.pdf --no-validate
    """
    geometry_backend = ctx.obj["geometry_backend"]
    extractor = create_extractor(geometry_backend)

    try:
        # Read and parse JSON
        with open(json_path, encoding="utf-8") as f:
            form_data = json.load(f)

        # Validate if requested
        if validate:
            errors = extractor.validate_form_data(
                pdf_path, form_data, strict=strict, allow_extra_fields=False
            )
            if errors:
                click.echo("Validation errors:", err=True)
                for error in errors:
                    click.echo(f"  - {error}", err=True)
                raise click.ClickException("Form validation failed")

            click.echo("✓ Form data validation passed")

        # Fill the form
        extractor.fill_form(pdf_path, form_data, output, validate=False)

        if output:
            click.echo(f"✓ Form filled and saved to: {output}")
        else:
            click.echo(f"✓ Form filled: {pdf_path}")

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except FormValidationError as e:
        raise click.ClickException(str(e)) from e
    except PDFCPUExecutionError as e:
        raise click.ClickException("Failed to fill form.") from e
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON file: {e}") from e


if __name__ == "__main__":  # pragma: no cover
    main()
