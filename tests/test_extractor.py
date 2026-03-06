"""Tests for the PDFFormExtractor class."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from privacyforms_pdf.extractor import (
    FormField,
    FormValidationError,
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

            def mock_run(args: list[str], check: bool = True) -> MagicMock:  # noqa: ARG001
                # Simulate pdfcpu export creating the JSON output file.
                output_path = args[-1]
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("{}")
                return mock_result

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "_run_command", side_effect=mock_run),
                patch("privacyforms_pdf.extractor.json.load", return_value=mock_data),
            ):
                result = extractor.extract(test_file)
                assert isinstance(result, PDFFormData)

    def test_extract_export_failure(self, tmp_path: Path) -> None:
        """Test extract raises PDFCPUExecutionError when export fails."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Export command failed"

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("pathlib.Path.unlink"),
                pytest.raises(PDFCPUExecutionError) as exc_info,
            ):
                extractor.extract(test_file)

            assert "Export command failed" in exc_info.value.stderr


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

    def test_get_field_value_no_match(self, tmp_path: Path) -> None:
        """Test get_field_value returns None when fields exist but don't match."""
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
                        name="OtherField",
                        value="Other",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                value = extractor.get_field_value(test_file, "Target")
                assert value is None


class TestGetFieldById:
    """Tests for get_field_by_id method."""

    def test_get_field_by_id_success(self, tmp_path: Path) -> None:
        """Test get_field_by_id returns field for existing ID."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_field = FormField(
                field_type="textfield",
                pages=[1],
                id="123",
                name="TestField",
                value="TestValue",
                locked=False,
            )
            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[mock_field],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor.get_field_by_id(test_file, "123")
                assert result is not None
                assert result.id == "123"
                assert result.name == "TestField"

    def test_get_field_by_id_not_found(self, tmp_path: Path) -> None:
        """Test get_field_by_id returns None for nonexistent ID."""
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
                result = extractor.get_field_by_id(test_file, "999")
                assert result is None

    def test_get_field_by_id_no_match(self, tmp_path: Path) -> None:
        """Test get_field_by_id returns None when fields exist but ID doesn't match."""
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
                        id="123",
                        name="TestField",
                        value="TestValue",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor.get_field_by_id(test_file, "999")
                assert result is None


class TestGetFieldByName:
    """Tests for get_field_by_name method."""

    def test_get_field_by_name_success(self, tmp_path: Path) -> None:
        """Test get_field_by_name returns field for existing name."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            mock_field = FormField(
                field_type="textfield",
                pages=[1],
                id="123",
                name="TestField",
                value="TestValue",
                locked=False,
            )
            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[mock_field],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor.get_field_by_name(test_file, "TestField")
                assert result is not None
                assert result.name == "TestField"
                assert result.id == "123"

    def test_get_field_by_name_not_found(self, tmp_path: Path) -> None:
        """Test get_field_by_name returns None for nonexistent name."""
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
                result = extractor.get_field_by_name(test_file, "Nonexistent")
                assert result is None

    def test_get_field_by_name_no_match(self, tmp_path: Path) -> None:
        """Test get_field_by_name returns None when fields exist but name doesn't match."""
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
                        name="OtherName",
                        value="Value",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor.get_field_by_name(test_file, "Target")
                assert result is None


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

    def test_run_command_timeout(self) -> None:
        """Test _run_command raises PDFCPUExecutionError on timeout."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor(timeout_seconds=0.1)

            with (
                patch(
                    "subprocess.run",
                    side_effect=subprocess.TimeoutExpired(
                        cmd=["/usr/bin/pdfcpu", "version"],
                        timeout=0.1,
                        stderr="timeout details",
                    ),
                ),
                pytest.raises(PDFCPUExecutionError) as exc_info,
            ):
                extractor._run_command(["version"])

            assert exc_info.value.returncode == -1
            assert "timed out" in str(exc_info.value).lower()
            assert exc_info.value.stderr == "timeout details"

    def test_run_command_sanitizes_long_stderr(self) -> None:
        """Test _run_command truncates stderr to avoid leaking excessive output."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "x" * 600

            with (
                patch("subprocess.run", return_value=mock_result),
                pytest.raises(PDFCPUExecutionError) as exc_info,
            ):
                extractor._run_command(["badcommand"])

            assert len(exc_info.value.stderr) == 500

    def test_sanitize_stderr_none(self) -> None:
        """Test _sanitize_stderr handles None values."""
        assert PDFFormExtractor._sanitize_stderr(None) == ""

    def test_sanitize_stderr_bytes(self) -> None:
        """Test _sanitize_stderr decodes bytes values."""
        assert PDFFormExtractor._sanitize_stderr(b"error bytes") == "error bytes"


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


