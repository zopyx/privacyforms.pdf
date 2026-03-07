"""Tests for the PDFFormExtractor class."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path as PathType
else:
    PathType = Path

from privacyforms_pdf.extractor import (
    FieldGeometry,
    FormField,
    FormValidationError,
    PDFField,
    PDFFormData,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
    get_available_geometry_backends,
    has_geometry_support,
)


class TestPDFFormExtractorInitialization:
    """Tests for PDFFormExtractor initialization."""

    def test_init_default(self) -> None:
        """Test initialization with default parameters."""
        extractor = PDFFormExtractor()
        assert extractor._extract_geometry is True
        assert extractor._timeout_seconds == 30.0

    def test_init_with_extract_geometry_false(self) -> None:
        """Test initialization with extract_geometry=False."""
        extractor = PDFFormExtractor(extract_geometry=False)
        assert extractor._extract_geometry is False

    def test_init_with_timeout(self) -> None:
        """Test initialization with custom timeout."""
        extractor = PDFFormExtractor(timeout_seconds=60.0)
        assert extractor._timeout_seconds == 60.0


class TestValidatePDFPath:
    """Tests for _validate_pdf_path method."""

    def test_validate_existing_file(self, tmp_path: Path) -> None:
        """Test validation passes for existing file."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        # Should not raise
        extractor._validate_pdf_path(test_file)

    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """Test validation raises for nonexistent file."""
        extractor = PDFFormExtractor()
        with pytest.raises(FileNotFoundError):
            extractor._validate_pdf_path(tmp_path / "nonexistent.pdf")

    def test_validate_directory(self, tmp_path: Path) -> None:
        """Test validation raises for directory."""
        extractor = PDFFormExtractor()
        with pytest.raises(FileNotFoundError):
            extractor._validate_pdf_path(tmp_path)


class TestHasForm:
    """Tests for has_form method."""

    def test_has_form_true(self, tmp_path: Path) -> None:
        """Test has_form returns True when PDF has form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        # Create a minimal mock PDF with form
        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"field1": {}}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.has_form(test_file)
            assert result is True

    def test_has_form_false(self, tmp_path: Path) -> None:
        """Test has_form returns False when PDF has no form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.has_form(test_file)
            assert result is False

    def test_has_form_empty(self, tmp_path: Path) -> None:
        """Test has_form returns False when PDF has empty form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {}

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.has_form(test_file)
            assert result is False


class TestParseFormData:
    """Tests for _build_raw_data_structure method."""

    def test_build_raw_data_empty(self, tmp_path: Path) -> None:
        """Test building raw data with empty fields list."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"

        raw_data = extractor._build_raw_data_structure([], str(test_file))

        assert raw_data["header"]["source"] == str(test_file)
        assert raw_data["header"]["version"] == "pypdf"
        assert raw_data["forms"][0]["textfield"] == []

    def test_build_raw_data_with_textfield(self, tmp_path: Path) -> None:
        """Test building raw data with textfield."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"

        field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="Test Value",
            pages=[1],
            locked=False,
        )

        raw_data = extractor._build_raw_data_structure([field], str(test_file))

        assert len(raw_data["forms"][0]["textfield"]) == 1
        assert raw_data["forms"][0]["textfield"][0]["name"] == "TestField"

    def test_build_raw_data_with_checkbox(self, tmp_path: Path) -> None:
        """Test building raw data with checkbox."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"

        field = PDFField(
            name="Agree",
            id="1",
            type="checkbox",
            value=True,
            pages=[1],
            locked=False,
        )

        raw_data = extractor._build_raw_data_structure([field], str(test_file))

        assert len(raw_data["forms"][0]["checkbox"]) == 1
        assert raw_data["forms"][0]["checkbox"][0]["value"] is True


