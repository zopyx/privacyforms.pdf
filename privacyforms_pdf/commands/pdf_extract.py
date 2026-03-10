"""Extract command for pdf-forms CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..extractor import PDFFormError, PDFFormNotFoundError
from .utils import create_extractor


@click.command(name="extract")
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
    help="Output raw pypdf data (default: unified PDFField format)",
)
@click.pass_context
def extract_command(
    ctx: click.Context,
    pdf_path: Path,
    output: Path | None,
    raw: bool,  # noqa: ARG001
) -> None:
    """Extract form data from a PDF file.

    PDF_PATH is the path to the PDF file to process.

    Examples:
        pdf-forms extract form.pdf
        pdf-forms extract form.pdf -o data.json
        pdf-forms extract form.pdf --raw -o raw.json
    """
    extractor = create_extractor()

    try:
        if raw and output:
            # Raw mode: write raw data
            form_data = extractor.extract(pdf_path)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(form_data.raw_data, f, indent=2)
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
    except PDFFormError as e:
        raise click.ClickException("Failed to extract form.") from e
