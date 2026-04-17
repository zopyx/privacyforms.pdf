#!/usr/bin/env python3
"""Validate that data JSON keys exist as field IDs in a PDF form JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import click

try:
    from .pdf_schema import PDFRepresentation
except ImportError:
    from pdf_schema import PDFRepresentation  # type: ignore[import-not-found]

_MAX_JSON_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_JSON_DEPTH = 50


def _check_json_size(path: Path, max_size: int = _MAX_JSON_SIZE) -> None:
    """Raise ClickException if *path* exceeds *max_size* bytes."""
    size = path.stat().st_size
    if size > max_size:
        raise click.ClickException(
            f"JSON file too large: {path.name} ({size} bytes). "
            f"Maximum allowed is {max_size} bytes."
        )


def _check_json_depth(obj: object, depth: int = 0, max_depth: int = _MAX_JSON_DEPTH) -> None:
    """Raise ClickException if *obj* exceeds *max_depth* levels of nesting."""
    if depth > max_depth:
        raise click.ClickException(
            f"JSON structure exceeds maximum nesting depth of {max_depth}"
        )
    if isinstance(obj, dict):
        for value in obj.values():
            _check_json_depth(value, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _check_json_depth(item, depth + 1, max_depth)


def _safe_json_loads(text: str) -> object:
    """Parse JSON with a safe depth limit."""
    try:
        result = json.loads(text)
    except RecursionError as exc:
        raise click.ClickException(
            f"JSON structure is too deeply nested (maximum depth {_MAX_JSON_DEPTH})"
        ) from exc
    _check_json_depth(result)
    return result


def _require_json_object(data: object) -> dict[str, object]:
    """Require a top-level JSON object for sample form data."""
    if not isinstance(data, Mapping):
        raise click.ClickException("Sample data JSON must be a top-level object with field IDs as keys")
    return {str(key): value for key, value in data.items()}


@click.command()
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
def main(form_json: Path, data_json: Path) -> None:
    """Validate that all keys in --data-json exist as field IDs in --form-json.

    Raises ClickException if any data key is not found among the form field IDs.
    """
    _check_json_size(form_json)
    _check_json_size(data_json)

    form_text = form_json.read_text(encoding="utf-8")
    form_data = PDFRepresentation.model_validate_json(form_text)

    data_text = data_json.read_text(encoding="utf-8")
    sample_data = _require_json_object(_safe_json_loads(data_text))

    valid_ids = {field.id for field in form_data.fields}
    errors: list[str] = []

    for key in sample_data:
        if key not in valid_ids:
            errors.append(f"Key '{key}' not found in form field IDs")

    if errors:
        message = "Validation failed with {} error(s):\n  - {}".format(
            len(errors), "\n  - ".join(errors)
        )
        raise click.ClickException(message)

    click.echo(f"Valid: all {len(sample_data)} key(s) exist in '{form_json}'")


if __name__ == "__main__":
    main()