class TestExtract:
    """Tests for extract method."""

    def test_extract_no_form(self, tmp_path: Path) -> None:
        """Test extract raises when PDF has no form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            pytest.raises(PDFFormNotFoundError),
        ):
            extractor.extract(test_file)

    def test_extract_file_not_found(self, tmp_path: Path) -> None:
        """Test extract raises when file doesn't exist."""
        extractor = PDFFormExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(tmp_path / "nonexistent.pdf")

    def test_extract_success(self, tmp_path: Path) -> None:
        """Test extract returns PDFFormData on success."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.pdf_header = "%PDF-1.4"
        mock_reader.get_fields.return_value = {
            "TestField": {
                "/FT": "/Tx",
                "/V": "Test Value",
            }
        }
        mock_reader.pages = []

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.extract(test_file)
            assert isinstance(result, PDFFormData)
            assert result.source == test_file
            assert result.pdf_version == "1.4"


class TestGetFieldType:
    """Tests for _get_field_type method."""

    def test_text_field(self) -> None:
        """Test text field type detection."""
        field = {"/FT": "/Tx"}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "textfield"

    def test_checkbox_field(self) -> None:
        """Test checkbox field type detection."""
        field = {"/FT": "/Btn", "/V": "/Off"}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "checkbox"

    def test_radiobuttongroup_field(self) -> None:
        """Test radio button group field type detection."""
        field = {"/FT": "/Btn", "/Opt": ["Option1", "Option2"]}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "radiobuttongroup"

    def test_combobox_field(self) -> None:
        """Test combobox field type detection."""
        field = {"/FT": "/Ch", "/Ff": 0x40000}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "combobox"

    def test_listbox_field(self) -> None:
        """Test listbox field type detection."""
        field = {"/FT": "/Ch", "/Ff": 0}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "listbox"

    def test_signature_field(self) -> None:
        """Test signature field type detection."""
        field = {"/FT": "/Sig"}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "signature"


class TestGetFieldValue:
    """Tests for _get_field_value method."""

    def test_string_value(self) -> None:
        """Test extracting string value."""
        field = {"/V": "Test Value"}
        result = PDFFormExtractor._get_field_value(field)
        assert result == "Test Value"

    def test_checkbox_yes(self) -> None:
        """Test extracting checkbox Yes value."""
        field = {"/V": "/Yes"}
        result = PDFFormExtractor._get_field_value(field)
        assert result is True

    def test_checkbox_off(self) -> None:
        """Test extracting checkbox Off value."""
        field = {"/V": "/Off"}
        result = PDFFormExtractor._get_field_value(field)
        assert result is False

    def test_empty_value(self) -> None:
        """Test extracting empty value."""
        field = {}
        result = PDFFormExtractor._get_field_value(field)
        assert result == ""


class TestListFields:
    """Tests for list_fields method."""

    def test_list_fields_returns_list(self, tmp_path: Path) -> None:
        """Test list_fields returns list of PDFField."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.pdf_version = "1.4"
        mock_reader.get_fields.return_value = {
            "Field1": {
                "/FT": "/Tx",
                "/V": "Value1",
            }
        }
        mock_reader.pages = []

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            fields = extractor.list_fields(test_file)
            assert len(fields) == 1
            assert isinstance(fields[0], PDFField)
            assert fields[0].name == "Field1"


class TestGetFieldValueMethod:
    """Tests for get_field_value instance method."""

    def test_get_existing_field(self, tmp_path: Path) -> None:
        """Test get_field_value returns value for existing field."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="Target",
            id="1",
            type="textfield",
            value="Found",
            pages=[1],
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
            value = extractor.get_field_value(test_file, "Target")
            assert value == "Found"

    def test_get_nonexistent_field(self, tmp_path: Path) -> None:
        """Test get_field_value returns None for nonexistent field."""
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


class TestGetFieldById:
    """Tests for get_field_by_id method."""

    def test_get_field_by_id_success(self, tmp_path: Path) -> None:
        """Test get_field_by_id returns field for existing ID."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            value="TestValue",
            pages=[1],
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
            assert isinstance(result, PDFField)
            assert result.id == "123"

    def test_get_field_by_id_not_found(self, tmp_path: Path) -> None:
        """Test get_field_by_id returns None for nonexistent ID."""
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


class TestGetFieldByName:
    """Tests for get_field_by_name method."""

    def test_get_field_by_name_success(self, tmp_path: Path) -> None:
        """Test get_field_by_name returns field for existing name."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            value="TestValue",
            pages=[1],
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
            assert isinstance(result, PDFField)
            assert result.name == "TestField"

    def test_get_field_by_name_not_found(self, tmp_path: Path) -> None:
        """Test get_field_by_name returns None for nonexistent name."""
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


class TestExtractToJSON:
    """Tests for extract_to_json method."""

    def test_extract_to_json_success(self, tmp_path: Path) -> None:
        """Test extract_to_json succeeds."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.json"

        mock_field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="TestValue",
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

        with patch.object(extractor, "extract", return_value=mock_form_data):
            extractor.extract_to_json(test_file, output_file)
            assert output_file.exists()


class TestValidateFormData:
    """Tests for validate_form_data method (simple format)."""

    def test_validate_empty_data(self, tmp_path: Path) -> None:
        """Test validation with empty form data."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="Field1",
            id="1",
            type="textfield",
            value="",
            pages=[1],
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
            errors = extractor.validate_form_data(test_file, {})
            assert errors == []

    def test_validate_field_not_found(self, tmp_path: Path) -> None:
        """Test validation catches field not in form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="Existing",
            id="1",
            type="textfield",
            value="",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        form_data = {"Nonexistent": "value"}

        with patch.object(extractor, "extract", return_value=mock_form_data):
            errors = extractor.validate_form_data(test_file, form_data)
            assert len(errors) == 1
            assert "Nonexistent" in errors[0]

    def test_validate_checkbox_type_error(self, tmp_path: Path) -> None:
        """Test validation catches checkbox type mismatch."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="Agree",
            id="1",
            type="checkbox",
            value=False,
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        form_data = {"Agree": "yes"}  # String instead of bool

        with patch.object(extractor, "extract", return_value=mock_form_data):
            errors = extractor.validate_form_data(test_file, form_data)
            assert len(errors) == 1
            assert "boolean" in errors[0].lower()

    def test_validate_strict_mode_missing_field(self, tmp_path: Path) -> None:
        """Test strict mode catches missing fields."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_field = PDFField(
            name="Required",
            id="1",
            type="textfield",
            value="",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        form_data = {}  # Empty, but strict mode requires all fields

        with patch.object(extractor, "extract", return_value=mock_form_data):
            errors = extractor.validate_form_data(test_file, form_data, strict=True)
            assert len(errors) == 1
            assert "Required" in errors[0]

    def test_validate_no_form(self, tmp_path: Path) -> None:
        """Test validation when PDF has no form."""
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


