"""Tests for the info command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import PDFFormError

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_has_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has form."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n")

        with patch("privacyforms_pdf.extractor.PDFFormService.has_form", return_value=True):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "contains a form" in result.output

    def test_info_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has no form."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n")

        with patch("privacyforms_pdf.extractor.PDFFormService.has_form", return_value=False):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "does not contain a form" in result.output

    def test_info_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n")

        with patch(
            "privacyforms_pdf.extractor.PDFFormService.has_form",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to get form info" in result.output

    def test_info_nonexistent_file(self, runner: CliRunner) -> None:
        """Test info command with nonexistent file."""
        result = runner.invoke(main, ["info", "/nonexistent/file.pdf"])
        assert result.exit_code != 0
