"""Verify-json command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..hooks import hookimpl
from ..schema import PDFRepresentation

_MAX_JSON_SIZE = 10 * 1024 * 1024  # 10 MB


def _check_json_size(path: Path, max_size: int = _MAX_JSON_SIZE) -> None:
    """Raise ClickException if *path* exceeds *max_size* bytes."""
    size = path.stat().st_size
    if size > max_size:
        raise click.ClickException(
            f"JSON file too large: {path.name} ({size} bytes). Maximum allowed is {max_size} bytes."
        )


@click.command(name="verify-json")
@click.argument("json_file", type=click.Path(exists=True, path_type=Path))
def verify_json_command(json_file: Path) -> None:
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


@hookimpl
def register_commands() -> list[click.Command]:
    """Register verify-json command."""
    return [verify_json_command]
