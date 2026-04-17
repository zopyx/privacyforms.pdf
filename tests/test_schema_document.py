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
        """radiobuttongroup value must be str or None (line 384)."""
        with pytest.raises(ValueError, match="radiobuttongroup value must be str or None"):
            PDFField(name="Status", id="f-2", type="radiobuttongroup", value=True)

    def test_combobox_value_rejects_non_str(self) -> None:
        """combobox value must be str or None (line 384)."""
        with pytest.raises(ValueError, match="combobox value must be str or None"):
            PDFField(name="Country", id="f-3", type="combobox", value=True)

    def test_listbox_list_value_without_multi_select_fails(self) -> None:
        """listbox list value requires multi_select flag (line 389)."""
        with pytest.raises(ValueError, match="list-valued listbox value requires field_flags.multi_select"):
            PDFField(name="Options", id="f-4", type="listbox", value=["a", "b"])

    def test_non_listbox_with_list_value_fails(self) -> None:
        """list values are only valid for listbox (line 392)."""
        field = PDFField.model_construct(name="Name", id="f-5", type="customtype", value=["a", "b"])
        with pytest.raises(ValueError, match="list values are only valid for listbox value"):
            field.validate_field_semantics()


class TestPDFRepresentationValidators:
    """Tests for PDFRepresentation validator branch coverage."""

    def test_spec_version_empty_fails(self) -> None:
        """spec_version must not be empty (line 423)."""
        with pytest.raises(ValueError, match="spec_version must not be empty"):
            PDFRepresentation(spec_version="   ")

    def test_spec_version_too_long_fails(self) -> None:
        """spec_version must not exceed 32 characters (line 425)."""
        with pytest.raises(ValueError, match="spec_version exceeds maximum length of 32 characters"):
            PDFRepresentation(spec_version="1.0" + "x" * 40)

    def test_source_too_long_fails(self) -> None:
        """source must not exceed 4096 characters (line 433)."""
        with pytest.raises(ValueError, match="source exceeds maximum length of 4096 characters"):
            PDFRepresentation(source="x" * 5000)

    def test_rows_invalid_field_reference_type(self) -> None:
        """rows must contain only str or PDFField references (line 464)."""
        field = PDFField(name="A", id="f-1", type="textfield")
        row = RowGroup.model_construct(fields=[123], page_index=1)
        with pytest.raises(ValueError, match="rows contain invalid field reference: 123"):
            PDFRepresentation(
                fields=[field],
                rows=[row],
            )

    def test_rows_unknown_field_after_resolution(self) -> None:
        """rows referencing PDFField objects not in fields fail the second check (lines 472-473)."""
        field_in_doc = PDFField(name="A", id="f-1", type="textfield")
        field_not_in_doc = PDFField(name="B", id="f-2", type="textfield")
        with pytest.raises(ValueError, match="rows reference fields that are not present in fields: f-2"):
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
