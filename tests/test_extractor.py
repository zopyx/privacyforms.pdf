"""Tests for the PDFFormService class."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from privacyforms_pdf.extractor import (
    FormValidationError,
    PDFFormNotFoundError,
    PDFFormService,
    cluster_y_positions,
    get_available_geometry_backends,
    has_geometry_support,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestPDFFormServiceInitialization:
    """Tests for service initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        service = PDFFormService()
        assert service._timeout_seconds == 30.0
        assert service._extract_geometry is True

    def test_custom_initialization(self) -> None:
        """Test initialization with custom values."""
        service = PDFFormService(timeout_seconds=60.0, extract_geometry=False)
        assert service._timeout_seconds == 60.0
        assert service._extract_geometry is False


class TestValidatePDFPath:
    """Tests for _validate_pdf_path method."""

    def test_valid_pdf_path(self, tmp_path: Path) -> None:
        """Test valid PDF path."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        service._validate_pdf_path(test_file)

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test nonexistent file raises FileNotFoundError."""
        service = PDFFormService()
        with pytest.raises(FileNotFoundError):
            service._validate_pdf_path(tmp_path / "nonexistent.pdf")

    def test_directory_path(self, tmp_path: Path) -> None:
        """Test directory path raises FileNotFoundError."""
        service = PDFFormService()
        with pytest.raises(FileNotFoundError):
            service._validate_pdf_path(tmp_path)


class TestHasForm:
    """Tests for has_form method."""

    def test_pdf_with_form(self, tmp_path: Path) -> None:
        """Test PDF with form returns True."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            assert service.has_form(test_file) is True

    def test_pdf_without_form(self, tmp_path: Path) -> None:
        """Test PDF without form returns False."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            assert service.has_form(test_file) is False


