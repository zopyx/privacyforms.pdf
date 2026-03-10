"""List-fields command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

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

        # Create Rich table
        table = Table(
            title=f"Form Fields in {pdf_path.name}", show_header=True, header_style="bold"
        )

        # Add columns
        table.add_column("Type", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Value", style="yellow")
        if geometry:
            table.add_column("Page", justify="right", style="magenta")
            table.add_column("Position (x, y)", justify="center", style="blue")
            table.add_column("Size (w×h)", justify="center", style="blue")

        # Add rows
        for field in fields:
            value_str = _format_list_fields_value(field)
            row = [field.field_type, field.name, value_str]

            if geometry:
                if field.geometry:
                    geom = field.geometry
                    pos = f"({geom.x:.1f}, {geom.y:.1f})"
                    size = f"{geom.width:.1f}×{geom.height:.1f}"
                    row.extend([str(geom.page), pos, size])
                else:
                    row.extend(["N/A", "N/A", "N/A"])

            table.add_row(*row)

        # Print table
        console = Console()
        console.print(table)
        console.print(f"\nTotal fields: {len(fields)}")

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except PDFFormError as e:
        raise click.ClickException("Failed to list fields.") from e
