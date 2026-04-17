"""Tests for Pydantic schema validator edge cases."""

from __future__ import annotations

import pytest

from privacyforms_pdf.schema import (
    ChoiceOption,
    FieldLayout,
    PDFField,
    RowGroup,
)


class TestRowGroupValidators:
    """Edge-case tests for RowGroup validators."""

    def test_page_index_below_minimum(self) -> None:
        """Test page_index below 1 is rejected."""
        with pytest.raises(ValueError, match="page_index must be at least 1"):
            RowGroup(page_index=0)

    def test_page_index_exceeds_maximum(self) -> None:
        """Test page_index above 100000 is rejected."""
        with pytest.raises(ValueError, match="page_index must not exceed 100000"):
            RowGroup(page_index=100_001)


class TestChoiceOptionValidators:
    """Edge-case tests for ChoiceOption validators."""

    def test_value_empty_after_strip(self) -> None:
        """Test choice value that is empty after stripping is rejected."""
        with pytest.raises(ValueError, match="choice values must not be empty"):
            ChoiceOption(value="   ")

    def test_value_too_long(self) -> None:
        """Test choice value exceeding 4096 characters is rejected."""
        match = "choice value exceeds maximum length of 4096 characters"
        with pytest.raises(ValueError, match=match):
            ChoiceOption(value="x" * 4097)

    def test_text_none_allowed(self) -> None:
        """Test None text is allowed."""
        option = ChoiceOption(value="a", text=None)
        assert option.text is None

    def test_text_too_long(self) -> None:
        """Test text exceeding 4096 characters is rejected."""
        with pytest.raises(ValueError, match="field exceeds maximum length of 4096 characters"):
            ChoiceOption(value="a", text="x" * 4097)

    def test_source_name_too_long(self) -> None:
        """Test source_name exceeding 4096 characters is rejected."""
        with pytest.raises(ValueError, match="field exceeds maximum length of 4096 characters"):
            ChoiceOption(value="a", source_name="x" * 4097)


class TestFieldLayoutValidators:
    """Edge-case tests for FieldLayout validators."""

    def test_page_negative(self) -> None:
        """Test negative page value is rejected."""
        with pytest.raises(ValueError, match="layout values must be non-negative"):
            FieldLayout(page=-1)

    def test_x_too_large(self) -> None:
        """Test x value above 1000000 is rejected."""
        with pytest.raises(ValueError, match="layout values must not exceed 1000000"):
            FieldLayout(x=1_000_001)

    def test_y_negative(self) -> None:
        """Test negative y value is rejected."""
        with pytest.raises(ValueError, match="layout values must be non-negative"):
            FieldLayout(y=-1)

    def test_width_too_large(self) -> None:
        """Test width value above 1000000 is rejected."""
        with pytest.raises(ValueError, match="layout values must not exceed 1000000"):
            FieldLayout(width=1_000_001)

    def test_height_negative(self) -> None:
        """Test negative height value is rejected."""
        with pytest.raises(ValueError, match="layout values must be non-negative"):
            FieldLayout(height=-1)


class TestPDFFieldValidators:
    """Edge-case tests for PDFField validators."""

    def test_name_empty_after_strip(self) -> None:
        """Test field name that is empty after stripping is rejected."""
        with pytest.raises(ValueError, match="field name must not be empty"):
            PDFField(name="   ", id="f-1", type="textfield")

    def test_name_too_long(self) -> None:
        """Test field name exceeding 2048 characters is rejected."""
        match = "field name exceeds maximum length of 2048 characters"
        with pytest.raises(ValueError, match=match):
            PDFField(name="x" * 2049, id="f-1", type="textfield")

    def test_id_empty_after_strip(self) -> None:
        """Test field id that is empty after stripping is rejected."""
        with pytest.raises(ValueError, match="field id must not be empty"):
            PDFField(name="Name", id="   ", type="textfield")

    def test_id_too_long(self) -> None:
        """Test field id exceeding 512 characters is rejected."""
        with pytest.raises(ValueError, match="field id exceeds maximum length of 512 characters"):
            PDFField(name="Name", id="x" * 513, type="textfield")

    def test_title_too_long(self) -> None:
        """Test title exceeding 4096 characters is rejected."""
        with pytest.raises(ValueError, match="field exceeds maximum length of 4096 characters"):
            PDFField(name="Name", id="f-1", type="textfield", title="x" * 4097)

    def test_format_too_long(self) -> None:
        """Test format exceeding 4096 characters is rejected."""
        with pytest.raises(ValueError, match="field exceeds maximum length of 4096 characters"):
            PDFField(name="Name", id="f-1", type="datefield", format="x" * 4097)


class TestPDFFieldValueLengthValidators:
    """Tests for validate_value_length edge cases."""

    def test_value_string_too_long(self) -> None:
        """String value exceeding 100k characters is rejected (line 330)."""
        match = "field value exceeds maximum length of 100000 characters"
        with pytest.raises(ValueError, match=match):
            PDFField(name="Name", id="f-1", type="textfield", value="x" * 100_001)

    def test_value_list_item_too_long(self) -> None:
        """List value item exceeding 100k characters is rejected (line 332)."""
        from privacyforms_pdf.schema import FieldFlags

        flags = FieldFlags(multi_select=True)
        match = "list value item exceeds maximum length of 100000 characters"
        with pytest.raises(ValueError, match=match):
            PDFField(
                name="Options", id="f-1", type="listbox", value=["x" * 100_001], field_flags=flags
            )


class TestPDFFieldPositiveIntegerValidators:
    """Tests for validate_positive_integers edge cases."""

    def test_max_length_zero(self) -> None:
        """max_length of zero is rejected (line 340)."""
        with pytest.raises(ValueError, match="numeric field constraints must be positive"):
            PDFField(name="Name", id="f-1", type="textfield", max_length=0)

    def test_max_length_too_large(self) -> None:
        """max_length above 1_000_000 is rejected (line 342)."""
        with pytest.raises(ValueError, match="numeric field constraints must not exceed 1000000"):
            PDFField(name="Name", id="f-1", type="textfield", max_length=1_000_001)
