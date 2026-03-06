"""Tests for the PDFFormExtractor class."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from privacyforms_pdf.extractor import (
    FormField,
    PDFCPUError,
    PDFCPUExecutionError,
    PDFCPUNotFoundError,
    PDFFormData,
    PDFFormExtractor,
    PDFFormNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestPDFFormExtractorInitialization:
    """Tests for PDFFormExtractor initialization."""

    def test_init_with_pdfcpu_in_path(self) -> None:
        """Test initialization when pdfcpu is found in PATH."""
        with patch("privacyforms_pdf.extractor.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pdfcpu"
            extractor = PDFFormExtractor()
            assert extractor._pdfcpu_path == "/usr/bin/pdfcpu"

    def test_init_with_custom_path(self) -> None:
        """Test initialization with custom pdfcpu path."""
        extractor = PDFFormExtractor(pdfcpu_path="/custom/path/pdfcpu")
        assert extractor._pdfcpu_path == "/custom/path/pdfcpu"

    def test_init_pdfcpu_not_found(self) -> None:
        """Test initialization raises error when pdfcpu is not found."""
        with patch("privacyforms_pdf.extractor.shutil.which") as mock_which:
            mock_which.return_value = None
            with pytest.raises(PDFCPUNotFoundError):
                PDFFormExtractor()

    def test_find_pdfcpu_returns_none(self) -> None:
        """Test _find_pdfcpu returns None when pdfcpu not in PATH."""
        with patch("privacyforms_pdf.extractor.shutil.which") as mock_which:
            mock_which.return_value = None
            result = PDFFormExtractor._find_pdfcpu()
            assert result is None


class TestCheckPDFCPU:
    """Tests for check_pdfcpu method."""

    def test_check_pdfcpu_success(self) -> None:
        """Test check_pdfcpu returns True when pdfcpu works."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "pdfcpu v0.11.1"

            with patch.object(extractor, "_run_command", return_value=mock_result):
                assert extractor.check_pdfcpu() is True

    def test_check_pdfcpu_failure(self) -> None:
        """Test check_pdfcpu returns False when pdfcpu fails."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()

            with patch.object(extractor, "_run_command", side_effect=PDFCPUError("pdfcpu error")):
                assert extractor.check_pdfcpu() is False


class TestGetPDFCPUVersion:
    """Tests for get_pdfcpu_version method."""

    def test_get_version_success(self) -> None:
        """Test get_pdfcpu_version returns version string."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            mock_result = MagicMock()
            mock_result.stdout = "pdfcpu v0.11.1 dev\n"

            with patch.object(extractor, "_run_command", return_value=mock_result):
                version = extractor.get_pdfcpu_version()
                assert version == "pdfcpu v0.11.1 dev"


class TestValidatePDFPath:
    """Tests for _validate_pdf_path method."""

    def test_validate_existing_file(self, tmp_path: Path) -> None:
        """Test validation passes for existing file."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()
            # Should not raise
            extractor._validate_pdf_path(test_file)

    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """Test validation raises for nonexistent file."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            with pytest.raises(FileNotFoundError):
                extractor._validate_pdf_path(tmp_path / "nonexistent.pdf")

    def test_validate_directory(self, tmp_path: Path) -> None:
        """Test validation raises for directory."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            with pytest.raises(FileNotFoundError):
                extractor._validate_pdf_path(tmp_path)


class TestHasForm:
    """Tests for has_form method."""

    def test_has_form_true(self, tmp_path: Path) -> None:
        """Test has_form returns True when PDF has form."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Form: Yes\nOther info"

            with patch.object(extractor, "_run_command", return_value=mock_result):
                assert extractor.has_form(test_file) is True

    def test_has_form_false(self, tmp_path: Path) -> None:
        """Test has_form returns False when PDF has no form."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Form: No\nOther info"

            with patch.object(extractor, "_run_command", return_value=mock_result):
                assert extractor.has_form(test_file) is False

    def test_has_form_execution_error(self, tmp_path: Path) -> None:
        """Test has_form raises on execution error."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error"

            with (
                patch.object(extractor, "_run_command", return_value=mock_result),
                pytest.raises(PDFCPUExecutionError),
            ):
                extractor.has_form(test_file)