class TestValidateFormData:
    """Tests for validate_form_data method (simple format)."""

    def test_validate_empty_data(self, tmp_path: Path) -> None:
        """Test validation with empty form data."""
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
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with patch.object(extractor, "extract", return_value=mock_form_data):
                # Empty form data should be valid
                errors = extractor.validate_form_data(test_file, {})
                assert errors == []

    def test_validate_field_not_found(self, tmp_path: Path) -> None:
        """Test validation catches field not in form."""
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
                        name="Existing",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            form_data = {"Nonexistent": "value"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                errors = extractor.validate_form_data(test_file, form_data)
                assert len(errors) == 1
                assert "Nonexistent" in errors[0]

    def test_validate_checkbox_type_error(self, tmp_path: Path) -> None:
        """Test validation catches checkbox type mismatch."""
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
                        field_type="checkbox",
                        pages=[1],
                        id="1",
                        name="Agree",
                        value=False,
                        locked=False,
                    )
                ],
                raw_data={},
            )

            form_data = {"Agree": "yes"}  # String instead of bool

            with patch.object(extractor, "extract", return_value=mock_form_data):
                errors = extractor.validate_form_data(test_file, form_data)
                assert len(errors) == 1
                assert "boolean" in errors[0].lower()

    def test_validate_strict_mode_missing_field(self, tmp_path: Path) -> None:
        """Test strict mode catches missing fields."""
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
                        name="Required",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            form_data = {}  # Empty, but strict mode requires all fields

            with patch.object(extractor, "extract", return_value=mock_form_data):
                errors = extractor.validate_form_data(test_file, form_data, strict=True)
                assert len(errors) == 1
                assert "Required" in errors[0]

    def test_validate_no_form(self, tmp_path: Path) -> None:
        """Test validation when PDF has no form."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            with (
                patch.object(extractor, "extract", side_effect=PDFFormNotFoundError("No form")),
            ):
                errors = extractor.validate_form_data(test_file, {"Name": "John"})
                assert len(errors) == 1
                assert "does not contain a form" in errors[0]

    def test_validate_allow_extra_fields(self, tmp_path: Path) -> None:
        """Test validation with allow_extra_fields=True."""
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

            form_data = {"Unknown": "value"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                errors = extractor.validate_form_data(test_file, form_data, allow_extra_fields=True)
                assert errors == []


class TestConvertToPdfcpuFormat:
    """Tests for _convert_to_pdfcpu_format method."""

    def test_convert_textfield(self, tmp_path: Path) -> None:
        """Test converting simple format with textfield."""
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
                        name="Name",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            simple_data = {"Name": "John Smith"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor._convert_to_pdfcpu_format(test_file, simple_data)

                assert "forms" in result
                assert len(result["forms"]) == 1
                assert len(result["forms"][0]["textfield"]) == 1
                field = result["forms"][0]["textfield"][0]
                assert field["name"] == "Name"
                assert field["value"] == "John Smith"
                assert field["id"] == "1"
                assert field["locked"] is False

    def test_convert_checkbox(self, tmp_path: Path) -> None:
        """Test converting simple format with checkbox."""
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
                        field_type="checkbox",
                        pages=[1],
                        id="2",
                        name="Agree",
                        value=False,
                        locked=False,
                    )
                ],
                raw_data={},
            )

            simple_data = {"Agree": True}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor._convert_to_pdfcpu_format(test_file, simple_data)

                assert len(result["forms"][0]["checkbox"]) == 1
                field = result["forms"][0]["checkbox"][0]
                assert field["name"] == "Agree"
                assert field["value"] is True

    def test_convert_unknown_field_skipped(self, tmp_path: Path) -> None:
        """Test that unknown fields are skipped during conversion."""
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
                        name="Name",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            simple_data = {"Name": "John", "Unknown": "value"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor._convert_to_pdfcpu_format(test_file, simple_data)

                # Only known field should be converted
                assert len(result["forms"][0]["textfield"]) == 1
                assert result["forms"][0]["textfield"][0]["name"] == "Name"

    def test_convert_datefield(self, tmp_path: Path) -> None:
        """Test converting simple format with datefield."""
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
                        field_type="datefield",
                        pages=[1],
                        id="3",
                        name="Date",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            simple_data = {"Date": "2025-06-01"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor._convert_to_pdfcpu_format(test_file, simple_data)

                assert len(result["forms"][0]["datefield"]) == 1
                field = result["forms"][0]["datefield"][0]
                assert field["name"] == "Date"
                assert field["value"] == "2025-06-01"
                assert "format" in field

    def test_convert_radiobuttongroup(self, tmp_path: Path) -> None:
        """Test converting simple format with radiobuttongroup."""
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
                        field_type="radiobuttongroup",
                        pages=[1],
                        id="4",
                        name="Status",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            simple_data = {"Status": "Yes"}

            with patch.object(extractor, "extract", return_value=mock_form_data):
                result = extractor._convert_to_pdfcpu_format(test_file, simple_data)

                assert len(result["forms"][0]["radiobuttongroup"]) == 1
                field = result["forms"][0]["radiobuttongroup"][0]
                assert field["name"] == "Status"
                assert "options" in field


class TestFillForm:
    """Tests for fill_form method."""

    def test_fill_form_no_form(self, tmp_path: Path) -> None:
        """Test fill_form raises when PDF has no form."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()

            with (
                patch.object(extractor, "has_form", return_value=False),
                pytest.raises(PDFFormNotFoundError),
            ):
                extractor.fill_form(test_file, {"Name": "John"})

    def test_fill_form_validation_raises(self, tmp_path: Path) -> None:
        """Test fill_form raises FormValidationError with validate=True."""
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
                        field_type="checkbox",
                        pages=[1],
                        id="1",
                        name="Agree",
                        value=False,
                        locked=False,
                    )
                ],
                raw_data={},
            )

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "extract", return_value=mock_form_data),
            ):
                # Invalid: checkbox value should be boolean
                form_data = {"Agree": "not-a-boolean"}

                with pytest.raises(FormValidationError) as exc_info:
                    extractor.fill_form(test_file, form_data, validate=True)

                assert "validation failed" in str(exc_info.value).lower()
                assert len(exc_info.value.errors) > 0

    def test_fill_form_success(self, tmp_path: Path) -> None:
        """Test fill_form succeeds with valid data."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            test_file = tmp_path / "test.pdf"
            test_file.touch()
            output_file = tmp_path / "output.pdf"

            mock_form_data = PDFFormData(
                source=test_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[
                    FormField(
                        field_type="textfield",
                        pages=[1],
                        id="1",
                        name="Name",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            mock_result = MagicMock()
            mock_result.returncode = 0

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "extract", return_value=mock_form_data),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("privacyforms_pdf.extractor.json.dump"),
                patch("pathlib.Path.unlink"),
            ):
                form_data = {"Name": "John Smith"}
                result = extractor.fill_form(test_file, form_data, output_file)
                assert result == output_file

    def test_fill_form_skip_validation(self, tmp_path: Path) -> None:
        """Test fill_form can skip validation."""
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
            mock_result = MagicMock()
            mock_result.returncode = 0

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "extract", return_value=mock_form_data),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("privacyforms_pdf.extractor.json.dump"),
                patch("pathlib.Path.unlink"),
            ):
                # Invalid data but validation is skipped
                form_data = {"Unknown": "value"}
                result = extractor.fill_form(test_file, form_data, validate=False)
                assert result == test_file

    def test_fill_form_execution_error(self, tmp_path: Path) -> None:
        """Test fill_form raises PDFCPUExecutionError when command fails."""
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
                        name="Name",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Fill command failed"

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "extract", return_value=mock_form_data),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("privacyforms_pdf.extractor.json.dump"),
                patch("pathlib.Path.unlink"),
                pytest.raises(PDFCPUExecutionError) as exc_info,
            ):
                form_data = {"Name": "John"}
                extractor.fill_form(test_file, form_data)

            assert "Fill command failed" in exc_info.value.stderr


class TestFillFormFromJSON:
    """Tests for fill_form_from_json method."""

    def test_fill_from_json_file_not_found(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises when JSON not found."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            pdf_file = tmp_path / "test.pdf"
            pdf_file.touch()
            json_file = tmp_path / "nonexistent.json"

            with pytest.raises(FileNotFoundError):
                extractor.fill_form_from_json(pdf_file, json_file)

    def test_fill_from_json_directory(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises when JSON path is directory."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            pdf_file = tmp_path / "test.pdf"
            pdf_file.touch()
            json_dir = tmp_path / "jsondir"
            json_dir.mkdir()

            with pytest.raises(FileNotFoundError) as exc_info:
                extractor.fill_form_from_json(pdf_file, json_dir)

            assert "not a file" in str(exc_info.value).lower()

    def test_fill_from_json_success(self, tmp_path: Path) -> None:
        """Test fill_form_from_json succeeds."""
        with patch.object(PDFFormExtractor, "_find_pdfcpu", return_value="/usr/bin/pdfcpu"):
            extractor = PDFFormExtractor()
            pdf_file = tmp_path / "test.pdf"
            pdf_file.touch()
            json_file = tmp_path / "data.json"
            output_file = tmp_path / "output.pdf"

            # Write valid JSON
            json_file.write_text('{"Name": "John"}')

            mock_form_data = PDFFormData(
                source=pdf_file,
                pdf_version="v1.0",
                has_form=True,
                fields=[
                    FormField(
                        field_type="textfield",
                        pages=[1],
                        id="1",
                        name="Name",
                        value="",
                        locked=False,
                    )
                ],
                raw_data={},
            )

            mock_result = MagicMock()
            mock_result.returncode = 0

            with (
                patch.object(extractor, "has_form", return_value=True),
                patch.object(extractor, "extract", return_value=mock_form_data),
                patch.object(extractor, "_run_command", return_value=mock_result),
                patch("pathlib.Path.unlink"),
            ):
                result = extractor.fill_form_from_json(pdf_file, json_file, output_file)
                assert result == output_file


class TestFormValidationError:
    """Tests for FormValidationError."""

    def test_error_message_without_errors(self) -> None:
        """Test error message without detailed errors."""
        err = FormValidationError("Validation failed")
        assert str(err) == "Validation failed"
        assert err.errors == []

    def test_error_message_with_errors(self) -> None:
        """Test error message with detailed errors."""
        err = FormValidationError("Validation failed", ["Error 1", "Error 2"])
        assert "Validation failed" in str(err)
        assert "Error 1" in str(err)
        assert "Error 2" in str(err)
