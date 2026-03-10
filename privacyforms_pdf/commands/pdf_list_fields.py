"""List-fields command for pdf-forms CLI."""

from __future__ import annotations

from collections import defaultdict
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


def _render_layout(fields: list[PDFField], pdf_name: str) -> None:
    """Render a visual layout representation of form fields.

    Groups fields by page and row (normalized_y), showing the structure
    of the form in a hierarchical console view.

    Args:
        fields: List of PDFField objects.
        pdf_name: Name of the PDF file for the title.
    """
    console = Console()
    console.print(f"\n[bold cyan]Form Layout: {pdf_name}[/bold cyan]\n")

    # Group fields by page
    fields_by_page: dict[int, list[PDFField]] = defaultdict(list)
    for field in fields:
        page = field.pages[0] if field.pages else 1
        fields_by_page[page].append(field)

    # Process each page
    for page_num in sorted(fields_by_page.keys()):
        page_fields = fields_by_page[page_num]
        console.print(f"[bold yellow]Page {page_num}[/bold yellow]")

        # Group fields by normalized_y (row)
        rows: dict[float, list[PDFField]] = defaultdict(list)
        for field in page_fields:
            norm_y = field.geometry.normalized_y if field.geometry else 0.0
            rows[norm_y].append(field)

        # Sort rows by normalized_y (descending - top to bottom)
        sorted_rows = sorted(rows.items(), key=lambda x: -x[0])

        for row_idx, (norm_y, row_fields) in enumerate(sorted_rows, 1):
            # Sort fields in row by x position (left to right)
            row_fields.sort(key=lambda f: f.geometry.x if f.geometry else 0)

            # Create row header
            y_display = f" (y≈{norm_y:.0f}pt)" if norm_y != 0.0 else ""
            console.print(f"  [dim]Row {row_idx}{y_display}[/dim]")

            # Display fields in this row
            for field in row_fields:
                # Build field representation
                name = field.name
                field_type = field.field_type
                value = field.value

                # Truncate long names
                display_name = name if len(name) <= 30 else name[:27] + "..."

                # Format value
                if isinstance(value, bool):
                    value_str = "☑" if value else "☐"
                elif value:
                    value_str = str(value)
                    if len(value_str) > 20:
                        value_str = value_str[:17] + "..."
                else:
                    value_str = ""

                # Type indicator
                type_icon = {
                    "textfield": "📝",
                    "checkbox": "☑",
                    "radiobuttongroup": "◉",
                    "combobox": "▼",
                    "listbox": "☰",
                    "datefield": "📅",
                    "signature": "✍",
                }.get(field_type, "•")

                # Build the field line
                type_str = f"[dim]({field_type})[/dim]"
                if value_str:
                    field_text = (
                        f"    {type_icon} [green]{display_name}[/green] "
                        f"{type_str} = [yellow]{value_str}[/yellow]"
                    )
                else:
                    field_text = f"    {type_icon} [green]{display_name}[/green] {type_str}"

                console.print(field_text)

        console.print()

    console.print(f"[dim]Total fields: {len(fields)}[/dim]\n")


@click.command(name="list-fields")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--geometry/--no-geometry",
    default=True,
    help="Show geometry information (default: true)",
)
@click.option(
    "--layout",
    is_flag=True,
    default=False,
    help="Show visual layout view grouped by rows",
)
@click.pass_context
def list_fields_command(
    ctx: click.Context,
    pdf_path: Path,
    geometry: bool,  # noqa: ARG001
    layout: bool,
) -> None:
    """List all form fields in a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Example:
        pdf-forms list-fields form.pdf
        pdf-forms list-fields form.pdf --no-geometry
        pdf-forms list-fields form.pdf --layout
    """
    extractor = create_extractor(extract_geometry=True)  # Always need geometry for sorting

    try:
        fields = extractor.list_fields(pdf_path)

        if not fields:
            click.echo("No form fields found.")
            return

        if layout:
            _render_layout(fields, pdf_path.name)
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
