"""Tests for the extract command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import PDFField, PDFFormData, PDFFormError, PDFFormNotFoundError


class TestExtractCommand:
    """Tests for the extract command."""

    def test_extract_to_stdout_unified(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command outputs unified format to stdout."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="Test Value",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={"header": {"version": "v1.0"}},
        )

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract", return_value=mock_form_data
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code == 0
            assert "TestField" in result.output
            assert "textfield" in result.output

    def test_extract_to_stdout_raw(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command outputs raw format with --raw flag."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_raw_data = {"header": {"version": "v1.0"}, "forms": []}
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data=mock_raw_data,
        )

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract", return_value=mock_form_data
        ):
            result = runner.invoke(main, ["extract", str(test_file), "--raw"])
            assert result.exit_code == 0
            assert "header" in result.output

    def test_extract_to_file_unified(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command writes unified format to output file."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.json"

        mock_field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="Test Value",
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract", return_value=mock_form_data
        ):
            result = runner.invoke(main, ["extract", str(test_file), "-o", str(output_file)])
            assert result.exit_code == 0
            assert "Unified form data extracted to" in result.output
            assert output_file.exists()

    def test_extract_to_file_raw(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command writes raw format with --raw flag."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.json"

        mock_raw_data = {"header": {"version": "v1.0"}, "forms": []}
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data=mock_raw_data,
        )

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract", return_value=mock_form_data
        ):
            result = runner.invoke(
                main, ["extract", str(test_file), "-o", str(output_file), "--raw"]
            )
            assert result.exit_code == 0
            assert "Raw form data extracted to" in result.output
            assert output_file.exists()

    def test_extract_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command handles missing form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract",
            side_effect=PDFFormNotFoundError("No form"),
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_extract_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command handles execution error."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.extract",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to extract" in result.output

    def test_extract_nonexistent_file(self, runner: CliRunner) -> None:
        """Test extract command with nonexistent file."""
        result = runner.invoke(main, ["extract", "/nonexistent/file.pdf"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "Invalid" in result.output
