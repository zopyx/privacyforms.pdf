"""Tests for the get-value command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import PDFFormError, PDFFormNotFoundError


class TestGetValueCommand:
    """Tests for the get-value command."""

    def test_get_value_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command returns value."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.get_field_value", return_value="The Value"
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code == 0
            assert result.output.strip() == "The Value"

    def test_get_value_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles missing field."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.get_field_value", return_value=None
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Missing"])
            assert result.exit_code != 0
            assert "not found" in result.output

    def test_get_value_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.get_field_value",
            side_effect=PDFFormNotFoundError("No form"),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_get_value_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.get_field_value",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "Failed to get field value" in result.output
