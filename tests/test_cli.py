"""Tests for the CLI module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from privacyforms_pdf.cli import create_extractor, main
from privacyforms_pdf.extractor import (
    FormField,
    PDFCPUExecutionError,
    PDFFormData,
    PDFFormExtractor,
    PDFFormNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click test runner."""
    return CliRunner()


class TestMainCommand:
    """Tests for the main CLI group."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Test main command shows help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PDF Form extraction" in result.output

    def test_main_version(self, runner: CliRunner) -> None:
        """Test main command shows version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_success(self, runner: CliRunner) -> None:
        """Test check command when pdfcpu is installed."""
        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "get_pdfcpu_version", return_value="v0.11.1"),
        ):
            result = runner.invoke(main, ["check"])
            assert result.exit_code == 0
            assert "pdfcpu is installed" in result.output

    def test_check_failure(self, runner: CliRunner) -> None:
        """Test check command when pdfcpu is not installed."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value=None):
            result = runner.invoke(main, ["check"])
            assert result.exit_code == 1
            assert "pdfcpu not found" in result.output


class TestExtractCommand:
    """Tests for the extract command."""

    def test_extract_to_stdout(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command outputs to stdout."""
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

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code == 0
            assert "header" in result.output

    def test_extract_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command writes to output file."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.json"

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "extract_to_json") as mock_extract,
        ):
            result = runner.invoke(main, ["extract", str(test_file), "-o", str(output_file)])
            assert result.exit_code == 0
            assert "Form data extracted to" in result.output
            mock_extract.assert_called_once_with(test_file, output_file)

    def test_extract_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command handles missing form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "extract", side_effect=PDFFormNotFoundError("No form")),
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_extract_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command handles execution error."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "extract",
                side_effect=PDFCPUExecutionError("Error", 1, "stderr msg"),
            ),
        ):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to extract" in result.output


class TestListFieldsCommand:
    """Tests for the list-fields command."""

    def test_list_fields_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command shows fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_fields = [
            FormField(
                field_type="textfield",
                pages=[1],
                id="1",
                name="Field Name",
                value="Field Value",
                locked=False,
            )
        ]

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "textfield" in result.output
            assert "Field Name" in result.output
            assert "Field Value" in result.output
            assert "Total fields: 1" in result.output

    def test_list_fields_empty(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command with no fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "list_fields", return_value=[]),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "No form fields found" in result.output

    def test_list_fields_long_value_truncated(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command truncates long values."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_fields = [
            FormField(
                field_type="textfield",
                pages=[1],
                id="1",
                name="Long",
                value="A" * 100,
                locked=False,
            )
        ]

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "..." in result.output


class TestGetValueCommand:
    """Tests for the get-value command."""

    def test_get_value_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command returns value."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "get_field_value", return_value="The Value"),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code == 0
            assert result.output.strip() == "The Value"

    def test_get_value_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles missing field."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "get_field_value", return_value=None),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Missing"])
            assert result.exit_code != 0
            assert "not found" in result.output


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_has_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=True),
        ):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "contains a form" in result.output

    def test_info_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has no form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=False),
        ):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "does not contain a form" in result.output


class TestCreateExtractor:
    """Tests for create_extractor helper."""

    def test_create_extractor_success(self) -> None:
        """Test create_extractor succeeds when pdfcpu is found."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = create_extractor()
            assert isinstance(extractor, PDFFormExtractor)

    def test_create_extractor_failure(self) -> None:
        """Test create_extractor raises ClickException when pdfcpu not found."""
        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value=None),
            pytest.raises(click.ClickException),
        ):
            create_extractor()


class TestCLIEdgeCases:
    """Tests for CLI edge cases."""

    def test_extract_nonexistent_file(self, runner: CliRunner) -> None:
        """Test extract command with nonexistent file."""
        result = runner.invoke(main, ["extract", "/nonexistent/file.pdf"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "Invalid" in result.output

    def test_list_fields_nonexistent_file(self, runner: CliRunner) -> None:
        """Test list-fields command with nonexistent file."""
        result = runner.invoke(main, ["list-fields", "/nonexistent/file.pdf"])
        assert result.exit_code != 0

    def test_list_fields_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "list_fields",
                side_effect=PDFFormNotFoundError("No form"),
            ),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_list_fields_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFCPUExecutionError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "list_fields",
                side_effect=PDFCPUExecutionError("Error", 1, "pdfcpu failed"),
            ),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to list fields" in result.output
            assert "pdfcpu failed" in result.output

    def test_get_value_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "get_field_value",
                side_effect=PDFFormNotFoundError("No form"),
            ),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_get_value_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFCPUExecutionError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "get_field_value",
                side_effect=PDFCPUExecutionError("Error", 1, "pdfcpu failed"),
            ),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "Failed to get value" in result.output

    def test_info_nonexistent_file(self, runner: CliRunner) -> None:
        """Test info command with nonexistent file."""
        result = runner.invoke(main, ["info", "/nonexistent/file.pdf"])
        assert result.exit_code != 0

    def test_info_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command handles PDFCPUExecutionError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(
                PDFFormExtractor,
                "has_form",
                side_effect=PDFCPUExecutionError("Error", 1, "pdfcpu error"),
            ),
        ):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to get info" in result.output


class TestFillFormCommand:
    """Tests for the fill-form command."""

    def test_fill_form_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command succeeds with valid data."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": []}')
        output_file = tmp_path / "output.pdf"

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(PDFFormExtractor, "_run_command") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "-o", str(output_file)],
            )
            assert result.exit_code == 0
            assert "validation passed" in result.output.lower()
            assert "saved to" in result.output.lower()

    def test_fill_form_validation_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command fails on validation error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text(
            '{"forms": [{"textfield": [{"id": "999", "name": "Bad", "value": "x"}]}]}'
        )

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "validation" in result.output.lower() or "validation" in result.stderr.lower()

    def test_fill_form_no_validate(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --no-validate flag."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": [{"textfield": [{"id": "1", "value": "test"}]}]}')
        output_file = tmp_path / "output.pdf"

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "_run_command") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(
                main,
                [
                    "fill-form",
                    str(pdf_file),
                    str(json_file),
                    "-o",
                    str(output_file),
                    "--no-validate",
                ],
            )
            assert result.exit_code == 0
            # Should not show validation message
            assert "validation passed" not in result.output.lower()

    def test_fill_form_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command when PDF has no form."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{}')

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=False),
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "does not contain a form" in result.output.lower()

    def test_fill_form_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with invalid JSON."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text("not valid json")

        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "invalid json" in result.output.lower()

    def test_fill_form_in_place(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command without output path (modifies in place)."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": []}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(PDFFormExtractor, "_run_command") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code == 0
            assert str(pdf_file) in result.output

    def test_fill_form_strict_mode(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --strict flag."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": []}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                FormField(
                    field_type="textfield",
                    pages=[1],
                    id="1",
                    name="Required",
                    value="",
                    locked=False,
                )
            ],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file), "--strict"])
            assert result.exit_code != 0
            assert "required" in result.output.lower() or "missing" in result.output.lower()

    def test_fill_form_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command handles PDFCPUExecutionError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": []}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(
                PDFFormExtractor,
                "_run_command",
                side_effect=PDFCPUExecutionError("Error", 1, "fill failed"),
            ),
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "Failed to fill form" in result.output

    def test_fill_form_no_validate_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form handles PDFFormNotFoundError when validation is skipped."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"forms": []}')

        with (
            patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(PDFFormExtractor, "has_form", return_value=False),
        ):
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "--no-validate"],
            )
            assert result.exit_code != 0
            assert "does not contain a form" in result.output.lower()
