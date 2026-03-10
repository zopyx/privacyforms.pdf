"""List-permissions command for pdf-forms CLI using pdfcpu."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import click

# Permission bit descriptions for high-level output
PERMISSION_DESCRIPTIONS = {
    3: ("print", "Print document"),
    4: ("modify", "Modify document (except annotations/form fields)"),
    5: ("extract", "Extract text and graphics"),
    6: ("annotations", "Add or modify annotations"),
    9: ("fill_forms", "Fill in form fields"),
    10: ("extract_accessibility", "Extract for accessibility"),
    11: ("assemble", "Assemble document (insert, rotate, delete pages)"),
    12: ("print_high", "Print high-quality / full resolution"),
}


def parse_permission_bits(output: str) -> dict:
    """Parse pdfcpu permission list output into a structured dict.

    Args:
        output: Raw output from pdfcpu permissions list command.

    Returns:
        Dictionary with permission bits info.
    """
    result = {
        "raw_bits": "",
        "hex_value": "",
        "permissions": {},
        "is_encrypted": False,
    }

    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()

        # Check if document is encrypted
        if "permission bits:" in line.lower():
            result["is_encrypted"] = True
            # Extract bit string and hex value
            match = re.search(
                r"permission bits:\s*([01]+)\s*\(x([0-9a-fA-F]+)\)",
                line,
                re.IGNORECASE,
            )
            if match:
                result["raw_bits"] = match.group(1)
                result["hex_value"] = match.group(2)

        # Parse individual bit lines
        bit_match = re.search(r"bit\s+(\d+):\s*(true|false)\s*\(([^)]+)\)", line, re.IGNORECASE)
        if bit_match:
            bit_num = int(bit_match.group(1))
            value = bit_match.group(2).lower() == "true"
            description = bit_match.group(3)
            result["permissions"][bit_num] = {
                "value": value,
                "description": description,
            }

    return result


def format_permissions_highlevel(permissions: dict) -> str:
    """Format permissions in a high-level human-readable way.

    Args:
        permissions: Dictionary from parse_permission_bits.

    Returns:
        Formatted string for display.
    """
    lines = []

    # Header
    lines.append("PDF Permissions")
    lines.append("=" * 50)

    if not permissions["is_encrypted"]:
        lines.append("Document is not encrypted - all permissions granted")
        return "\n".join(lines)

    lines.append(f"Raw permission bits: {permissions['raw_bits']} (0x{permissions['hex_value']})")
    lines.append("")

    # Group permissions by category
    allowed = []
    denied = []

    for bit_num in sorted(PERMISSION_DESCRIPTIONS.keys()):
        if bit_num in permissions["permissions"]:
            perm_info = permissions["permissions"][bit_num]
            name, description = PERMISSION_DESCRIPTIONS[bit_num]
            if perm_info["value"]:
                allowed.append(f"  ✓ {name:20} - {description}")
            else:
                denied.append(f"  ✗ {name:20} - {description}")

    if allowed:
        lines.append("Allowed permissions:")
        lines.extend(allowed)
        lines.append("")

    if denied:
        lines.append("Denied permissions:")
        lines.extend(denied)
        lines.append("")

    # Summary
    total_relevant = len([b for b in permissions["permissions"] if b in PERMISSION_DESCRIPTIONS])
    allowed_count = len(allowed)
    denied_count = len(denied)

    lines.append(
        f"Summary: {allowed_count} allowed, {denied_count} denied "
        f"out of {total_relevant} relevant permission bits"
    )

    return "\n".join(lines)


@click.command(name="list-permissions")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--user-password",
    "-upw",
    help="User password (if document has user password protection)",
)
@click.option(
    "--owner-password",
    "-opw",
    help="Owner password (alternative to user password)",
)
@click.option(
    "--raw",
    is_flag=True,
    help="Show raw pdfcpu output instead of high-level summary",
)
@click.option(
    "--pdfcpu-path",
    default="pdfcpu",
    help="Path to the pdfcpu binary (default: pdfcpu)",
)
@click.pass_context
def list_permissions_command(
    ctx: click.Context,  # noqa: ARG001
    pdf_path: Path,
    user_password: str | None,
    owner_password: str | None,
    raw: bool,
    pdfcpu_path: str,
) -> None:
    """List permissions of an encrypted PDF file using pdfcpu.

    PDF_PATH is the path to the PDF file to check.

    This command requires pdfcpu to be installed. It displays the permission
    bits set for an encrypted PDF in a human-readable format.

    Examples:
        pdf-forms list-permissions doc.pdf
        pdf-forms list-permissions doc.pdf -upw userpass
        pdf-forms list-permissions doc.pdf -opw ownerpass
        pdf-forms list-permissions doc.pdf --raw
    """
    # Build pdfcpu permissions list command
    cmd = [pdfcpu_path, "permissions", "list"]

    # Add passwords if provided
    if user_password:
        cmd.extend(["-upw", user_password])
    if owner_password:
        cmd.extend(["-opw", owner_password])

    cmd.append(str(pdf_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # Don't raise on non-zero exit, we handle errors manually
        )

        # Check for password prompt in output
        if (
            "please provide the correct password" in result.stderr.lower()
            or "please provide the correct password" in result.stdout.lower()
        ):
            raise click.ClickException(
                "This document requires a password. Please provide -upw (user password) "
                "or -opw (owner password)"
            )

        # Check for other errors
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Failed to list permissions"

            # pdfcpu binary not found
            if "command not found" in error_msg.lower() or "not recognized" in error_msg.lower():
                raise click.ClickException(
                    f"pdfcpu not found at '{pdfcpu_path}'. "
                    "Please install pdfcpu or provide the correct path with --pdfcpu-path"
                ) from None

            # PDF parsing/processing errors - might not be encrypted or malformed
            if "required entry" in error_msg.lower() or "dict=" in error_msg.lower():
                raise click.ClickException(
                    f"pdfcpu could not process this PDF: {error_msg}\n\n"
                    "This error often occurs when:\n"
                    "  1. The PDF is not encrypted (use 'pdf-forms info' to check)\n"
                    "  2. The PDF has malformed form fields\n"
                    "  3. The PDF is corrupted\n\n"
                    "To check if the PDF is encrypted, run:\n"
                    f"  pdf-forms info {pdf_path}"
                ) from None

            raise click.ClickException(f"Failed to list permissions: {error_msg}") from None

        # Output handling
        if raw:
            # Show raw pdfcpu output
            click.echo(result.stdout)
            if result.stderr:
                click.echo(result.stderr, err=True)
        else:
            # Parse and show high-level output
            permissions = parse_permission_bits(result.stdout)

            # Check if document is not encrypted
            if not permissions["is_encrypted"] and "permission bits" not in result.stdout.lower():
                # Check stdout for non-encrypted indication
                click.echo("Document is not encrypted - all permissions granted")
                return

            formatted = format_permissions_highlevel(permissions)
            click.echo(formatted)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Failed to list permissions"
        raise click.ClickException(f"Failed to list permissions: {error_msg}") from e
    except FileNotFoundError as e:
        raise click.ClickException(
            f"pdfcpu not found at '{pdfcpu_path}'. "
            "Please install pdfcpu or provide the correct path with --pdfcpu-path"
        ) from e
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
