#!/usr/bin/env python3
"""CLI utility to verify a JSON file against the PDFRepresentation schema."""

from __future__ import annotations

from pathlib import Path

import click

try:
    from .pdf_schema import PDFRepresentation
except ImportError:
    from pdf_schema import PDFRepresentation  # type: ignore[import-not-found]

_MAX_JSON_SIZE = 10 * 1024 * 1024  # 10 MB


def _check_json_size(path: Path, max_size: int = _MAX_JSON_SIZE) -> None:
    """Raise ClickException if *path* exceeds *max_size* bytes."""
    size = path.stat().st_size
    if size > max_size:
        raise click.ClickException(
            f"JSON file too large: {path.name} ({size} bytes). "
            f"Maximum allowed is {max_size} bytes."
        )


@click.command()
@click.argument("json_file", type=click.Path(exists=True, path_type=Path))
def main(json_file: Path) -> None:
    """Verify JSON_FILE against the PDFRepresentation schema."""
    _check_json_size(json_file)
    data = json_file.read_text(encoding="utf-8")
    try:
        PDFRepresentation.model_validate_json(data)
        click.echo(f"Valid: {json_file}")
    except Exception as exc:
        click.echo(f"Invalid: {json_file}", err=True)
        click.echo(str(exc), err=True)
        raise click.ClickException("Schema validation failed.") from exc


if __name__ == "__main__":
    main()
