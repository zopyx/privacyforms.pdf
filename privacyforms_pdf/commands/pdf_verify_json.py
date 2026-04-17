"""Verify-json command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..hooks import hookimpl
from ..json_utils import MAX_JSON_SIZE
from ..json_utils import check_json_size as _base_check_json_size
from ..schema import PDFRepresentation


def _check_json_size(path: Path, max_size: int = MAX_JSON_SIZE) -> None:
    """Raise ClickException if *path* exceeds *max_size* bytes."""
    try:
        _base_check_json_size(path, max_size=max_size)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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
