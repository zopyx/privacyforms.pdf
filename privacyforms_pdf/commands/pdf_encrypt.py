"""Encrypt command for pdf-forms CLI using pdfcpu."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click


@click.command(name="encrypt")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.argument("output_path", type=click.Path(path_type=Path), required=False)
@click.option(
    "--owner-password",
    "-opw",
    required=True,
    help="Owner password (mandatory) - grants full access to the document",
)
@click.option(
    "--user-password",
    "-upw",
    help="User password (optional) - required to open the document",
)
@click.option(
    "--mode",
    type=click.Choice(["rc4", "aes"], case_sensitive=False),
    default="aes",
    help="Encryption algorithm (default: aes)",
)
@click.option(
    "--key",
    "key_length",
    type=click.Choice(["40", "128", "256"], case_sensitive=False),
    default="256",
    help="Key length in bits (default: 256)",
)
@click.option(
    "--perm",
    "permissions",
    type=click.Choice(["none", "all"], case_sensitive=False),
    default="none",
    help="Permissions: 'none' for most restrictive, 'all' for full access (default: none)",
)
@click.option(
    "--pdfcpu-path",
    default="pdfcpu",
    help="Path to the pdfcpu binary (default: pdfcpu)",
)
@click.pass_context
def encrypt_command(
    ctx: click.Context,  # noqa: ARG001
    pdf_path: Path,
    output_path: Path | None,
    owner_password: str,
    user_password: str | None,
    mode: str,
    key_length: str,
    permissions: str,
    pdfcpu_path: str,
) -> None:
    """Encrypt a PDF file using pdfcpu.

    PDF_PATH is the path to the PDF file to encrypt.
    OUTPUT_PATH is the optional output path (modifies input if not provided).

    This command requires pdfcpu to be installed. The owner password is mandatory
    and grants full access to the document. The user password is optional but
    recommended - it will be required to open the document.

    Examples:
        pdf-forms encrypt doc.pdf -opw ownerpass
        pdf-forms encrypt doc.pdf encrypted.pdf -opw ownerpass -upw userpass
        pdf-forms encrypt doc.pdf -opw ownerpass --mode aes --key 256 --perm none
    """
    # Build pdfcpu encrypt command
    cmd = [
        pdfcpu_path,
        "encrypt",
        "-mode",
        mode.lower(),
        "-key",
        key_length,
        "-perm",
        permissions.lower(),
        "-opw",
        owner_password,
    ]

    # Add user password if provided
    if user_password:
        cmd.extend(["-upw", user_password])

    # Add input and output files
    cmd.append(str(pdf_path))
    if output_path:
        cmd.append(str(output_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        if output_path:
            click.echo(f"✓ PDF encrypted and saved to: {output_path}")
        else:
            click.echo(f"✓ PDF encrypted: {pdf_path}")

        # Print any warnings/info from pdfcpu
        if result.stderr:
            click.echo(result.stderr, err=True)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else "Failed to encrypt PDF"

        # pdfcpu binary not found
        if "command not found" in error_msg.lower() or "not recognized" in error_msg.lower():
            raise click.ClickException(
                f"pdfcpu not found at '{pdfcpu_path}'. "
                "Please install pdfcpu or provide the correct path with --pdfcpu-path"
            ) from e

        # PDF processing errors - malformed form fields
        if "required entry" in error_msg.lower() or "dict=" in error_msg.lower():
            raise click.ClickException(
                f"pdfcpu could not process this PDF: {error_msg}\n\n"
                "This error often occurs when:\n"
                "  1. The PDF has malformed form fields\n"
                "  2. The PDF is corrupted\n\n"
                "Try using the fill-form command first to normalize the PDF, "
                "or use a different PDF tool to fix the form fields."
            ) from e

        raise click.ClickException(f"Encryption failed: {error_msg}") from e
    except FileNotFoundError as e:
        raise click.ClickException(
            f"pdfcpu not found at '{pdfcpu_path}'. "
            "Please install pdfcpu or provide the correct path with --pdfcpu-path"
        ) from e
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
