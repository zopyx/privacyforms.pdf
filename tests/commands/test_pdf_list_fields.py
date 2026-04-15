"""Tests for the list-fields command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from privacyforms_pdf.cli import main
from privacyforms_pdf.extractor import FieldGeometry, PDFField, PDFFormError, PDFFormNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


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

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
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

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
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

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--no-geometry"])
            assert result.exit_code == 0
            # Should still show fields but without geometry columns
            assert "Field1" in result.output

    def test_list_fields_empty(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command with no fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch("privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=[]):
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

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code == 0
            # Rich uses ellipsis character (…) for truncation, not "..."
            assert "…" in result.output or "AAA" in result.output

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

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--no-geometry"])
            assert result.exit_code == 0
            # With Rich Table, long values may be truncated, so check components separately
            assert "radiobuttongroup" in result.output
            assert "Choice" in result.output
            assert "Option1" in result.output

    def test_list_fields_shows_listbox_options(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command shows options for listbox fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_fields = [
            PDFField(
                name="Languages",
                id="1",
                type="listbox",
                value="German",
                options=["English", "German", "French"],
            )
        ]

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--no-geometry"])
            assert result.exit_code == 0
            # With Rich Table, long values may be truncated, so check components separately
            assert "listbox" in result.output
            assert "Languages" in result.output
            assert "German" in result.output

    def test_list_fields_no_form_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFFormNotFoundError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields",
            side_effect=PDFFormNotFoundError("No form"),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "No form" in result.output

    def test_list_fields_execution_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command handles PDFFormError."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields",
            side_effect=PDFFormError("Error"),
        ):
            result = runner.invoke(main, ["list-fields", str(test_file)])
            assert result.exit_code != 0
            assert "Failed to list fields" in result.output

    def test_list_fields_nonexistent_file(self, runner: CliRunner) -> None:
        """Test list-fields command with nonexistent file."""
        result = runner.invoke(main, ["list-fields", "/nonexistent/file.pdf"])
        assert result.exit_code != 0

    def test_list_fields_layout(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields command with --layout flag."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        geometry1 = FieldGeometry(page=1, rect=(100.0, 500.0, 200.0, 530.0))
        geometry2 = FieldGeometry(page=1, rect=(300.0, 500.0, 400.0, 530.0))
        geometry3 = FieldGeometry(page=1, rect=(100.0, 200.0, 200.0, 230.0))

        mock_fields = [
            PDFField(
                name="First Name",
                id="1",
                type="textfield",
                value="John",
                pages=[1],
                geometry=geometry1,
            ),
            PDFField(
                name="Last Name",
                id="2",
                type="textfield",
                value="Doe",
                pages=[1],
                geometry=geometry2,
            ),
            PDFField(
                name="Email",
                id="3",
                type="textfield",
                value="",
                pages=[1],
                geometry=geometry3,
            ),
        ]

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--layout"])
            assert result.exit_code == 0
            assert "Form Layout" in result.output
            assert "Page 1" in result.output
            assert "First Name" in result.output
            assert "Last Name" in result.output
            assert "Email" in result.output
            assert "Total fields: 3" in result.output

    def test_list_fields_layout_empty(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields --layout with no fields."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch("privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=[]):
            result = runner.invoke(main, ["list-fields", str(test_file), "--layout"])
            assert result.exit_code == 0
            assert "No form fields found" in result.output

    def test_list_fields_layout_multi_page(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields --layout with fields on multiple pages."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        geometry1 = FieldGeometry(page=1, rect=(100.0, 500.0, 200.0, 530.0))
        geometry2 = FieldGeometry(page=2, rect=(100.0, 500.0, 200.0, 530.0))

        mock_fields = [
            PDFField(
                name="Page1Field",
                id="1",
                type="textfield",
                value="",
                pages=[1],
                geometry=geometry1,
            ),
            PDFField(
                name="Page2Field",
                id="2",
                type="textfield",
                value="",
                pages=[2],
                geometry=geometry2,
            ),
        ]

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--layout"])
            assert result.exit_code == 0
            assert "Page 1" in result.output
            assert "Page 2" in result.output
            assert "Page1Field" in result.output
            assert "Page2Field" in result.output

    def test_list_fields_layout_checkbox(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test list-fields --layout shows checkbox values correctly."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        geometry = FieldGeometry(page=1, rect=(100.0, 500.0, 120.0, 520.0))
        mock_fields = [
            PDFField(
                name="Agree",
                id="1",
                type="checkbox",
                value=True,
                pages=[1],
                geometry=geometry,
            ),
        ]

        with patch(
            "privacyforms_pdf.extractor.PDFFormExtractor.list_fields", return_value=mock_fields
        ):
            result = runner.invoke(main, ["list-fields", str(test_file), "--layout"])
            assert result.exit_code == 0
            assert "Agree" in result.output
            assert "checkbox" in result.output