class TestFillForm:
    """Tests for fill_form method."""

    def test_fill_form_success(self, tmp_path: Path) -> None:
        """Test fill_form succeeds."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx", "/V": ""}}
        mock_reader.pages = []

        mock_writer = MagicMock()

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = extractor.fill_form(test_file, {"Name": "John"}, output_file, validate=False)
            assert result == output_file

    def test_fill_form_no_output(self, tmp_path: Path) -> None:
        """Test fill_form without output path modifies input."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx", "/V": ""}}
        mock_reader.pages = []

        mock_writer = MagicMock()

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = extractor.fill_form(test_file, {"Name": "John"}, validate=False)
            assert result == test_file

    def test_fill_form_validation_error(self, tmp_path: Path) -> None:
        """Test fill_form raises FormValidationError on validation failure."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_field = PDFField(
            name="Name",
            id="1",
            type="textfield",
            value="",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {}}

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch.object(extractor, "extract", return_value=mock_form_data),
            pytest.raises(FormValidationError),
        ):
            # Unknown field should trigger validation error
            extractor.fill_form(test_file, {"UnknownField": "value"}, output_file, validate=True)

    def test_fill_form_no_form(self, tmp_path: Path) -> None:
        """Test fill_form raises when PDF has no form."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = None

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            pytest.raises(PDFFormNotFoundError),
        ):
            extractor.fill_form(test_file, {"Name": "John"}, validate=False)


