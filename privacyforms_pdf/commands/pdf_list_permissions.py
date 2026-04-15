"""List-permissions command for pdf-forms CLI using pdfcpu."""

from __future__ import annotations

from pathlib import Path

import click

from privacyforms_pdf.models import PDFFormError
from privacyforms_pdf.security import PDFSecurityManager, format_permissions_highlevel


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
    security = PDFSecurityManager(pdfcpu_path=pdfcpu_path)

    try:
        permissions = security.list_permissions(
            pdf_path,
            user_password=user_password,
            owner_password=owner_password,
        )

        if raw:
            result = security._run(
                [
                    security._resolve_pdfcpu(),
                    "permissions",
                    "list",
                    *(["-upw", user_password] if user_password else []),
                    *(["-opw", owner_password] if owner_password else []),
                    str(pdf_path),
                ]
            )
            click.echo(result.stdout)
            if result.stderr:
                click.echo(result.stderr, err=True)
        else:
            if not permissions["is_encrypted"]:
                click.echo("Document is not encrypted - all permissions granted")
                return

            formatted = format_permissions_highlevel(permissions)
            click.echo(formatted)

    except PDFFormError as e:
        error_msg = str(e).lower()

        if "pdfcpu binary not found" in error_msg:
            raise click.ClickException(
                f"pdfcpu not found at '{pdfcpu_path}'. "
                "Please install pdfcpu or provide the correct path with --pdfcpu-path"
            ) from e

        if "requires a password" in error_msg:
            raise click.ClickException(
                "This document requires a password. Please provide -upw (user password) "
                "or -opw (owner password)"
            ) from e

        if "required entry" in error_msg or "dict=" in error_msg:
            raise click.ClickException(
                f"pdfcpu could not process this PDF: {e}\n\n"
                "This error often occurs when:\n"
                "  1. The PDF is not encrypted (use 'pdf-forms info' to check)\n"
                "  2. The PDF has malformed form fields\n"
                "  3. The PDF is corrupted\n\n"
                "To check if the PDF is encrypted, run:\n"
                f"  pdf-forms info {pdf_path}"
            ) from None

        raise click.ClickException(f"Failed to list permissions: {e}") from None
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e


# Re-export helpers for existing tests
from privacyforms_pdf.security import parse_permission_bits  # noqa: E402

__all__ = ["list_permissions_command", "parse_permission_bits", "format_permissions_highlevel"]