class TestParseFormData:
    """Tests for _parse_form_data method."""

    def test_parse_empty_forms(self, tmp_path: Path) -> None:
        """Test parsing with empty forms list."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"

            raw_data = {"header": {"version": "pdfcpu v1.0"}, "forms": []}

            result = extractor._parse_form_data(test_file, raw_data)

            assert isinstance(result, PDFFormData)
            assert result.source == test_file
            assert result.pdf_version == "pdfcpu v1.0"
            assert result.has_form is False
            assert result.fields == []

    def test_parse_textfield(self, tmp_path: Path) -> None:
        """Test parsing textfield data."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"

            raw_data = {
                "header": {"version": "pdfcpu v1.0"},
                "forms": [
                    {
                        "textfield": [
                            {
                                "pages": [1],
                                "id": "5",
                                "name": "Test Field",
                                "value": "Test Value",
                                "locked": False,
                            }
                        ]
                    }
                ],
            }

            result = extractor._parse_form_data(test_file, raw_data)

            assert len(result.fields) == 1
            field = result.fields[0]
            assert field.field_type == "textfield"
            assert field.id == "5"
            assert field.name == "Test Field"
            assert field.value == "Test Value"
            assert field.locked is False
            assert field.pages == [1]

    def test_parse_checkbox(self, tmp_path: Path) -> None:
        """Test parsing checkbox data."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"

            raw_data = {
                "header": {"version": "pdfcpu v1.0"},
                "forms": [
                    {
                        "checkbox": [
                            {
                                "pages": [1, 2],
                                "id": "10",
                                "name": "Agree",
                                "value": True,
                                "locked": True,
                            }
                        ]
                    }
                ],
            }

            result = extractor._parse_form_data(test_file, raw_data)

            assert len(result.fields) == 1
            field = result.fields[0]
            assert field.field_type == "checkbox"
            assert field.value is True
            assert field.locked is True
            assert field.pages == [1, 2]

    def test_parse_all_field_types(self, tmp_path: Path) -> None:
        """Test parsing all supported field types."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"

            raw_data = {
                "header": {"version": "pdfcpu v1.0"},
                "forms": [
                    {
                        "textfield": [{"pages": [1], "id": "1", "name": "Text", "value": "v"}],
                        "datefield": [{"pages": [1], "id": "2", "name": "Date", "value": "v"}],
                        "checkbox": [{"pages": [1], "id": "3", "name": "Check", "value": True}],
                        "radiobuttongroup": [
                            {"pages": [1], "id": "4", "name": "Radio", "value": "v"}
                        ],
                        "combobox": [{"pages": [1], "id": "5", "name": "Combo", "value": "v"}],
                        "listbox": [{"pages": [1], "id": "6", "name": "List", "value": "v"}],
                    }
                ],
            }

            result = extractor._parse_form_data(test_file, raw_data)

            assert len(result.fields) == 6
            field_types = [f.field_type for f in result.fields]
            assert "textfield" in field_types
            assert "datefield" in field_types
            assert "checkbox" in field_types
            assert "radiobuttongroup" in field_types
            assert "combobox" in field_types
            assert "listbox" in field_types


class TestExtract:
    """Tests for extract method."""

    def test_extract_no_form(self, tmp_path: Path) -> None:
        """Test extract raises when PDF has no form."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            with (
                patch.object(extractor, "has_form", return_value=False),
                pytest.raises(PDFFormNotFoundError),
            ):
                extractor.extract(test_file)

    def test_extract_file_not_found(self, tmp_path: Path) -> None:
        """Test extract raises when file doesn't exist."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            with pytest.raises(FileNotFoundError):
                extractor.extract(tmp_path / "nonexistent.pdf")

    def test_extract_success(self, tmp_path: Path) -> None:
        """Test extract returns PDFFormData on success."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_data = {
                "header": {"version": "pdfcpu v1.0"},
                "forms": [{"textfield": []}],
            }

            mock_result = MagicMock()
            mock_result.returncode = 0

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("privacyforms_pdf.extractor.json.load", return_value=mock_data),
                patch("pathlib.Path.unlink"),
            ):
                result = extractor.extract(test_file)
                assert isinstance(result, PDFFormData)


class TestListFields:
    """Tests for list_fields method."""

    def test_list_fields_returns_list(self, tmp_path: Path) -> None:
        """Test list_fields returns list of FormField."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[
                    FormField(
                        field_type="textfield",
                        pages=[1],
                        id="1",
                        name="Field1",
                        value="Value1",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                fields = extractor.list_fields(test_file)
                assert len(fields) == 1
                assert fields[0].name == "Field1"


class TestGetFieldValue:
    """Tests for get_field_value method."""

    def test_get_existing_field(self, tmp_path: Path) -> None:
        """Test get_field_value returns value for existing field."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[
                    FormField(
                        field_type="textfield",
                        pages=[1],
                        id="1",
                        name="Target",
                        value="Found",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                value = extractor.get_field_value(test_file, "Target")
                assert value == "Found"

    def test_get_nonexistent_field(self, tmp_path: Path) -> None:
        """Test get_field_value returns None for nonexistent field."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                value = extractor.get_field_value(test_file, "Nonexistent")
                assert value is None


class TestRunCommand:
    """Tests for _run_command method."""

    def test_run_command_success(self) -> None:
        """Test _run_command returns result on success."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                result = extractor._run_command(["version"])
                assert result.returncode == 0

    def test_run_command_failure_with_check(self) -> None:
        """Test _run_command raises on failure with check=True."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error message"

            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(PDFCPUExecutionError) as exc_info:
                    extractor._run_command(["badcommand"])
                assert exc_info.value.returncode == 1
                assert exc_info.value.stderr == "Error message"

    def test_run_command_failure_without_check(self) -> None:
        """Test _run_command returns result on failure with check=False."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()

            mock_result = MagicMock()
            mock_result.returncode = 1

            with patch("subprocess.run", return_value=mock_result):
                result = extractor._run_command(["badcommand"], check=False)
                assert result.returncode == 1

    def test_run_command_file_not_found(self) -> None:
        """Test _run_command raises PDFCPUNotFoundError on FileNotFoundError."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()

            with (
                patch("subprocess.run", side_effect=FileNotFoundError()),
                pytest.raises(PDFCPUNotFoundError),
            ):
                extractor._run_command(["version"])


class TestExtractToJSON:
    """Tests for extract_to_json method."""

    def test_extract_to_json_success(self, tmp_path: Path) -> None:
        """Test extract_to_json succeeds."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()
            output_file = tmp_path / "output.json"

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch.object(extractor, "_run_command", return_value=mock_result):
                extractor.extract_to_json(test_file, output_file)
                # Should complete without error

    def test_extract_to_json_failure(self, tmp_path: Path) -> None:
        """Test extract_to_json raises on failure."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()
            output_file = tmp_path / "output.json"

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Export failed"

            with (
                patch.object(extractor, "_run_command", return_value=mock_result),
                pytest.raises(PDFCPUExecutionError),
            ):
                extractor.extract_to_json(test_file, output_file)
