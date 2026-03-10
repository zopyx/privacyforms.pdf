"""Command-line interface for privacyforms-pdf."""

from __future__ import annotations

from importlib.metadata import version as get_version

import click

from .commands import (
    check_command,
    create_extractor,
    extract_command,
    fill_form_command,
    get_value_command,
    info_command,
    list_fields_command,
)
from .extractor import (
    FormValidationError,
    PDFField,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
)

# Re-export for backwards compatibility
__all__ = [
    "create_extractor",
    "main",
    # Exceptions for tests
    "FormValidationError",
    "PDFField",
    "PDFFormError",
    "PDFFormExtractor",
    "PDFFormNotFoundError",
]


@click.group()
@click.version_option(version=get_version("privacyforms-pdf"), prog_name="pdf-forms")
@click.pass_context
def main(ctx: click.Context) -> None:
    """PDF Form extraction and manipulation tools using pypdf.

    This CLI provides commands to extract, list, and fill PDF forms.
    Uses pypdf library for all operations.
    """
    # Store context for subcommands
    ctx.ensure_object(dict)


# Register commands
main.add_command(check_command)
main.add_command(extract_command)
main.add_command(list_fields_command)
main.add_command(get_value_command)
main.add_command(info_command)
main.add_command(fill_form_command)


if __name__ == "__main__":  # pragma: no cover
    main()