class TestFillFormFromJson:
    """Tests for fill_form_from_json method."""

    def test_fill_form_from_json_success(self, tmp_path: Path) -> None:
        """Test fill_form_from_json succeeds."""
        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "data.json"
        json_file.write_text('{"Name": "John"}')
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {}}
        mock_reader.pages = []

        mock_writer = MagicMock()

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = extractor.fill_form_from_json(pdf_file, json_file, output_file, validate=False)
            assert result == output_file

    def test_fill_form_from_json_not_found(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises FileNotFoundError for missing JSON."""
        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            extractor.fill_form_from_json(pdf_file, json_file)

    def test_fill_form_from_json_not_a_file(self, tmp_path: Path) -> None:
        """Test fill_form_from_json raises FileNotFoundError for directory."""
        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        json_dir = tmp_path / "jsondir"
        json_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            extractor.fill_form_from_json(pdf_file, json_dir)


class TestPDFField:
    """Tests for PDFField Pydantic model."""

    def test_field_creation(self) -> None:
        """Test creating a PDFField."""
        field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            value="Test Value",
            pages=[1],
            locked=False,
        )
        assert field.name == "TestField"
        assert field.id == "123"
        assert field.field_type == "textfield"
        assert field.value == "Test Value"
        assert field.pages == [1]
        assert field.locked is False

    def test_field_with_geometry(self) -> None:
        """Test PDFField with geometry."""
        geometry = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            geometry=geometry,
        )
        assert field.geometry is not None
        assert field.geometry.page == 1
        assert field.geometry.x == 100.0
        assert field.geometry.y == 200.0
        assert field.geometry.width == 200.0
        assert field.geometry.height == 200.0

    def test_field_model_dump(self) -> None:
        """Test PDFField serialization."""
        geometry = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            value="Test Value",
            pages=[1],
            locked=False,
            geometry=geometry,
        )
        data = field.model_dump()
        assert data["name"] == "TestField"
        assert data["id"] == "123"
        assert data["field_type"] == "textfield"
        assert data["geometry"] is not None
        assert data["geometry"]["page"] == 1
        assert data["geometry"]["x"] == 100.0

    def test_field_model_dump_no_geometry(self) -> None:
        """Test PDFField serialization without geometry."""
        field = PDFField(
            name="TestField",
            id="123",
            type="textfield",
            value="Test Value",
        )
        data = field.model_dump()
        assert field.name == "TestField"
        assert data["geometry"] is None


class TestFieldGeometry:
    """Tests for FieldGeometry model."""

    def test_geometry_creation(self) -> None:
        """Test creating FieldGeometry."""
        geom = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        assert geom.page == 1
        assert geom.rect == (100.0, 200.0, 300.0, 400.0)

    def test_geometry_properties(self) -> None:
        """Test FieldGeometry properties."""
        geom = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        assert geom.x == 100.0
        assert geom.y == 200.0
        assert geom.width == 200.0
        assert geom.height == 200.0

    def test_geometry_model_dump(self) -> None:
        """Test FieldGeometry serialization."""
        geom = FieldGeometry(page=1, rect=(100.0, 200.0, 300.0, 400.0))
        data = geom.model_dump()
        assert data["page"] == 1
        assert data["rect"] == [100.0, 200.0, 300.0, 400.0]
        assert data["x"] == 100.0
        assert data["y"] == 200.0
        assert data["width"] == 200.0
        assert data["height"] == 200.0
        assert data["units"] == "pt"


class TestPDFFormData:
    """Tests for PDFFormData class."""

    def test_to_json(self, tmp_path: Path) -> None:
        """Test PDFFormData to_json method."""
        field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="Test",
        )
        form_data = PDFFormData(
            source=tmp_path / "test.pdf",
            pdf_version="v1.0",
            has_form=True,
            fields=[field],
            raw_data={},
        )
        json_str = form_data.to_json()
        assert "TestField" in json_str
        assert "textfield" in json_str

    def test_to_dict(self, tmp_path: Path) -> None:
        """Test PDFFormData to_dict method."""
        field = PDFField(
            name="TestField",
            id="1",
            type="textfield",
            value="Test",
        )
        form_data = PDFFormData(
            source=tmp_path / "test.pdf",
            pdf_version="v1.0",
            has_form=True,
            fields=[field],
            raw_data={},
        )
        data = form_data.to_dict()
        assert data["pdf_version"] == "v1.0"
        assert data["has_form"] is True
        assert len(data["fields"]) == 1
        assert data["fields"][0]["name"] == "TestField"


class TestFormFieldLegacy:
    """Tests for legacy FormField class."""

    def test_form_field_creation(self) -> None:
        """Test creating legacy FormField."""
        field = FormField(
            field_type="textfield",
            pages=[1],
            id="1",
            name="Test",
            value="Value",
            locked=False,
        )
        assert field.field_type == "textfield"
        assert field.name == "Test"
        assert field.value == "Value"

    def test_form_field_equality(self) -> None:
        """Test FormField equality."""
        field1 = FormField(
            field_type="textfield",
            pages=[1],
            id="1",
            name="Test",
            value="Value",
            locked=False,
        )
        field2 = FormField(
            field_type="textfield",
            pages=[1],
            id="1",
            name="Test",
            value="Value",
            locked=False,
        )
        assert field1 == field2

    def test_form_field_equality_different_type(self) -> None:
        """Test FormField equality with non-FormField returns NotImplemented."""
        field = FormField(
            field_type="textfield",
            pages=[1],
            id="1",
            name="Test",
            value="Value",
            locked=False,
        )
        assert field != "not a form field"
        assert field != 123

    def test_form_field_repr(self) -> None:
        """Test FormField repr."""
        field = FormField(
            field_type="textfield",
            pages=[1],
            id="123",
            name="TestField",
            value="Value",
            locked=False,
        )
        repr_str = repr(field)
        assert "FormField" in repr_str
        assert "textfield" in repr_str
        assert "TestField" in repr_str
        assert "123" in repr_str


class TestFormValidationError:
    """Tests for FormValidationError."""

    def test_str_with_errors(self) -> None:
        """Test __str__ with error list."""
        err = FormValidationError("Validation failed", ["error1", "error2"])
        str_repr = str(err)
        assert "Validation failed" in str_repr
        assert "error1" in str_repr
        assert "error2" in str_repr

    def test_str_without_errors(self) -> None:
        """Test __str__ without error list."""
        err = FormValidationError("Validation failed")
        str_repr = str(err)
        assert str_repr == "Validation failed"


class TestGeometryHelpers:
    """Tests for geometry helper functions."""

    def test_get_available_geometry_backends(self) -> None:
        """Test get_available_geometry_backends returns list."""
        backends = get_available_geometry_backends()
        assert isinstance(backends, list)
        assert "pypdf" in backends

    def test_has_geometry_support(self) -> None:
        """Test has_geometry_support returns True when backend available."""
        assert has_geometry_support() is True


class TestBackwardsCompatibility:
    """Tests for backwards compatibility aliases."""

    def test_pdfcpu_error_alias(self) -> None:
        """Test PDFCPUError is alias for PDFFormError."""
        from privacyforms_pdf.extractor import PDFCPUError

        assert PDFCPUError is PDFFormError

    def test_pdfcpu_execution_error_alias(self) -> None:
        """Test PDFCPUExecutionError is alias for PDFFormError."""
        from privacyforms_pdf.extractor import PDFCPUExecutionError

        assert PDFCPUExecutionError is PDFFormError

    def test_pdfcpu_not_found_error_alias(self) -> None:
        """Test PDFCPUNotFoundError is alias for PDFFormError."""
        from privacyforms_pdf.extractor import PDFCPUNotFoundError

        assert PDFCPUNotFoundError is PDFFormError


class TestGetFieldTypeEdgeCases:
    """Tests for _get_field_type edge cases."""

    def test_field_type_from_type_when_ft_none(self) -> None:
        """Test fallback to /Type when /FT is None."""
        field = {"/Type": "/Tx"}  # No /FT key
        result = PDFFormExtractor._get_field_type(field)
        assert result == "textfield"

    def test_date_field_with_aa(self) -> None:
        """Test date field detection with /AA."""
        field = {"/FT": "/Tx", "/AA": {}}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "textfield"

    def test_date_field_with_dv(self) -> None:
        """Test date field detection with /DV."""
        field = {"/FT": "/Tx", "/DV": "default"}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "textfield"

    def test_default_fallback_textfield(self) -> None:
        """Test default fallback returns textfield for unknown types."""
        field = {"/FT": "/Unknown"}
        result = PDFFormExtractor._get_field_type(field)
        assert result == "textfield"


class TestGetFieldValueEdgeCases:
    """Tests for _get_field_value edge cases."""

    def test_nameobject_yes(self) -> None:
        """Test extracting NameObject with Yes value."""

        class MockName:
            name = "/Yes"

        field = {"/V": MockName()}
        result = PDFFormExtractor._get_field_value(field)
        assert result is True

    def test_nameobject_off(self) -> None:
        """Test extracting NameObject with Off value."""

        class MockName:
            name = "/Off"

        field = {"/V": MockName()}
        result = PDFFormExtractor._get_field_value(field)
        assert result is False

    def test_nameobject_other(self) -> None:
        """Test extracting NameObject with other value."""

        class MockName:
            name = "/SomeValue"

        field = {"/V": MockName()}
        result = PDFFormExtractor._get_field_value(field)
        assert result == "/SomeValue"


class TestGetFieldOptionsEdgeCases:
    """Tests for _get_field_options edge cases."""

    def test_options_from_kids_with_ap(self) -> None:
        """Test extracting options from Kids with appearance."""

        class MockKid:
            def get_object(self):
                return {"/AP": {"/N": {"/Option1": None, "/Option2": None}}}

        field = {"/Kids": [MockKid()]}
        result = PDFFormExtractor._get_field_options(field)
        assert "/Option1" in result
        assert "/Option2" in result

    def test_options_no_kids_no_opt(self) -> None:
        """Test empty options when no /Opt or /Kids."""
        field = {}
        result = PDFFormExtractor._get_field_options(field)
        assert result == []


class TestBuildRawDataStructure:
    """Tests for _build_raw_data_structure method."""

    def test_datefield_with_format(self) -> None:
        """Test datefield gets format in raw data."""
        extractor = PDFFormExtractor()
        field = PDFField(
            name="Date",
            id="1",
            type="datefield",
            value="2024-01-01",
            format="yyyy-mm-dd",
        )
        raw_data = extractor._build_raw_data_structure([field], "test.pdf")
        assert raw_data["forms"][0]["datefield"][0]["format"] == "yyyy-mm-dd"

    def test_field_with_options(self) -> None:
        """Test radiobuttongroup gets options in raw data."""
        extractor = PDFFormExtractor()
        field = PDFField(
            name="Radio",
            id="1",
            type="radiobuttongroup",
            value="Option1",
            options=["Option1", "Option2"],
        )
        raw_data = extractor._build_raw_data_structure([field], "test.pdf")
        assert raw_data["forms"][0]["radiobuttongroup"][0]["options"] == ["Option1", "Option2"]

    def test_unknown_field_type_fallback(self) -> None:
        """Test unknown field type falls back to textfield."""
        extractor = PDFFormExtractor()
        field = PDFField(
            name="Unknown",
            id="1",
            type="unknowntype",
            value="value",
        )
        raw_data = extractor._build_raw_data_structure([field], "test.pdf")
        assert raw_data["forms"][0]["textfield"][0]["name"] == "Unknown"

    def test_signature_field(self) -> None:
        """Test signature field is included in raw data."""
        extractor = PDFFormExtractor()
        field = PDFField(
            name="Sig",
            id="1",
            type="signature",
            value="",
        )
        raw_data = extractor._build_raw_data_structure([field], "test.pdf")
        assert len(raw_data["forms"][0]["signature"]) == 1


class TestFillFormEdgeCases:
    """Tests for fill_form edge cases."""

    def test_fill_form_validation_fails(self, tmp_path: Path) -> None:
        """Test fill_form raises FormValidationError when validation fails."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_field = PDFField(
            name="Known",
            id="1",
            type="textfield",
            value="",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        with (
            patch.object(extractor, "has_form", return_value=True),
            patch.object(extractor, "extract", return_value=mock_form_data),
            pytest.raises(FormValidationError),
        ):
            extractor.fill_form(test_file, {"Unknown": "value"}, output_file, validate=True)

    def test_fill_form_empty_data(self, tmp_path: Path) -> None:
        """Test fill_form with empty data dict."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {}}

        mock_writer = MagicMock()

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = extractor.fill_form(test_file, {}, output_file, validate=False)
            assert result == output_file
            # update_page_form_field_values should not be called with empty data
            mock_writer.update_page_form_field_values.assert_not_called()


class TestGetFieldPagesEdgeCases:
    """Tests for _get_field_pages edge cases."""

    def test_get_field_pages_exception_handling(self) -> None:
        """Test exception handling in _get_field_pages."""
        extractor = PDFFormExtractor()

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.side_effect = Exception("Error reading annotation")

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")
        # Should return default page 1 when exception occurs
        assert result == [1]

    def test_get_field_pages_wrong_subtype(self) -> None:
        """Test that non-Widget annotations are skipped."""
        extractor = PDFFormExtractor()

        class MockAnnot:
            def get(self, key, default=None):
                if key == "/Subtype":
                    return "/Link"  # Not a widget
                if key == "/T":
                    return "TestField"
                return default

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")
        # Should return default page 1 when no widget found
        assert result == [1]


class TestExtractGeometryEdgeCases:
    """Tests for _extract_geometry_from_pdf edge cases."""

    def test_extract_geometry_no_rect(self) -> None:
        """Test widget without /Rect is skipped."""
        extractor = PDFFormExtractor()

        class MockAnnot:
            def get(self, key, default=None):
                return {
                    "/Subtype": "/Widget",
                    "/T": "TestField",
                    # No /Rect
                }.get(key, default)

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)
        assert result == {}

    def test_extract_geometry_exception_handling(self) -> None:
        """Test exception handling in _extract_geometry_from_pdf."""
        extractor = PDFFormExtractor()

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.side_effect = Exception("Error reading annotation")

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)
        assert result == {}


class TestExtractAllSamplePdfs:
    """Tests for extracting form data from all sample PDFs."""

    def test_extract_filledform_pdf(self) -> None:
        """Test extracting form data from FilledForm.pdf."""
        from pathlib import Path

        pdf_path = Path("samples/FilledForm.pdf")
        if not pdf_path.exists():
            pytest.skip("FilledForm.pdf not found")

        extractor = PDFFormExtractor()
        form_data = extractor.extract(pdf_path)

        assert form_data.has_form is True
        assert len(form_data.fields) > 0
        assert form_data.source == pdf_path

        # Check for expected fields
        field_names = {f.name for f in form_data.fields}
        assert "Candidate Name" in field_names
        assert "Home phone number" in field_names

    def test_extract_bescheinigung_pdf(self) -> None:
        """Test extracting form data from Bescheinigung PDF."""
        from pathlib import Path

        pdf_path = Path("samples/Bescheinigung_ueber_die_Anrechnung_von_Studienzeiten.pdf")
        if not pdf_path.exists():
            pytest.skip("Bescheinigung PDF not found")

        extractor = PDFFormExtractor()

        # This PDF may or may not have a form
        has_form = extractor.has_form(pdf_path)

        if has_form:
            form_data = extractor.extract(pdf_path)
            assert isinstance(form_data.fields, list)
        else:
            with pytest.raises(PDFFormNotFoundError):
                extractor.extract(pdf_path)

    def test_extract_formloser_antrag_pdf(self) -> None:
        """Test extracting form data from Formloser-Antrag PDF."""
        from pathlib import Path

        pdf_path = Path("samples/Formloser-Antrag-Inland.pdf")
        if not pdf_path.exists():
            pytest.skip("Formloser-Antrag PDF not found")

        extractor = PDFFormExtractor()

        has_form = extractor.has_form(pdf_path)

        if has_form:
            form_data = extractor.extract(pdf_path)
            assert isinstance(form_data.fields, list)
        else:
            with pytest.raises(PDFFormNotFoundError):
                extractor.extract(pdf_path)

    def test_extract_vfnm_pdf(self) -> None:
        """Test extracting form data from VFNM PDF."""
        from pathlib import Path

        pdf_path = Path("samples/VFNM-2018-05-22-mustervorlage-vorblatt.pdf")
        if not pdf_path.exists():
            pytest.skip("VFNM PDF not found")

        extractor = PDFFormExtractor()

        has_form = extractor.has_form(pdf_path)

        if has_form:
            form_data = extractor.extract(pdf_path)
            assert isinstance(form_data.fields, list)
        else:
            with pytest.raises(PDFFormNotFoundError):
                extractor.extract(pdf_path)


class TestExtractEdgeCases:
    """Tests for extract method edge cases."""

    def test_extract_without_pdf_header(self, tmp_path: Path) -> None:
        """Test extract when reader has no pdf_header attribute."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        del mock_reader.pdf_header  # Remove pdf_header attribute
        mock_reader.get_fields.return_value = {
            "TestField": {"/FT": "/Tx", "/V": "Test"},
        }
        mock_reader.pages = []

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.extract(test_file)
            assert result.pdf_version == "unknown"


class TestGetFieldValueRemaining:
    """Additional tests for _get_field_value."""

    def test_non_string_non_nameobject_value(self) -> None:
        """Test handling of non-string, non-NameObject value."""
        field = {"/V": 12345}  # Integer value
        result = PDFFormExtractor._get_field_value(field)
        assert result == "12345"


class TestGetFieldOptionsRemaining:
    """Additional tests for _get_field_options."""

    def test_kid_without_ap(self) -> None:
        """Test kid without /AP is skipped."""

        class MockKid:
            def get_object(self):
                return {}  # No /AP

        field = {"/Kids": [MockKid()]}
        result = PDFFormExtractor._get_field_options(field)
        assert result == []

    def test_kid_with_ap_but_no_n(self) -> None:
        """Test kid with /AP but no /N."""

        class MockKid:
            def get_object(self):
                return {"/AP": {}}  # No /N in /AP

        field = {"/Kids": [MockKid()]}
        result = PDFFormExtractor._get_field_options(field)
        assert result == []


class TestGetFieldPagesRemaining:
    """Additional tests for _get_field_pages."""

    def test_t_value_is_nameobject(self) -> None:
        """Test T value that is a NameObject."""
        extractor = PDFFormExtractor()

        class MockName:
            name = "TestField"

        class MockAnnot:
            def get(self, key, default=None):
                if key == "/Subtype":
                    return "/Widget"
                if key == "/T":
                    return MockName()
                return default

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")
        assert result == [1]

    def test_no_t_value(self) -> None:
        """Test widget without T value is skipped."""
        extractor = PDFFormExtractor()

        class MockAnnot:
            def get(self, key, default=None):
                if key == "/Subtype":
                    return "/Widget"
                if key == "/T":
                    return None
                return default

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")
        assert result == [1]  # Default page


class TestExtractGeometryRemaining:
    """Additional tests for _extract_geometry_from_pdf."""

    def test_non_widget_subtype(self) -> None:
        """Test non-widget annotation is skipped."""
        extractor = PDFFormExtractor()

        class MockAnnot:
            def get(self, key, default=None):
                return {
                    "/Subtype": "/Link",  # Not a widget
                    "/T": "TestField",
                    "/Rect": [0, 0, 100, 100],
                }.get(key, default)

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)
        assert result == {}

    def test_no_t_value_in_widget(self) -> None:
        """Test widget without T value is skipped."""
        extractor = PDFFormExtractor()

        class MockAnnot:
            def get(self, key, default=None):
                if key == "/Subtype":
                    return "/Widget"
                if key == "/T":
                    return None
                return default

        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = MockAnnot()

        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)
        assert result == {}


