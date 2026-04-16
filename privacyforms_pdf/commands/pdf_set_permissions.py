"""Set-permissions command for pdf-forms CLI using pdfcpu."""

from __future__ import annotations

from pathlib import Path

import click

from privacyforms_pdf.models import PDFFormError
from privacyforms_pdf.security import PDFSecurityManager, build_permission_bits

__all__ = ["PDFSecurityManager", "build_permission_bits", "set_permissions_command"]


@click.command(name="set-permissions")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--owner-password",
    "-opw",
    required=True,
    help="Owner password (required) - needed to modify permissions",
)
@click.option(
    "--user-password",
    "-upw",
    help="User password (optional) - if changing, provide new user password",
)
@click.option(
    "--permissions",
    "-perm",
    type=click.Choice(["none", "print", "all"], case_sensitive=False),
    help="Permission preset: 'none', 'print', or 'all' (overrides individual flags)",
)
@click.option(
    "--print",
    "print_perm",
    is_flag=True,
    help="Allow printing (Bit 3)",
)
@click.option(
    "--modify",
    "modify_perm",
    is_flag=True,
    help="Allow modification except annotations/forms (Bit 4)",
)
@click.option(
    "--extract",
    "extract_perm",
    is_flag=True,
    help="Allow text/graphics extraction (Bit 5)",
)
@click.option(
    "--annotations",
    "annotations_perm",
    is_flag=True,
    help="Allow adding/modifying annotations (Bit 6)",
)
@click.option(
    "--fill-forms",
    "fill_forms_perm",
    is_flag=True,
    help="Allow filling form fields (Bit 9)",
)
@click.option(
    "--extract-accessibility",
    "extract_accessibility_perm",
    is_flag=True,
    help="Allow extraction for accessibility (Bit 10)",
)
@click.option(
    "--assemble",
    "assemble_perm",
    is_flag=True,
    help="Allow document assembly (insert, rotate, delete pages) (Bit 11)",
)
@click.option(
    "--print-high",
    "print_high_perm",
    is_flag=True,
    help="Allow high-quality printing (Bit 12)",
)
@click.option(
    "--custom-bits",
    help=(
        "Custom permission bits in hex (e.g., 'F3C') or binary "
        "(e.g., '111100111100') - overrides all other options"
    ),
)
@click.option(
    "--pdfcpu-path",
    default="pdfcpu",
    help="Path to the pdfcpu binary (default: pdfcpu)",
)
@click.pass_context
def set_permissions_command(
    ctx: click.Context,  # noqa: ARG001
    pdf_path: Path,
    owner_password: str,
    user_password: str | None,
    permissions: str | None,
    print_perm: bool,
    modify_perm: bool,
    extract_perm: bool,
    annotations_perm: bool,
    fill_forms_perm: bool,
    extract_accessibility_perm: bool,
    assemble_perm: bool,
    print_high_perm: bool,
    custom_bits: str | None,
    pdfcpu_path: str,
) -> None:
    """Set permissions of an encrypted PDF file using pdfcpu.

    PDF_PATH is the path to the encrypted PDF file to modify.
    The file is modified in place.

    This command requires pdfcpu to be installed. The owner password is
    mandatory to modify permissions.

    You can set permissions using:
      - Permission presets (--permissions none|print|all)
      - Individual permission flags (--print, --modify, etc.)
      - Custom bits (--custom-bits)

    Permission bits (from PDF spec):
      Bit 3:  --print              - Print document
      Bit 4:  --modify             - Modify (except annotations/forms)
      Bit 5:  --extract            - Extract text/graphics
      Bit 6:  --annotations        - Add/modify annotations
      Bit 9:  --fill-forms         - Fill form fields
      Bit 10: --extract-accessibility - Extract for accessibility
      Bit 11: --assemble           - Document assembly
      Bit 12: --print-high         - High-quality printing

    Examples:
        # Presets
        pdf-forms set-permissions doc.pdf -opw ownerpass --permissions none
        pdf-forms set-permissions doc.pdf -opw ownerpass --permissions all

        # Individual flags (default is none if no preset specified)
        pdf-forms set-permissions doc.pdf -opw ownerpass --print
        pdf-forms set-permissions doc.pdf -opw ownerpass --print --extract

        # Multiple permissions
        pdf-forms set-permissions doc.pdf -opw opw --print --fill-forms --annotations

        # Custom bits (hex or binary)
        pdf-forms set-permissions doc.pdf -opw opw --custom-bits F3C
    """
    security = PDFSecurityManager(pdfcpu_path=pdfcpu_path)

    try:
        security.set_permissions(
            pdf_path,
            owner_password=owner_password,
            user_password=user_password,
            permissions_preset=permissions,
            print_perm=print_perm,
            modify=modify_perm,
            extract=extract_perm,
            annotations=annotations_perm,
            fill_forms=fill_forms_perm,
            extract_accessibility=extract_accessibility_perm,
            assemble=assemble_perm,
            print_high=print_high_perm,
            custom_bits=custom_bits,
        )

        click.echo(f"✓ Permissions updated: {pdf_path}")

        if custom_bits:
            click.echo(f"  Custom bits: {custom_bits}")
        elif permissions:
            click.echo(f"  Preset: {permissions}")
        else:
            active = []
            if print_perm:
                active.append("print")
            if modify_perm:
                active.append("modify")
            if extract_perm:
                active.append("extract")
            if annotations_perm:
                active.append("annotations")
            if fill_forms_perm:
                active.append("fill-forms")
            if extract_accessibility_perm:
                active.append("extract-accessibility")
            if assemble_perm:
                active.append("assemble")
            if print_high_perm:
                active.append("print-high")
            if active:
                click.echo(f"  Permissions: {', '.join(active)}")
            else:
                click.echo("  Permissions: none (most restrictive)")

    except PDFFormError as e:
        error_msg = str(e).lower()

        if "pdfcpu binary not found" in error_msg:
            raise click.ClickException(
                f"pdfcpu not found at '{pdfcpu_path}'. "
                "Please install pdfcpu or provide the correct path with --pdfcpu-path"
            ) from e

        if "incorrect owner password" in error_msg:
            raise click.ClickException(
                "Incorrect owner password. The owner password is required to modify permissions."
            ) from e

        if "not encrypted" in error_msg:
            raise click.ClickException(
                "This document is not encrypted. Permissions can only be set on encrypted PDFs. "
                f"First encrypt the PDF using: pdf-forms encrypt {pdf_path} -opw <password>"
            ) from e

        if "required entry" in error_msg or "dict=" in error_msg:
            raise click.ClickException(
                f"pdfcpu could not process this PDF: {e}\n\n"
                "This error often occurs when the PDF has malformed form fields or is corrupted."
            ) from None

        raise click.ClickException(f"Failed to set permissions: {e}") from e
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
