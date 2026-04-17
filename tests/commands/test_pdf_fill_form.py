"""Tests for the fill-form command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from demo.fill_sample import generate_sample_value
from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import (
    FormValidationError,
    PDFFormError,
    PDFFormNotFoundError,
    PDFFormService,
)
from privacyforms_pdf.parser import parse_pdf

if TYPE_CHECKING:
    from click.testing import CliRunner


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDF = REPO_ROOT / "samples" / "FilledForm.pdf"


class TestFillFormCommand:
    """Tests for the fill-form command."""

    def test_fill_form_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command succeeds with valid data."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Candidate Name": "John Smith", "Full time": true}')
        output_file = tmp_path / "output.pdf"

        with (
            patch.object(PDFFormService, "has_form", return_value=True),
            patch.object(PDFFormService, "validate_form_data", return_value=[]),
            patch.object(PDFFormService, "fill_form") as mock_fill,
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

        with patch.object(PDFFormService, "validate_form_data", return_value=["Field not found"]):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0

    def test_fill_form_no_validate(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --no-validate flag."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')
        output_file = tmp_path / "output.pdf"

        with (
            patch.object(PDFFormService, "has_form", return_value=True),
            patch.object(PDFFormService, "fill_form") as mock_fill,
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
            assert "validation passed" not in result.output.lower()

    def test_fill_form_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command when PDF has no form."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        err_msg = "PDF does not contain a form"
        with (
            patch.object(PDFFormService, "has_form", return_value=False),
            patch.object(PDFFormService, "fill_form", side_effect=PDFFormNotFoundError(err_msg)),
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

        with (
            patch.object(PDFFormService, "has_form", return_value=True),
            patch.object(PDFFormService, "validate_form_data", return_value=[]),
            patch.object(PDFFormService, "fill_form") as mock_fill,
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

        with patch.object(
            PDFFormService,
            "validate_form_data",
            return_value=["Required field not provided: 'Missing'"],
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file), "--strict"])
            assert result.exit_code != 0
            assert "required" in result.output.lower() or "missing" in result.output.lower()

    def test_fill_form_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command handles PDFFormError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        with (
            patch.object(PDFFormService, "has_form", return_value=True),
            patch.object(PDFFormService, "fill_form", side_effect=PDFFormError("Error")),
        ):
            result = runner.invoke(
                main, ["fill-form", str(pdf_file), str(json_file), "--no-validate"]
            )
            assert result.exit_code != 0
            assert "Error" in result.output

    def test_fill_form_checkbox_validation_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command validation fails with checkbox type error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Agree": "not-a-boolean"}')

        with patch.object(
            PDFFormService,
            "validate_form_data",
            return_value=["Field 'Agree': checkbox value must be boolean, got str"],
        ):
            result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
            assert result.exit_code != 0
            assert "boolean" in result.stderr.lower() or "boolean" in result.output.lower()

    def test_fill_form_with_field_id_keys(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command supports field IDs through --field-keys=id."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"f-0": "John Smith"}')
        output_file = tmp_path / "output.pdf"

        with (
            patch.object(PDFFormService, "has_form", return_value=True),
            patch.object(PDFFormService, "validate_form_data", return_value=[]),
            patch.object(PDFFormService, "fill_form") as mock_fill,
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
                    "--field-keys",
                    "id",
                ],
            )
            assert result.exit_code == 0
            mock_fill.assert_called_once()
            assert mock_fill.call_args.kwargs["key_mode"] == "id"

    def test_fill_form_non_object_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form rejects non-object JSON payloads."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('["not", "an", "object"]')

        result = runner.invoke(main, ["fill-form", str(pdf_file), str(json_file)])
        assert result.exit_code != 0
        assert "top-level object" in result.output.lower()

    def test_fill_form_no_validate_no_form(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form handles PDFFormNotFoundError when validation is skipped."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')

        with patch.object(PDFFormService, "has_form", return_value=False):
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

        with patch.object(
            PDFFormService,
            "fill_form",
            side_effect=FormValidationError("validation failed", ["bad field"]),
        ):
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "--no-validate"],
            )
            assert result.exit_code != 0
            assert "validation failed" in result.output.lower()

    def test_fill_form_real_sample_with_id_keys(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form end to end with a real sample PDF and ID-keyed data."""
        representation = parse_pdf(SAMPLE_PDF)
        fill_data: dict[str, str | bool] = {}
        expected_by_name: dict[str, str | bool] = {}

        for field in representation.fields:
            if field.type not in {"textfield", "textarea", "datefield", "checkbox"}:
                continue
            value = generate_sample_value(field.type, field.name)
            fill_data[field.id] = value
            expected_by_name[field.name] = value
            if len(fill_data) == 3:
                break

        assert fill_data

        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps(fill_data), encoding="utf-8")
        output_file = tmp_path / "filled.pdf"

        result = runner.invoke(
            main,
            [
                "fill-form",
                str(SAMPLE_PDF),
                str(json_file),
                "-o",
                str(output_file),
                "--field-keys",
                "id",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        filled_representation = parse_pdf(output_file)
        for field_name, expected_value in expected_by_name.items():
            field = filled_representation.get_field_by_name(field_name)
            assert field is not None
            assert field.value == expected_value
