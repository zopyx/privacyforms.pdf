"""Tests for the canonical PDF schema and parser module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from privacyforms_pdf.parser import extract_pdf_form, parse_pdf
from privacyforms_pdf.schema import (
    ChoiceOption,
    FieldFlags,
    PDFField,
    PDFRepresentation,
    RowGroup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FILLED_FORM_SAMPLE = REPO_ROOT / "samples" / "FilledForm.pdf"


class TestPDFSchemaValidation:
    """Tests for strict Pydantic schema validation."""

    def test_valid_textfield(self) -> None:
        """Test a minimal valid textfield."""
        field = PDFField(name="Name", id="f-1", type="textfield", value="Jane")
        assert field.name == "Name"
        assert field.value == "Jane"

    def test_checkbox_accepts_bool(self) -> None:
        """Test checkbox accepts bool values."""
        field = PDFField(name="Agree", id="f-2", type="checkbox", value=True)
        assert field.value is True

    def test_checkbox_rejects_string_value(self) -> None:
        """Test strict validation rejects string for checkbox value."""
        with pytest.raises(ValueError):
            PDFField(name="Agree", id="f-2", type="checkbox", value="yes")

    def test_checkbox_rejects_string_default_value(self) -> None:
        """Test strict validation rejects string for checkbox default_value."""
        with pytest.raises(ValueError):
            PDFField(name="Agree", id="f-2", type="checkbox", default_value="yes")

    def test_extra_field_rejected(self) -> None:
        """Test extra fields are rejected in strict mode."""
        with pytest.raises(ValueError):
            PDFField(name="Name", id="f-1", type="textfield", unknown_field="x")  # type: ignore

    def test_coercion_rejected_for_id(self) -> None:
        """Test integer ids are not coerced to strings."""
        with pytest.raises(ValueError):
            PDFField(name="Name", id=123, type="textfield")  # type: ignore

    def test_datefield_only_allows_format(self) -> None:
        """Test format is only valid on datefield."""
        PDFField(name="Date", id="f-3", type="datefield", format="yyyy-mm-dd")
        with pytest.raises(ValueError):
            PDFField(name="Name", id="f-3", type="textfield", format="yyyy-mm-dd")

    def test_textarea_hints_only_for_textarea(self) -> None:
        """Test textarea rows/cols are only valid on textarea."""
        PDFField(name="Notes", id="f-4", type="textarea", textarea_rows=4)
        with pytest.raises(ValueError):
            PDFField(name="Name", id="f-4", type="textfield", textarea_rows=4)

    def test_choices_only_for_choice_fields(self) -> None:
        """Test choices are only valid on choice fields."""
        with pytest.raises(ValueError):
            PDFField(
                name="Name",
                id="f-5",
                type="textfield",
                choices=[ChoiceOption(value="a")],
            )

    def test_textfield_rejects_list_default_value(self) -> None:
        """Test textfield default_value must not be a list."""
        with pytest.raises(ValueError):
            PDFField(name="Name", id="f-5", type="textfield", default_value=["a"])

    def test_field_ids_must_be_unique(self) -> None:
        """Test duplicate field ids are rejected."""
        with pytest.raises(ValueError):
            PDFRepresentation(
                fields=[
                    PDFField(name="A", id="f-1", type="textfield"),
                    PDFField(name="B", id="f-1", type="textfield"),
                ]
            )

    def test_rows_must_reference_valid_fields(self) -> None:
        """Test rows referencing unknown field ids are rejected."""
        field = PDFField(name="A", id="f-1", type="textfield")
        with pytest.raises(ValueError):
            PDFRepresentation(
                fields=[field],
                rows=[RowGroup(fields=["f-999"], page_index=1)],
            )

    def test_row_group_resolves_string_ids(self) -> None:
        """Test RowGroup resolves string IDs to PDFField objects."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(
            fields=[field],
            rows=[RowGroup(fields=["f-1"], page_index=1)],
        )
        assert len(rep.rows) == 1
        assert isinstance(rep.rows[0].fields[0], PDFField)
        assert rep.rows[0].fields[0].id == "f-1"


