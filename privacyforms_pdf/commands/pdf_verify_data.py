"""Verify-data command for pdf-forms CLI."""

from __future__ import annotations

from pathlib import Path

import click

from ..hooks import hookimpl
from ..json_utils import (
    MAX_JSON_SIZE,
    load_json_object,
)
from ..json_utils import (
    check_json_size as _base_check_json_size,
)
from ..schema import PDFRepresentation


def _check_json_size(path: Path, max_size: int = MAX_JSON_SIZE) -> None:
    """Raise ClickException if *path* exceeds *max_size* bytes."""
    try:
        _base_check_json_size(path, max_size=max_size)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _valid_field_keys(form_data: PDFRepresentation, key_mode: str) -> set[str]:
    """Return the set of allowed sample-data keys for the selected key mode."""
    ids = {field.id for field in form_data.fields}
    names = {field.name for field in form_data.fields}
    if key_mode == "id":
        return ids
    if key_mode == "name":
        return names
    return ids | names


@click.command(name="verify-data")
@click.option(
    "--form-json",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the PDF form JSON file produced by the parser.",
)
@click.option(
    "--data-json",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the sample data JSON file with key:value pairs.",
)
@click.option(
    "--key-mode",
    type=click.Choice(["id", "name", "auto"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Validate sample data keys as field IDs, field names, or either.",
)
def verify_data_command(form_json: Path, data_json: Path, key_mode: str) -> None:
    """Validate that all keys in --data-json exist in --form-json."""
    try:
        _check_json_size(form_json)
        _check_json_size(data_json)

        form_text = form_json.read_text(encoding="utf-8")
        form_data = PDFRepresentation.model_validate_json(form_text)

        sample_data = load_json_object(data_json)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    valid_keys = _valid_field_keys(form_data, key_mode)
    errors: list[str] = []

    for key in sample_data:
        if key not in valid_keys:
            if key_mode == "id":
                label = "field IDs"
            elif key_mode == "name":
                label = "field names"
            else:
                label = "field names or IDs"
            errors.append(f"Key '{key}' not found in form {label}")

    if errors:
        message = "Validation failed with {} error(s):\n  - {}".format(
            len(errors), "\n  - ".join(errors)
        )
        raise click.ClickException(message)

    click.echo(f"Valid: all {len(sample_data)} key(s) exist in '{form_json}'")


@hookimpl
def register_commands() -> list[click.Command]:
    """Register verify-data command."""
    return [verify_data_command]
