"""Parse command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from ..hooks import hookimpl
from ..parser import extract_pdf_form
from ..schema import PDFField

if TYPE_CHECKING:
    from ..schema import PDFRepresentation


def _safe_write_text(path: Path, content: str) -> None:
    """Write text to *path*, refusing to overwrite via existing symlinks."""
    if path.is_symlink():
        raise click.ClickException(f"Refusing to write to symlink: {path}")
    path.write_text(content, encoding="utf-8")


def _print_rows(representation: PDFRepresentation, *, show_ids: bool = False) -> None:
    """Print a compact, human-readable overview of row groups and fields."""
    click.echo(
        f"\nParsed {len(representation.fields)} fields into {len(representation.rows)} rows\n"
    )
    for idx, row in enumerate(representation.rows, start=1):
        labels = [f.id if show_ids else f.name for f in row.fields if isinstance(f, PDFField)]
        click.echo(f"Row {idx:2d} (page {row.page_index}): {', '.join(labels)}")


@click.command(name="parse")
@click.argument("pdf_file", type=click.Path(exists=True, path_type=Path))
@click.argument("output_json", required=False, type=click.Path(path_type=Path))
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(path_type=Path),
    help="Output JSON file path (alternative to positional OUTPUT_JSON).",
)
@click.option(
    "--by-id",
    "by_id",
    is_flag=True,
    default=False,
    help="Display rows using field IDs instead of field names.",
)
def parse_command(
    pdf_file: Path, output_json: Path | None, output: Path | None, by_id: bool
) -> None:
    """Parse a fillable PDF into the canonical JSON schema.

    PDF_FILE is the path to the PDF file to parse.
    OUTPUT_JSON defaults to <pdf-stem>.json.
    """
    if output is not None:
        output_path = output
    else:
        output_path = output_json if output_json is not None else pdf_file.with_suffix(".json")

    try:
        representation = extract_pdf_form(pdf_file)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    json_text = representation.to_compact_json(indent=2)

    _safe_write_text(output_path, json_text)
    click.echo(f"Written to {output_path}")
    _print_rows(representation, show_ids=by_id)


@hookimpl
def register_commands() -> list[click.Command]:
    """Register parse command."""
    return [parse_command]