class TestExtractFacade:
    """Tests for parse/read facade methods."""

    def test_extract_delegates_to_parse_pdf(self, tmp_path: Path) -> None:
        """Test extract delegates to parse_pdf."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        expected = MagicMock()

        with patch("privacyforms_pdf.extractor.parse_pdf", return_value=expected):
            result = service.extract(test_file)
            assert result is expected

    def test_extract_to_json_writes_compact_json(self, tmp_path: Path) -> None:
        """Test extract_to_json writes parsed representation JSON."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "out.json"
        representation = MagicMock()
        representation.to_compact_json.return_value = '{"fields": []}'

        with patch.object(service, "extract", return_value=representation) as mock_extract:
            service.extract_to_json(test_file, output_file)
            mock_extract.assert_called_once_with(test_file, source=None)
            assert output_file.read_text(encoding="utf-8") == '{"fields": []}'

    def test_list_fields_returns_representation_fields(self, tmp_path: Path) -> None:
        """Test list_fields returns the parsed fields."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        field = MagicMock()
        representation = MagicMock(fields=[field])

        with patch.object(service, "extract", return_value=representation):
            assert service.list_fields(test_file) == [field]

    def test_get_field_helpers_use_representation(self, tmp_path: Path) -> None:
        """Test get_field_by_id, get_field_by_name, and get_field_value."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        field = MagicMock(value="Jane")
        representation = MagicMock()
        representation.get_field_by_id.return_value = field
        representation.get_field_by_name.return_value = field

        with patch.object(service, "extract", return_value=representation):
            assert service.get_field_by_id(test_file, "f-0") is field
            assert service.get_field_by_name(test_file, "Name") is field
            assert service.get_field_value(test_file, "Name") == "Jane"

    def test_empty_fields(self, tmp_path: Path) -> None:
        """Test PDF with empty fields dict returns False."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            assert service.has_form(test_file) is False


class TestGetFieldHelpers:
    """Tests for static field helper methods."""

    def test_get_field_type_textfield(self) -> None:
        """Test textfield type detection."""
        assert PDFFormService._get_field_type({"/FT": "/Tx"}) == "textfield"

    def test_get_field_type_checkbox(self) -> None:
        """Test checkbox type detection."""
        assert PDFFormService._get_field_type({"/FT": "/Btn", "/V": "/Off"}) == "checkbox"

    def test_get_field_type_radiobuttongroup(self) -> None:
        """Test radiobuttongroup type detection."""
        assert (
            PDFFormService._get_field_type({"/FT": "/Btn", "/Opt": ["A", "B"]})
            == "radiobuttongroup"
        )

    def test_get_field_value_bool(self) -> None:
        """Test boolean value extraction."""
        assert PDFFormService._get_field_value({"/V": "/Yes"}) is True
        assert PDFFormService._get_field_value({"/V": "/Off"}) is False

    def test_get_field_value_string(self) -> None:
        """Test string value extraction."""
        assert PDFFormService._get_field_value({"/V": "hello"}) == "hello"

    def test_get_field_options_from_opt(self) -> None:
        """Test options extraction from /Opt."""
        assert PDFFormService._get_field_options({"/Opt": ["A", "B"]}) == ["A", "B"]

    def test_get_field_value_none(self) -> None:
        """Test returning empty string when value is None."""
        assert PDFFormService._get_field_value({}) == ""

    def test_get_field_value_name_object_yes(self) -> None:
        """Test NameObject with yes returns True."""
        mock_name = MagicMock()
        mock_name.name = "/Yes"
        assert PDFFormService._get_field_value({"/V": mock_name}) is True

    def test_get_field_value_name_object_off(self) -> None:
        """Test NameObject with off returns False."""
        mock_name = MagicMock()
        mock_name.name = "/Off"
        assert PDFFormService._get_field_value({"/V": mock_name}) is False

    def test_get_field_value_name_object_other(self) -> None:
        """Test NameObject with arbitrary value returns string."""
        mock_name = MagicMock()
        mock_name.name = "/SomeName"
        assert PDFFormService._get_field_value({"/V": mock_name}) == "/SomeName"

    def test_get_field_value_non_str_object(self) -> None:
        """Test non-string, non-name value returns str(value)."""
        assert PDFFormService._get_field_value({"/V": 123}) == "123"


class TestValidateFormData:
    """Tests for validate_form_data method."""

    def test_valid_form_data(self, tmp_path: Path) -> None:
        """Test validation with valid form data."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {"Name": "John"})
            assert errors == []

    def test_unknown_field(self, tmp_path: Path) -> None:
        """Test validation fails for unknown field."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {"Unknown": "x"})
            assert len(errors) == 1
            assert "not found in form" in errors[0]

    def test_checkbox_non_bool(self, tmp_path: Path) -> None:
        """Test validation catches non-bool checkbox value."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Agree": {"/FT": "/Btn", "/V": "/Off"}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {"Agree": "yes"})
            assert "checkbox value must be boolean" in errors[0]

    def test_strict_mode(self, tmp_path: Path) -> None:
        """Test strict mode requires all fields."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {}, strict=True)
            assert "Required field not provided" in errors[0]

    def test_no_form(self, tmp_path: Path) -> None:
        """Test validation returns error when PDF has no form."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {"Name": "John"})
            assert errors == ["PDF does not contain a form"]

    def test_allow_extra_fields(self, tmp_path: Path) -> None:
        """Test allow_extra_fields permits unknown keys."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(
                test_file, {"Name": "John", "Extra": "x"}, allow_extra_fields=True
            )
            assert errors == []

    def test_pdf_read_failure(self, tmp_path: Path) -> None:
        """Test validation catches PdfReader exception."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with patch("privacyforms_pdf.extractor.PdfReader", side_effect=Exception("corrupted")):
            errors = service.validate_form_data(test_file, {"Name": "John"})
            assert len(errors) == 1
            assert "Could not read PDF" in errors[0]

    def test_strict_mode_multiple_missing(self, tmp_path: Path) -> None:
        """Test strict mode requires all fields with loop continuation."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {
            "Name": {"/FT": "/Tx"},
            "Email": {"/FT": "/Tx"},
        }

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            errors = service.validate_form_data(test_file, {"Name": "John"}, strict=True)
            assert len(errors) == 1
            assert "Required field not provided: 'Email'" in errors[0]

    def test_validate_form_data_with_id_keys(self, tmp_path: Path) -> None:
        """Test validation supports field IDs when requested."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}
        parsed_field = type("ParsedField", (), {"id": "f-0", "name": "Name"})()
        parsed_representation = MagicMock(fields=[parsed_field])

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service, "extract", return_value=parsed_representation),
        ):
            errors = service.validate_form_data(test_file, {"f-0": "John"}, key_mode="id")
            assert errors == []

    def test_validate_form_data_auto_keys_accepts_names_and_ids(self, tmp_path: Path) -> None:
        """Test auto key mode accepts mixed name and ID keys."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {
            "Name": {"/FT": "/Tx"},
            "Agree": {"/FT": "/Btn", "/V": "/Off"},
        }
        name_field = type("ParsedField", (), {"id": "f-0", "name": "Name"})()
        checkbox_field = type("ParsedField", (), {"id": "f-1", "name": "Agree"})()
        parsed_representation = MagicMock(fields=[name_field, checkbox_field])

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service, "extract", return_value=parsed_representation),
        ):
            errors = service.validate_form_data(
                test_file,
                {"f-0": "John", "Agree": True},
                key_mode="auto",
            )
            assert errors == []


class TestFillForm:
    """Tests for fill_form method."""

    def test_fill_form_no_form(self, tmp_path: Path) -> None:
        """Test fill_form raises when PDF has no form."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            pytest.raises(PDFFormNotFoundError),
        ):
            service.fill_form(test_file, {"Name": "John"}, validate=False)

    def test_fill_form_validation_failure(self, tmp_path: Path) -> None:
        """Test fill_form raises on validation failure."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            pytest.raises(FormValidationError),
        ):
            service.fill_form(test_file, {"Unknown": "x"}, validate=True)

    def test_fill_form_delegates_to_filler(self, tmp_path: Path) -> None:
        """Test fill_form delegates to FormFiller.fill."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service._filler, "fill", return_value=output_file) as mock_fill,
        ):
            result = service.fill_form(test_file, {"Name": "John"}, output_file, validate=False)
            assert result == output_file
            mock_fill.assert_called_once_with(test_file, {"Name": "John"}, output_file)

    def test_fill_form_falls_back_on_pypdf_appearance_error(self, tmp_path: Path) -> None:
        """Test fill_form fallback is used for pypdf appearance-stream bug."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx", "/V": ""}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]
        mock_writer.update_page_form_field_values.side_effect = AttributeError(
            "'int' object has no attribute 'encode'"
        )

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
            patch.object(
                service._filler,
                "_fill_form_fields_without_appearance",
            ) as fallback,
        ):
            result = service.fill_form(test_file, {"Name": "John"}, output_file, validate=False)
            assert result == output_file
            fallback.assert_called_once_with(mock_writer, {"Name": "John"})

    def test_fill_form_with_validation_success(self, tmp_path: Path) -> None:
        """Test fill_form with validate=True and valid data delegates to filler."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service._filler, "fill", return_value=output_file) as mock_fill,
        ):
            result = service.fill_form(test_file, {"Name": "John"}, output_file, validate=True)
            assert result == output_file
            mock_fill.assert_called_once_with(test_file, {"Name": "John"}, output_file)

    def test_fill_form_with_id_keys_normalizes_before_fill(self, tmp_path: Path) -> None:
        """Test fill_form maps field IDs to names before delegating to the filler."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}
        parsed_field = type("ParsedField", (), {"id": "f-0", "name": "Name"})()
        parsed_representation = MagicMock(fields=[parsed_field])

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service, "extract", return_value=parsed_representation),
            patch.object(service._filler, "fill", return_value=output_file) as mock_fill,
        ):
            result = service.fill_form(
                test_file,
                {"f-0": "John"},
                output_file,
                validate=True,
                key_mode="id",
            )
            assert result == output_file
            mock_fill.assert_called_once_with(test_file, {"Name": "John"}, output_file)

    def test_fill_form_duplicate_keys_raise(self, tmp_path: Path) -> None:
        """Test fill_form raises when two keys map to the same form field."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}
        parsed_field = type("ParsedField", (), {"id": "f-0", "name": "Name"})()
        parsed_representation = MagicMock(fields=[parsed_field])

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service, "extract", return_value=parsed_representation),
            pytest.raises(FormValidationError, match="key normalization failed"),
        ):
            service.fill_form(
                test_file,
                {"Name": "John", "f-0": "Jane"},
                output_file,
                validate=False,
                key_mode="auto",
            )


