"""Tests for PDFField semantics and PDFRepresentation validators."""

from __future__ import annotations

import pytest

from privacyforms_pdf.schema import (
    PDFField,
    PDFRepresentation,
    RowGroup,
)


class TestPDFFieldScalarValidation:
    """Tests for _validate_scalar_value branch coverage."""

    def test_checkbox_value_rejects_non_bool(self) -> None:
        """Checkbox value must be bool or None (line 371)."""
        with pytest.raises(ValueError, match="checkbox value must be bool or None"):
            PDFField(name="Agree", id="f-1", type="checkbox", value="hello")

    def test_radiobuttongroup_value_rejects_non_str(self) -> None:
        """Radiobuttongroup value must be str or None (line 384)."""
        match = "radiobuttongroup value must be str or None"
        with pytest.raises(ValueError, match=match):
            PDFField(name="Status", id="f-2", type="radiobuttongroup", value=True)

    def test_combobox_value_rejects_non_str(self) -> None:
        """Combobox value must be str or None (line 384)."""
        match = "combobox value must be str or None"
        with pytest.raises(ValueError, match=match):
            PDFField(name="Country", id="f-3", type="combobox", value=True)

    def test_listbox_list_value_without_multi_select_fails(self) -> None:
        """Listbox list value requires multi_select flag (line 389)."""
        match = "list-valued listbox value requires field_flags.multi_select"
        with pytest.raises(ValueError, match=match):
            PDFField(name="Options", id="f-4", type="listbox", value=["a", "b"])

    def test_non_listbox_with_list_value_fails(self) -> None:
        """List values are only valid for listbox (line 392)."""
        field = PDFField.model_construct(name="Name", id="f-5", type="customtype", value=["a", "b"])
        with pytest.raises(ValueError, match="list values are only valid for listbox value"):
            field._validate_scalar_value(["a", "b"], label="value")


class TestPDFRepresentationValidators:
    """Tests for PDFRepresentation validator branch coverage."""

    def test_spec_version_empty_fails(self) -> None:
        """spec_version must not be empty (line 423)."""
        with pytest.raises(ValueError, match="spec_version must not be empty"):
            PDFRepresentation(spec_version="   ")

    def test_spec_version_too_long_fails(self) -> None:
        """spec_version must not exceed 32 characters (line 425)."""
        match = "spec_version exceeds maximum length of 32 characters"
        with pytest.raises(ValueError, match=match):
            PDFRepresentation(spec_version="1.0" + "x" * 40)

    def test_source_too_long_fails(self) -> None:
        """Source must not exceed 4096 characters (line 433)."""
        match = "source exceeds maximum length of 4096 characters"
        with pytest.raises(ValueError, match=match):
            PDFRepresentation(source="x" * 5000)

    def test_rows_invalid_field_reference_type(self) -> None:
        """Rows must contain only str or PDFField references (line 464)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        row = RowGroup.model_construct(fields=[123], page_index=1)
        with pytest.raises(ValueError, match="rows contain invalid field reference: 123"):
            PDFRepresentation(
                fields=[field],
                rows=[row],
            )

    def test_rows_unknown_field_after_resolution(self) -> None:
        """Rows referencing PDFField objects not in fields fail the second check (lines 472-473)."""
        field_in_doc = PDFField(name="A", id="f-1", type="textfield")
        field_not_in_doc = PDFField(name="B", id="f-2", type="textfield")
        match = "rows reference fields that are not present in fields: f-2"
        with pytest.raises(ValueError, match=match):
            PDFRepresentation(
                fields=[field_in_doc],
                rows=[RowGroup(fields=[field_not_in_doc], page_index=1)],
            )


class TestPDFRepresentationLookupMethods:
    """Tests for get_field_by_id and get_field_by_name returning None."""

    def test_get_field_by_id_returns_none(self) -> None:
        """get_field_by_id returns None for unknown id (lines 479-482)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(fields=[field])
        assert rep.get_field_by_id("unknown") is None

    def test_get_field_by_name_returns_none(self) -> None:
        """get_field_by_name returns None for unknown name (lines 486-489)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(fields=[field])
        assert rep.get_field_by_name("unknown") is None


class TestPDFRepresentationLookupMethodsMatch:
    """Tests for get_field_by_id and get_field_by_name returning a match."""

    def test_get_field_by_id_returns_match(self) -> None:
        """get_field_by_id returns the field when id matches (line 481)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(fields=[field])
        assert rep.get_field_by_id("f-1") is field

    def test_get_field_by_name_returns_match(self) -> None:
        """get_field_by_name returns the field when name matches (line 488)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        rep = PDFRepresentation(fields=[field])
        assert rep.get_field_by_name("A") is field

    def test_source_whitespace_normalized_to_none(self) -> None:
        """Whitespace-only source is normalized to None (line 433)."""
        rep = PDFRepresentation(source="   ")
        assert rep.source is None

    def test_source_none_passes_through_validator(self) -> None:
        """Explicit None source hits the early return in normalize_source (line 433)."""
        rep = PDFRepresentation(source=None)
        assert rep.source is None
