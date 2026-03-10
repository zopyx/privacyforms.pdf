"""Set-permissions command for pdf-forms CLI using pdfcpu."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

# Permission bit positions (PDF spec uses bits 3-12)
PERMISSION_BITS = {
    "print": 3,  # Bit 3: Print (rev2), print quality (rev>=3)
    "modify": 4,  # Bit 4: Modify other than controlled by bits 6,9,11
    "extract": 5,  # Bit 5: Extract (rev2), extract other than bit 10 (rev>=3)
    "annotations": 6,  # Bit 6: Add or modify annotations
    "fill_forms": 9,  # Bit 9: Fill in form fields (rev>=3)
    "extract_accessibility": 10,  # Bit 10: Extract (rev>=3)
    "assemble": 11,  # Bit 11: Modify/assemble (rev>=3)
    "print_high": 12,  # Bit 12: Print high-level (rev>=3)
}


def build_permission_bits(
    print_perm: bool = False,
    modify: bool = False,
    extract: bool = False,
    annotations: bool = False,
    fill_forms: bool = False,
    extract_accessibility: bool = False,
    assemble: bool = False,
    print_high: bool = False,
) -> str:
    """Build a 12-bit permission string from individual flags.

    Args:
        print_perm: Allow printing
        modify: Allow modification (except annotations/form fields)
        extract: Allow text/graphics extraction
        annotations: Allow adding/modifying annotations
        fill_forms: Allow filling form fields
        extract_accessibility: Allow extraction for accessibility
        assemble: Allow document assembly (insert, rotate, delete pages)
        print_high: Allow high-quality printing

    Returns:
        12-character binary string of permission bits.
    """
    # Initialize all bits to 0 (bits 1-12, index 0-11)
    bits = ["0"] * 12

    # Set bits based on permissions (PDF bits are 1-indexed, we use 0-indexed)
    if print_perm:
        bits[2] = "1"  # Bit 3
    if modify:
        bits[3] = "1"  # Bit 4
    if extract:
        bits[4] = "1"  # Bit 5
    if annotations:
        bits[5] = "1"  # Bit 6
    if fill_forms:
        bits[8] = "1"  # Bit 9
    if extract_accessibility:
        bits[9] = "1"  # Bit 10
    if assemble:
        bits[10] = "1"  # Bit 11
    if print_high:
        bits[11] = "1"  # Bit 12

    return "".join(bits)


@click.command(name="set-permissions")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("output_path", type=click.Path(path_type=Path), required=False)
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
    output_path: Path | None,
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
    OUTPUT_PATH is the optional output path (modifies input if not provided).

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
    # Build pdfcpu permissions set command
    cmd = [pdfcpu_path, "permissions", "set"]

    # Determine permission value (priority: custom_bits > preset > individual flags)
    if custom_bits:
        # Validate custom bits (hex or binary)
        perm_value = custom_bits.strip().upper()
        if not all(c in "01" for c in perm_value) and not all(
            c in "0123456789ABCDEF" for c in perm_value
        ):
            raise click.ClickException(
                "Invalid --custom-bits value. Must be hex (e.g., 'F3C') "
                "or binary (e.g., '111100111100')"
            )
    elif permissions:
        # Use preset
        perm_value = permissions.lower()
    else:
        # Build from individual flags (default all False = none)
        perm_value = build_permission_bits(
            print_perm=print_perm,
            modify=modify_perm,
            extract=extract_perm,
            annotations=annotations_perm,
            fill_forms=fill_forms_perm,
            extract_accessibility=extract_accessibility_perm,
            assemble=assemble_perm,
            print_high=print_high_perm,
        )

    cmd.extend(["-perm", perm_value])

    # Add passwords
    if user_password:
        cmd.extend(["-upw", user_password])
    cmd.extend(["-opw", owner_password])

    # Add input and output files
    cmd.append(str(pdf_path))
    if output_path:
        cmd.append(str(output_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # Handle errors manually
        )

        # Check for specific error conditions
        stderr_lower = result.stderr.lower() if result.stderr else ""
        stdout_lower = result.stdout.lower() if result.stdout else ""

        # Owner password required
        if (
            "please provide the owner password" in stderr_lower
            or "please provide the owner password" in stdout_lower
        ):
            raise click.ClickException(
                "Incorrect owner password. The owner password is required to modify permissions."
            )

        # Document not encrypted
        if "not encrypted" in stderr_lower or "not encrypted" in stdout_lower:
            raise click.ClickException(
                "This document is not encrypted. Permissions can only be set on encrypted PDFs. "
                f"First encrypt the PDF using: pdf-forms encrypt {pdf_path} -opw <password>"
            )

        # PDF processing errors
        if "required entry" in stderr_lower or "dict=" in stderr_lower:
            raise click.ClickException(
                f"pdfcpu could not process this PDF: {result.stderr.strip()}\n\n"
                "This error often occurs when the PDF has malformed form fields or is corrupted."
            ) from None

        # Check for other errors
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Failed to set permissions"
            if "command not found" in error_msg.lower() or "not recognized" in error_msg.lower():
                raise click.ClickException(
                    f"pdfcpu not found at '{pdfcpu_path}'. "
                    "Please install pdfcpu or provide the correct path with --pdfcpu-path"
                ) from None
            raise click.ClickException(f"Failed to set permissions: {error_msg}") from None

        # Success
        if output_path:
            click.echo(f"✓ Permissions set and saved to: {output_path}")
        else:
            click.echo(f"✓ Permissions updated: {pdf_path}")

        # Show what was set
        if custom_bits:
            click.echo(f"  Custom bits: {custom_bits}")
        elif permissions:
            click.echo(f"  Preset: {permissions}")
        else:
            # Show which individual flags were set
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

        # Print any warnings/info from pdfcpu
        if result.stderr and "writing" not in result.stderr.lower():
            click.echo(result.stderr, err=True)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Failed to set permissions"
        raise click.ClickException(f"Failed to set permissions: {error_msg}") from e
    except FileNotFoundError as e:
        raise click.ClickException(
            f"pdfcpu not found at '{pdfcpu_path}'. "
            "Please install pdfcpu or provide the correct path with --pdfcpu-path"
        ) from e
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