class TestFillFormFromJson:
    """Tests for fill_form_from_json method."""

    def test_fill_form_from_json_success(self, tmp_path: Path) -> None:
        """Test fill_form_from_json reads JSON and delegates."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "John"}')
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(service._filler, "fill", return_value=output_file) as mock_fill,
        ):
            result = service.fill_form_from_json(test_file, json_file, output_file, validate=False)
            assert result == output_file
            mock_fill.assert_called_once_with(test_file, {"Name": "John"}, output_file)

    def test_fill_form_from_json_not_found(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises when JSON not found."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        with pytest.raises(FileNotFoundError):
            service.fill_form_from_json(test_file, tmp_path / "missing.json")

    def test_fill_form_from_json_directory(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises when JSON path is a directory."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        json_dir = tmp_path / "data_dir"
        json_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Path is not a file"):
            service.fill_form_from_json(test_file, json_dir)

    def test_fill_form_from_json_rejects_nested_json(self, tmp_path: Path) -> None:
        """Test fill_form_from_json rejects overly nested JSON."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        json_file = tmp_path / "data.json"
        deep: dict[str, object] = {"key": "value"}
        for _ in range(55):
            deep = {"nested": deep}
        json_file.write_text(json.dumps(deep), encoding="utf-8")

        with pytest.raises(ValueError, match="maximum nesting depth"):
            service.fill_form_from_json(test_file, json_file)

    def test_fill_form_from_json_rejects_non_object(self, tmp_path: Path) -> None:
        """Test fill_form_from_json rejects non-object JSON payloads."""
        service = PDFFormService()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('["not", "an", "object"]', encoding="utf-8")

        with pytest.raises(ValueError, match="top-level object"):
            service.fill_form_from_json(test_file, json_file)


class TestBackwardsCompatibility:
    """Tests for backwards compatibility re-exports."""

    def test_cluster_y_positions_export(self) -> None:
        """Test cluster_y_positions is exported."""
        result = cluster_y_positions([10.0, 25.0, 40.0], 15.0)
        assert isinstance(result, dict)

    def test_geometry_helpers_export(self) -> None:
        """Test geometry backend helpers are exported."""
        assert get_available_geometry_backends() == ["pypdf"]
        assert has_geometry_support() is True