class TestFillFormValidationBranch:
    """Test for fill_form validation branch."""

    def test_fill_form_with_validation_errors(self, tmp_path: Path) -> None:
        """Test fill_form raises error when validation finds errors."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_field = PDFField(
            name="Name",
            id="1",
            type="textfield",
            value="",
            pages=[1],
            locked=False,
        )
        mock_form_data = PDFFormData(
            source=test_file,
            pdf_version="v1.0",
            has_form=True,
            fields=[mock_field],
            raw_data={},
        )

        with (
            patch.object(extractor, "has_form", return_value=True),
            patch.object(extractor, "extract", return_value=mock_form_data),
            pytest.raises(FormValidationError),
        ):
            # Passing unknown field triggers validation error
            extractor.fill_form(test_file, {"UnknownField": "value"}, output_file, validate=True)


class TestExtractGeometryFromPdf:
    """Tests for _extract_geometry_from_pdf method."""

    def test_extract_geometry_with_widget(self) -> None:
        """Test extracting geometry from widget annotations."""
        extractor = PDFFormExtractor()

        # Create a proper mock that simulates pypdf dictionary object
        class MockAnnot:
            def __init__(self):
                self.data = {
                    "/Subtype": "/Widget",
                    "/T": "TestField",
                    "/Rect": [100.0, 200.0, 300.0, 400.0],
                }

            def get(self, key, default=None):
                return self.data.get(key, default)

        mock_annot = MockAnnot()
        mock_annot_ref = MagicMock()
        mock_annot_ref.get_object.return_value = mock_annot

        # Create a mock page that behaves like a dict for "/Annots"
        class MockPage(dict):
            def __init__(self):
                super().__init__()
                self["/Annots"] = [mock_annot_ref]

            def get(self, key, default=None):
                return self["/Annots"] if key == "/Annots" else default

        mock_page = MockPage()

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)

        assert "TestField" in result
        assert result["TestField"].page == 1
        assert result["TestField"].rect == (100.0, 200.0, 300.0, 400.0)

    def test_extract_geometry_no_annots(self) -> None:
        """Test extracting geometry when page has no annotations."""
        extractor = PDFFormExtractor()

        mock_page = MagicMock()
        mock_page.__contains__ = lambda self, key: False

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)

        assert result == {}

    def test_extract_geometry_non_widget_annot(self) -> None:
        """Test that non-widget annotations are skipped."""
        extractor = PDFFormExtractor()

        mock_annot = MagicMock()
        mock_annot.get.side_effect = lambda key: {
            "/Subtype": "/Link",  # Not a widget
            "/T": "TestField",
        }.get(key)

        mock_page = MagicMock()
        mock_page.__contains__ = lambda self, key: key == "/Annots"

        def _get_annot(key, default=None):
            if key == "/Annots":
                return [MagicMock(get_object=lambda: mock_annot)]
            return default

        mock_page.get.side_effect = _get_annot

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._extract_geometry_from_pdf(mock_reader)

        assert result == {}


class TestGetFieldPages:
    """Tests for _get_field_pages method."""

    def test_get_field_pages_with_widget(self) -> None:
        """Test finding field pages with widget annotation."""
        extractor = PDFFormExtractor()

        mock_annot = MagicMock()
        mock_annot.get.side_effect = lambda key: {
            "/Subtype": "/Widget",
            "/T": "TestField",
        }.get(key)

        mock_page = MagicMock()
        mock_page.__contains__ = lambda self, key: key == "/Annots"

        def _get_annot(key, default=None):
            if key == "/Annots":
                return [MagicMock(get_object=lambda: mock_annot)]
            return default

        mock_page.get.side_effect = _get_annot

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")

        assert result == [1]

    def test_get_field_pages_no_annots(self) -> None:
        """Test finding field pages when no annotations exist."""
        extractor = PDFFormExtractor()

        mock_page = MagicMock()
        mock_page.__contains__ = lambda self, key: False

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        result = extractor._get_field_pages(mock_reader, "TestField")

        assert result == [1]  # Defaults to page 1


class TestGetFieldOptions:
    """Tests for _get_field_options method."""

    def test_options_from_opt(self) -> None:
        """Test extracting options from /Opt key."""
        field = {"/Opt": ["Option1", "Option2", "Option3"]}
        result = PDFFormExtractor._get_field_options(field)
        assert result == ["Option1", "Option2", "Option3"]

    def test_options_empty(self) -> None:
        """Test extracting options when none exist."""
        field = {}
        result = PDFFormExtractor._get_field_options(field)
        assert result == []


class TestFillFormWithRealPdf:
    """Tests for fill_form with actual PDF operations."""

    def test_fill_form_updates_field_values(self, tmp_path: Path) -> None:
        """Test that fill_form properly updates field values."""
        extractor = PDFFormExtractor()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {
            "Name": {"/FT": "/Tx", "/V": ""},
            "Agree": {"/FT": "/Btn", "/V": "/Off"},
        }
        mock_reader.pages = [MagicMock()]

        mock_writer = MagicMock()

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = extractor.fill_form(
                test_file,
                {"Name": "John", "Agree": True},
                output_file,
                validate=False,
            )
            assert result == output_file
            # Verify writer was called (append is used now instead of add_page)
            mock_writer.append.assert_called_once()
            mock_writer.write.assert_called_once()


class TestPDFFieldOptions:
    """Tests for PDFField with options."""

    def test_field_with_options(self) -> None:
        """Test creating a PDFField with options."""
        field = PDFField(
            name="RadioField",
            id="1",
            type="radiobuttongroup",
            value="Option1",
            options=["Option1", "Option2", "Option3"],
        )
        assert field.options == ["Option1", "Option2", "Option3"]
        data = field.model_dump()
        assert data["options"] == ["Option1", "Option2", "Option3"]

    def test_field_with_format(self) -> None:
        """Test creating a PDFField with date format."""
        field = PDFField(
            name="DateField",
            id="1",
            type="datefield",
            value="2024-01-01",
            format="yyyy-mm-dd",
        )
        assert field.format == "yyyy-mm-dd"


class TestExtractGeometryDisabled:
    """Tests for extract with geometry disabled."""

    def test_extract_without_geometry(self, tmp_path: Path) -> None:
        """Test extract when extract_geometry is False."""
        extractor = PDFFormExtractor(extract_geometry=False)
        test_file = tmp_path / "test.pdf"
        test_file.touch()

        mock_reader = MagicMock()
        mock_reader.pdf_version = "1.4"
        mock_reader.get_fields.return_value = {
            "TestField": {
                "/FT": "/Tx",
                "/V": "Test Value",
            }
        }
        mock_reader.pages = []

        with patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader):
            result = extractor.extract(test_file)
            assert isinstance(result, PDFFormData)
            # Field should have no geometry
            assert result.fields[0].geometry is None
