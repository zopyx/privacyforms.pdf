"""Tests for the CLI module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from click.testing import CliRunner

from privacyforms_pdf.cli import create_extractor, main
from privacyforms_pdf.extractor import (
    FieldGeometry,
    FormValidationError,
    PDFField,
    PDFFormData,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
)


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
        assert "0.1.3" in result.output


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_success(self, runner: CliRunner) -> None:
        """Test check command when pypdf is available."""
        result = runner.invoke(main, ["check"])
        assert result.exit_code == 0
        assert "ready" in result.output.lower() or "pypdf" in result.output.lower()


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

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
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

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
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

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
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

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
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

        with patch.object(PDFFormExtractor, "extract", side_effect=PDFFormNotFoundError("No form")):
            result = runner.invoke(main, ["extract", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_extract_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test extract command handles execution error."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor,
            "extract",
            side_effect=PDFFormError("Error"),
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
            PDFField(
                name="Field Name",
                id="1",
                type="textfield",
                value="Field Value",
                pages=[1],
                locked=False,
            )
        ]

        with patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "textfield" in result.output
            assert "Field Name" in result.output
            assert "Field Value" in result.output
            assert "Total fields: 1" in result.output

    def test_list_fields_with_geometry(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command shows geometry information."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        geometry = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        mock_fields = [
            PDFField(
                name="Field1",
                id="1",
                type="textfield",
                value="Value",
                pages=[1],
                geometry=geometry,
            )
        ]

        with patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "Position" in result.output or "100" in result.output
            assert "Size" in result.output or "200" in result.output

    def test_list_fields_no_geometry(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command with --no-geometry flag."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        geometry = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        mock_fields = [
            PDFField(
                name="Field1",
                id="1",
                type="textfield",
                value="Value",
                geometry=geometry,
            )
        ]

        with patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields):
            result = runner.invoke(main, ["list-fields", str(test_file), "--no-geometry"])
            assert result.exit_code == 0
            # Should still show fields but without geometry columns
            assert "Field1" in result.output

    def test_list_fields_empty(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command with no fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(PDFFormExtractor, "list_fields", return_value=[]):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "No form fields found" in result.output

    def test_list_fields_long_value_truncated(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command truncates long values."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_fields = [
            PDFField(
                name="Long",
                id="1",
                type="textfield",
                value="A" * 100,
                pages=[1],
                locked=False,
            )
        ]

        with patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            assert "..." in result.output

    def test_list_fields_shows_radio_options(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command shows options for radio button groups."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_fields = [
            PDFField(
                name="Choice",
                id="1",
                type="radiobuttongroup",
                value="Option1",
                options=["Option1", "Option2", "Option3"],
            )
        ]

        with patch.object(PDFFormExtractor, "list_fields", return_value=mock_fields):
            result = runner.invoke(main, ["list-fields", str(test_file), "--no-geometry"])
            assert result.exit_code == 0
            assert "Option1 [options: Option1, Option2, Option3]" in result.output

    def test_list_fields_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor, "list_fields", side_effect=PDFFormNotFoundError("No form")
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_list_fields_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor,
            "list_fields",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to list fields" in result.output


class TestGetValueCommand:
    """Tests for the get-value command."""

    def test_get_value_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command returns value."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(PDFFormExtractor, "get_field_value", return_value="The Value"):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code == 0
            assert result.output.strip() == "The Value"

    def test_get_value_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles missing field."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(PDFFormExtractor, "get_field_value", return_value=None):
            result = runner.invoke(main, ["get-value", str(test_file), "Missing"])
            assert result.exit_code != 0
            assert "not found" in result.output

    def test_get_value_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor, "get_field_value", side_effect=PDFFormNotFoundError("No form")
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_get_value_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test get-value command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor,
            "get_field_value",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["get-value", str(test_file), "Field"])
            assert result.exit_code != 0
            assert "Failed to get field value" in result.output


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_has_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(PDFFormExtractor, "has_form", return_value=True):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "contains a form" in result.output

    def test_info_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command when PDF has no form."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(PDFFormExtractor, "has_form", return_value=False):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code == 0
            assert "does not contain a form" in result.output

    def test_info_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch.object(
            PDFFormExtractor,
            "has_form",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["info", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to get form info" in result.output


class TestCreateExtractor:
    """Tests for create_extractor helper."""

    def test_create_extractor_success(self) -> None:
        """Test create_extractor succeeds."""
        extractor = create_extractor()
        assert isinstance(extractor, PDFFormExtractor)

    def test_create_extractor_with_geometry(self) -> None:
        """Test create_extractor with geometry option."""
        extractor = create_extractor(extract_geometry=False)
        assert isinstance(extractor, PDFFormExtractor)
        assert extractor._extract_geometry is False


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

    def test_info_nonexistent_file(self, runner: CliRunner) -> None:
        """Test info command with nonexistent file."""
        result = runner.invoke(main, ["info", "/nonexistent/file.pdf"])
        assert result.exit_code != 0


class TestFillFormCommand:
    """Tests for the fill-form command."""

    def test_fill_form_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command succeeds with valid data."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Candidate Name": "John Smith", "Full time": true}')
        output_file = tmp_path / "output.pdf"

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Candidate Name",
                    id="1",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                ),
                PDFField(
                    name="Full time",
                    id="2",
                    type="checkbox",
                    value=False,
                    pages=[1],
                    locked=False,
                ),
            ],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(PDFFormExtractor, "fill_form") as mock_fill,
        ):
            mock_fill.return_value = output_file
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
        json_file.write_text('{"Unknown": "value"}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[],
            raw_data={},
        )

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0

    def test_fill_form_no_validate(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --no-validate flag."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')
        output_file = tmp_path / "output.pdf"

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Name",
                    id="1",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                )
            ],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(PDFFormExtractor, "fill_form") as mock_fill,
        ):
            mock_fill.return_value = output_file
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
        json_file.write_text('{"Name": "test"}')

        err_msg = "PDF does not contain a form"
        with (
            patch.object(PDFFormExtractor, "has_form", return_value=False),
            patch.object(PDFFormExtractor, "fill_form", side_effect=PDFFormNotFoundError(err_msg)),
        ):
            result = runner.invoke(
                main, ["fill-form", str(pdf_file), str(json_file), "--no-validate"]
            )
            assert result.exit_code != 0
            assert "does not contain a form" in result.output.lower()

    def test_fill_form_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with invalid JSON."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text("not valid json")

        result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
        assert result.exit_code != 0
        assert "invalid json" in result.output.lower()

    def test_fill_form_in_place(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command without output path (modifies in place)."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Name",
                    id="1",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                )
            ],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(PDFFormExtractor, "fill_form") as mock_fill,
        ):
            mock_fill.return_value = pdf_file
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code == 0
            assert str(pdf_file) in result.output

    def test_fill_form_strict_mode(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --strict flag."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "John"}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Name",
                    id="1",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                ),
                PDFField(
                    name="Missing",
                    id="2",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                ),
            ],
            raw_data={},
        )

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file), "--strict"])
            assert result.exit_code != 0
            assert "required" in result.output.lower() or "missing" in result.output.lower()

    def test_fill_form_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command handles PDFFormError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Name",
                    id="1",
                    type="textfield",
                    value="",
                    pages=[1],
                    locked=False,
                )
            ],
            raw_data={},
        )

        with (
            patch.object(PDFFormExtractor, "has_form", return_value=True),
            patch.object(PDFFormExtractor, "extract", return_value=mock_form_data),
            patch.object(
                PDFFormExtractor,
                "fill_form",
                side_effect=PDFFormError("Error"),
            ),
        ):
            result = runner.invoke(
                main, ["fill-form", str(pdf_file), str(json_file), "--no-validate"]
            )
            assert result.exit_code != 0
            assert "Failed to fill form" in result.output

    def test_fill_form_checkbox_validation_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command validation fails with checkbox type error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Agree": "not-a-boolean"}')

        mock_form_data = PDFFormData(
            source=pdf_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[
                PDFField(
                    name="Agree",
                    id="1",
                    type="checkbox",
                    value=False,
                    pages=[1],
                    locked=False,
                )
            ],
            raw_data={},
        )

        with patch.object(PDFFormExtractor, "extract", return_value=mock_form_data):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "boolean" in result.stderr.lower() or "boolean" in result.output.lower()

    def test_fill_form_no_validate_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form handles PDFFormNotFoundError when validation is skipped."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        with patch.object(PDFFormExtractor, "has_form", return_value=False):
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "--no-validate"],
            )
            assert result.exit_code != 0
            assert "does not contain a form" in result.output.lower()

    def test_fill_form_form_validation_error_passthrough(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test fill-form command handles FormValidationError from extractor."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        with (
            patch.object(
                PDFFormExtractor,
                "fill_form",
                side_effect=FormValidationError("validation failed", ["bad field"]),
            ),
        ):
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "--no-validate"],
            )
            assert result.exit_code != 0
            assert "validation failed" in result.output.lower()
