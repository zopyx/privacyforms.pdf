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

# Whitelist of built-in command modules that are trusted
_TRUSTED_COMMAND_MODULES = {
    "privacyforms_pdf.commands.pdf_fill_form",
    "privacyforms_pdf.commands.pdf_info",
    "privacyforms_pdf.commands.pdf_parse",
    "privacyforms_pdf.commands.pdf_schema",
    "privacyforms_pdf.commands.pdf_verify_data",
    "privacyforms_pdf.commands.pdf_verify_json",
}

pm = pluggy.PluginManager("privacyforms_pdf")
pm.add_hookspecs(PDFFormsCommandsSpec)
pm.load_setuptools_entrypoints("privacyforms_pdf.commands")


def _is_trusted_plugin(plugin: object) -> bool:
    """Return True if *plugin* is from a trusted built-in module."""
    module = getattr(plugin, "__module__", None)
    return module in _TRUSTED_COMMAND_MODULES


def _register_commands(group: click.Group) -> None:
    """Register trusted plugin commands onto *group*."""
    for cmd_list in pm.hook.register_commands():
        for cmd in cmd_list:
            if not _is_trusted_plugin(cmd.callback):
                continue
            group.add_command(cmd)


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


_register_commands(main)


if __name__ == "__main__":  # pragma: no cover
    main()
