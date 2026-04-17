"""Centralized I/O safety utilities for file reads and writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def validate_pdf_path(pdf_path: Path) -> None:
    """Validate that *pdf_path* exists, is a regular file, and looks like a PDF.

    Args:
        pdf_path: Path to validate.

    Raises:
        ValueError: If the path is a symlink or not a PDF.
        FileNotFoundError: If the path does not exist or is not a file.
    """
    if pdf_path.is_symlink():
        raise ValueError(f"Symlinks are not allowed: {pdf_path}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Path is not a file: {pdf_path}")
    with pdf_path.open("rb") as f:
        header = f.read(4)
        if header != b"%PDF":
            raise ValueError(f"File does not appear to be a valid PDF: {pdf_path}")


def safe_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write *content* to *path*, refusing to write through symlinks.

    Args:
        path: Destination file path.
        content: Text content to write.
        encoding: Text encoding (default: utf-8).

    Raises:
        ValueError: If *path* is a symlink.
    """
    if path.is_symlink():
        raise ValueError(f"Refusing to write to symlink: {path}")
    path.write_text(content, encoding=encoding)