class TestPDFSchemaSerialization:
    """Tests for compact JSON serialization."""

    def test_compact_json_omits_none_and_defaults(self) -> None:
        """Test compact JSON omits None values and defaults."""
        field = PDFField(name="Name", id="f-1", type="textfield", value="Jane")
        rep = PDFRepresentation(fields=[field])
        json_text = rep.to_compact_json()
        data = json.loads(json_text)
        assert "title" not in data["fields"][0]
        assert "field_flags" not in data["fields"][0]

    def test_field_flags_only_serializes_true_values(self) -> None:
        """Test FieldFlags only serializes True values."""
        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            field_flags=FieldFlags(required=True),
        )
        rep = PDFRepresentation(fields=[field])
        data = json.loads(rep.to_compact_json())
        flags = data["fields"][0]["field_flags"]
        assert flags == {"required": True}

    def test_row_group_serializes_field_ids(self) -> None:
        """Test RowGroup serializes fields as IDs."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(
            fields=[field],
            rows=[RowGroup(fields=[field], page_index=1)],
        )
        data = json.loads(rep.to_compact_json())
        assert data["rows"][0]["fields"] == ["f-1"]

    def test_round_trip_with_row_ids(self) -> None:
        """Test JSON round-trip resolves row IDs back to objects."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(
            fields=[field],
            rows=[RowGroup(fields=[field], page_index=1)],
        )
        json_text = rep.to_compact_json()
        restored = PDFRepresentation.model_validate_json(json_text)
        assert len(restored.rows) == 1
        assert isinstance(restored.rows[0].fields[0], PDFField)


class TestPDFParserUnit:
    """Unit tests for parser functions with mocked pypdf."""

    def test_parse_pdf_empty_form_uses_explicit_source(self, tmp_path: Path) -> None:
        """Test parsing a PDF with no form fields preserves an explicit source."""
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {}
            result = parse_pdf(tmp_path / "empty.pdf", source="empty.pdf")
            assert result.fields == []
            assert result.rows == []
            assert result.source == "empty.pdf"

    def test_parse_pdf_textfield(self, tmp_path: Path) -> None:
        """Test parsing a single textfield."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Name"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/V"): TextStringObject("Jane Doe"),
                NameObject("/Ff"): NumberObject(0),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Name": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert len(result.fields) == 1
            assert result.fields[0].name == "Name"
            assert result.fields[0].type == "textfield"
            assert result.fields[0].value == "Jane Doe"

    def test_parse_pdf_checkbox(self, tmp_path: Path) -> None:
        """Test parsing a checkbox field."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Agree"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): NameObject("/Yes"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Agree": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "checkbox"
            assert result.fields[0].value is True

    def test_parse_pdf_radiobuttongroup(self, tmp_path: Path) -> None:
        """Test parsing a radio button group."""
        kid1 = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(10), NumberObject(20), NumberObject(30), NumberObject(40)]
                ),
                NameObject("/AS"): NameObject("/OptionA"),
                NameObject("/AP"): DictionaryObject(
                    {
                        NameObject("/N"): DictionaryObject(
                            {
                                NameObject("/Off"): DictionaryObject(),
                                NameObject("/OptionA"): DictionaryObject(),
                            }
                        )
                    }
                ),
            }
        )
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Status"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): NameObject("/OptionA"),
                NameObject("/Ff"): NumberObject(49152),
                NameObject("/Kids"): ArrayObject([kid1]),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Status": field_dict}
            mock_page = MagicMock()
            mock_page.get.return_value = None
            mock_reader.return_value.pages = [mock_page]
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "radiobuttongroup"
            assert result.fields[0].value == "OptionA"
            assert len(result.fields[0].choices) == 1
            assert result.fields[0].choices[0].value == "OptionA"

    def test_parse_pdf_skips_pushbutton(self, tmp_path: Path) -> None:
        """Test unsupported pushbuttons are omitted from parsed fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Submit"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/Ff"): NumberObject(1 << 16),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Submit": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields == []
            assert result.rows == []
            assert result.source == "form.pdf"

    def test_extract_pdf_form_facade(self, tmp_path: Path) -> None:
        """Test extract_pdf_form facade calls parse_pdf."""
        with patch("privacyforms_pdf.parser.parse_pdf") as mock_parse:
            mock_parse.return_value = PDFRepresentation(fields=[])
            extract_pdf_form(tmp_path / "form.pdf")
            mock_parse.assert_called_once()


class TestPDFParserIntegration:
    """Integration tests with real PDF files."""

    def test_parse_filled_form(self) -> None:
        """Test parsing the real FilledForm.pdf sample."""
        pdf_path = FILLED_FORM_SAMPLE
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")

        result = parse_pdf(pdf_path)
        assert isinstance(result, PDFRepresentation)
        assert len(result.fields) > 0
        assert result.source == pdf_path.name

        # Verify expected field types
        names = {f.name: f.type for f in result.fields}
        assert names.get("Candidate Name") == "datefield"
        assert names.get("Special skills") == "textarea"
        assert names.get("Signature") == "signature"
        assert names.get("Diploma or GED") == "radiobuttongroup"

        # Verify rows exist and resolve correctly
        if result.rows:
            assert isinstance(result.rows[0].fields[0], PDFField)

    def test_round_trip_serialization(self) -> None:
        """Test JSON round-trip with real parsed data."""
        pdf_path = FILLED_FORM_SAMPLE
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")

        result = parse_pdf(pdf_path)
        json_text = result.to_compact_json()
        restored = PDFRepresentation.model_validate_json(json_text)
        assert len(restored.fields) == len(result.fields)
        assert len(restored.rows) == len(result.rows)
