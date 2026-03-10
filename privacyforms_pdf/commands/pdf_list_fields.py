"""List-fields command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..extractor import PDFField, PDFFormError, PDFFormNotFoundError
from .utils import create_extractor


def _format_list_fields_value(field: PDFField) -> str:
    """Build the value column text for the list-fields command."""
    value_parts = [str(field.value)] if str(field.value) else []

    if field.field_type in {"radiobuttongroup", "listbox"} and field.options:
        options_str = ", ".join(str(option) for option in field.options)
        value_parts.append(f"[options: {options_str}]")

    value_str = " ".join(value_parts)

    if len(value_str) > 50:
        return value_str[:47] + "..."
    return value_str


@click.command(name="list-fields")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--geometry/--no-geometry",
    default=True,
    help="Show geometry information (default: true)",
)
@click.pass_context
def list_fields_command(
    ctx: click.Context,
    pdf_path: Path,
    geometry: bool,  # noqa: ARG001
) -> None:
    """List all form fields in a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms list-fields form.pdf
        pdf-forms list-fields form.pdf --no-geometry
    """
    extractor = create_extractor(extract_geometry=geometry)

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
            value_str = _format_list_fields_value(field)
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
    except PDFFormError as e:
        raise click.ClickException("Failed to list fields.") from e
