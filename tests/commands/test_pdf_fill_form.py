"""Tests for the fill-form command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import (
    FormValidationError,
    PDFFormData,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
    PDFField,
)

if TYPE_CHECKING:
    pass


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
            # Error message should contain the actual error from PDFFormError
            assert "Error" in result.output

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

    def test_fill_form_with_pdfcpu(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --pdfcpu option."""
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
            patch.object(PDFFormExtractor, "fill_form_with_pdfcpu") as mock_fill_pdfcpu,
        ):
            mock_fill_pdfcpu.return_value = output_file
            result = runner.invoke(
                main,
                [
                    "fill-form",
                    str(pdf_file),
                    str(json_file),
                    "-o",
                    str(output_file),
                    "--pdfcpu",
                ],
            )
            assert result.exit_code == 0
            assert "validation passed" in result.output.lower()
            assert "pdfcpu" in result.output.lower()
            assert "saved to" in result.output.lower()
            mock_fill_pdfcpu.assert_called_once()

    def test_fill_form_with_pdfcpu_custom_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command with --pdfcpu and --pdfcpu-path options."""
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
            patch.object(PDFFormExtractor, "fill_form_with_pdfcpu") as mock_fill_pdfcpu,
        ):
            mock_fill_pdfcpu.return_value = output_file
            result = runner.invoke(
                main,
                [
                    "fill-form",
                    str(pdf_file),
                    str(json_file),
                    "-o",
                    str(output_file),
                    "--pdfcpu",
                    "--pdfcpu-path",
                    "/custom/pdfcpu",
                ],
            )
            assert result.exit_code == 0
            mock_fill_pdfcpu.assert_called_once()
            # Check that custom path was passed
            call_kwargs = mock_fill_pdfcpu.call_args.kwargs
            assert call_kwargs.get("pdfcpu_path") == "/custom/pdfcpu"

    def test_fill_form_with_pdfcpu_fallback_message(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test fill-form command reports pypdf fallback when pdfcpu is incompatible."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "test"}')
        output_file = tmp_path / "output.pdf"

        def fallback_fill(
            self: PDFFormExtractor,
            *_args: object,
            **_kwargs: object,
        ) -> Path:
            self._last_fill_backend = "pypdf-fallback"
            return output_file

        with patch.object(PDFFormExtractor, "fill_form_with_pdfcpu", new=fallback_fill):
            result = runner.invoke(
                main,
                [
                    "fill-form",
                    str(pdf_file),
                    str(json_file),
                    "-o",
                    str(output_file),
                    "--pdfcpu",
                    "--no-validate",
                ],
            )

        assert result.exit_code == 0
        assert "pypdf fallback" in result.output.lower()

    def test_fill_form_pdfcpu_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test fill-form command handles pdfcpu not found error."""
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
                "fill_form_with_pdfcpu",
                side_effect=PDFFormError("pdfcpu binary not found"),
            ),
        ):
            result = runner.invoke(
                main,
                ["fill-form", str(pdf_file), str(json_file), "--pdfcpu", "--no-validate"],
            )
            assert result.exit_code != 0
            assert "pdfcpu binary not found" in result.output.lower()
