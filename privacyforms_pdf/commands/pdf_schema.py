"""Schema command for pdf-forms CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..extractor import PDFFormService
from ..hooks import hookimpl


@click.command(name="schema")
@click.argument("output_json", required=False, type=click.Path(path_type=Path))
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(path_type=Path),
    help="Output JSON file path (alternative to positional OUTPUT_JSON).",
)
def schema_command(output_json: Path | None, output: Path | None) -> None:
    """Output the JSON Schema of the canonical PDFRepresentation model.

    OUTPUT_JSON defaults to "pdfrepresentation-schema.json".
    """
    if output is not None:
        output_path = output
    else:
        default_name = Path("pdfrepresentation-schema.json")
        output_path = output_json if output_json is not None else default_name

    schema = PDFFormService.get_json_schema()
    json_text = json.dumps(schema, indent=2)

    if output_path.is_symlink():
        raise click.ClickException(f"Refusing to write to symlink: {output_path}")

    output_path.write_text(json_text, encoding="utf-8")
    click.echo(f"Written to {output_path}")


@hookimpl
def register_commands() -> list[click.Command]:
    """Register schema command."""
    return [schema_command]
