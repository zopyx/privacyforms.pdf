"""Tests for security_io utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from privacyforms_pdf.security_io import safe_write_text, validate_pdf_path


class TestValidatePdfPath:
    """Tests for validate_pdf_path."""

    def test_valid_pdf(self, tmp_path: Path) -> None:
        """A valid PDF file passes validation."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        validate_pdf_path(pdf)

    def test_missing_file(self, tmp_path: Path) -> None:
        """A missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            validate_pdf_path(tmp_path / "missing.pdf")

    def test_directory(self, tmp_path: Path) -> None:
        """A directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Path is not a file"):
            validate_pdf_path(tmp_path)

    def test_symlink_rejected(self, tmp_path: Path) -> None:
        """A symlink raises ValueError."""
        real = tmp_path / "real.pdf"
        real.write_bytes(b"%PDF-1.4\n")
        link = tmp_path / "link.pdf"
        link.symlink_to(real)
        with pytest.raises(ValueError, match="Symlinks are not allowed"):
            validate_pdf_path(link)

    def test_invalid_magic_rejected(self, tmp_path: Path) -> None:
        """A file without %PDF header raises ValueError."""
        txt = tmp_path / "not_a_pdf.pdf"
        txt.write_text("Hello world", encoding="utf-8")
        with pytest.raises(ValueError, match="does not appear to be a valid PDF"):
            validate_pdf_path(txt)

    def test_empty_file_rejected(self, tmp_path: Path) -> None:
        """An empty file raises ValueError."""
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="does not appear to be a valid PDF"):
            validate_pdf_path(empty)


class TestSafeWriteText:
    """Tests for safe_write_text."""

    def test_writes_regular_file(self, tmp_path: Path) -> None:
        """Writing to a regular file succeeds."""
        f = tmp_path / "out.txt"
        safe_write_text(f, "hello")
        assert f.read_text(encoding="utf-8") == "hello"

    def test_rejects_symlink(self, tmp_path: Path) -> None:
        """Writing through a symlink raises ValueError."""
        real = tmp_path / "real.txt"
        real.write_text("secret", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        with pytest.raises(ValueError, match="Refusing to write to symlink"):
            safe_write_text(link, "attacker")
        assert real.read_text(encoding="utf-8") == "secret"

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Custom encoding is respected."""
        f = tmp_path / "out.txt"
        safe_write_text(f, "hello", encoding="utf-8")
        assert f.read_text(encoding="utf-8") == "hello"
