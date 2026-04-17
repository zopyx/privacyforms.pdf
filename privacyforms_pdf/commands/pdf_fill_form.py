"""Fill-form command for pdf-forms CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

import click

from ..extractor import FormValidationError, PDFFormError, PDFFormNotFoundError
from ..hooks import hookimpl
from .utils import create_extractor


@click.command(name="fill-form")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("json_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output PDF file path (modifies input if not provided)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate JSON data against form fields before filling (default: validate)",
)
@click.option(
    "--strict/--no-strict",
    default=False,
    help="Require all form fields to be provided (default: not strict)",
)
@click.option(
    "--field-keys",
    type=click.Choice(["name", "id", "auto"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Interpret JSON keys as field names, field IDs, or auto-detect either. Prefer IDs.",
)
@click.pass_context
def fill_form_command(
    ctx: click.Context,  # noqa: ARG001
    pdf_path: Path,
    json_path: Path,
    output: Path | None,
    validate: bool,
    strict: bool,
    field_keys: str,
) -> None:
    """Fill a PDF form with data from a JSON file.

    PDF_PATH is the path to the PDF form file.
    JSON_PATH is the path to the JSON file with form data.

    The JSON file must contain simple key:value pairs. Field IDs are the
    preferred key format. Field names and mixed keys remain supported.

        {"f-0": "John Smith", "f-3": true}

    Examples:
        pdf-forms fill-form form.pdf data.json -o filled.pdf
        pdf-forms fill-form form.pdf data.json -o filled.pdf --strict
        pdf-forms fill-form form.pdf data.json -o filled.pdf --no-validate
    """
    extractor = create_extractor()
    key_mode = cast("Literal['name', 'id', 'auto']", field_keys)

    try:
        form_data = extractor.load_form_data_json(json_path)

        # Validate if requested
        if validate:
            errors = extractor.validate_form_data(
                pdf_path,
                form_data,
                strict=strict,
                allow_extra_fields=False,
                key_mode=key_mode,
            )
            if errors:
                click.echo("Validation errors:", err=True)
                for error in errors:
                    click.echo(f"  - {error}", err=True)
                raise click.ClickException("Form validation failed")

            click.echo("✓ Form data validation passed")

        extractor.fill_form(
            pdf_path,
            form_data,
            output,
            validate=False,
            key_mode=key_mode,
        )

        if output:
            click.echo(f"✓ Form filled and saved to: {output}")
        else:
            click.echo(f"✓ Form filled: {pdf_path}")

    except PDFFormNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except FormValidationError as e:
        raise click.ClickException(str(e)) from e
    except PDFFormError as e:
        error_msg = str(e) if str(e) else "Failed to fill form."
        raise click.ClickException(error_msg) from e
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON file: {e}") from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e


@hookimpl
def register_commands() -> list[click.Command]:
    """Register fill-form command."""
    return [fill_form_command]
