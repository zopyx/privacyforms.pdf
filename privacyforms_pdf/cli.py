"""Command-line interface for privacyforms-pdf."""

from __future__ import annotations

from importlib.metadata import version as get_version

import click
import pluggy

from .commands import create_extractor
from .hooks import PDFFormsCommandsSpec

# Re-export for backwards compatibility
__all__ = [
    "create_extractor",
    "main",
]

pm = pluggy.PluginManager("privacyforms_pdf")
pm.add_hookspecs(PDFFormsCommandsSpec)
pm.load_setuptools_entrypoints("privacyforms_pdf.commands")


@click.group()
@click.version_option(version=get_version("privacyforms-pdf"), prog_name="pdf-forms")
@click.pass_context
def main(ctx: click.Context) -> None:
    """PDF Form extraction and manipulation tools using pypdf.

    This CLI provides commands to parse, fill, and validate PDF forms.
    Uses pypdf library for all operations.
    """
    # Store context for subcommands
    ctx.ensure_object(dict)


# Register commands from plugins
for cmd_list in pm.hook.register_commands():
    for cmd in cmd_list:
        main.add_command(cmd)


if __name__ == "__main__":  # pragma: no cover
    main()
