"""Quick coverage wins for small modules."""

from __future__ import annotations

import pytest

from privacyforms_pdf.backends import __all__ as backends_all
from privacyforms_pdf.hooks import PDFFormsCommandsSpec
from privacyforms_pdf.models import FormValidationError
from privacyforms_pdf.schema import FieldLayout, PDFField
from privacyforms_pdf.schema_layout import _build_rows


class TestBackendsInit:
    """Tests for backends package init."""

    def test_all_is_empty_list(self) -> None:
        """It exports an empty __all__ list."""
        assert backends_all == []


class TestHooks:
    """Tests for hook specifications."""

    def test_register_commands_raises_not_implemented(self) -> None:
        """It raises NotImplementedError when called on the spec class."""
        spec = PDFFormsCommandsSpec()
        with pytest.raises(NotImplementedError):
            spec.register_commands()


class TestModels:
    """Tests for exception models."""

    def test_form_validation_error_str_with_errors(self) -> None:
        """It formats errors as a bulleted list when errors are present."""
        exc = FormValidationError("Validation failed", ["error one", "error two"])
        expected = "Validation failed\n- error one\n- error two"
        assert str(exc) == expected

    def test_form_validation_error_str_without_errors(self) -> None:
        """It returns just the message when no errors are present."""
        exc = FormValidationError("Validation failed")
        assert str(exc) == "Validation failed"


class TestSchemaLayout:
    """Tests for schema layout helpers."""

    def _make_field(
        self,
        *,
        name: str,
        field_id: str,
        page: int | None = 1,
        x: int = 0,
        y: int = 0,
    ) -> PDFField:
        """Helper to create a PDFField with layout."""
        layout = FieldLayout(page=page, x=x, y=y, width=10, height=10) if page is not None else None
        return PDFField(name=name, id=field_id, type="textfield", layout=layout)

    def test_build_rows_empty(self) -> None:
        """It returns an empty list when no fields are provided."""
        assert _build_rows([]) == []

    def test_build_rows_single_field(self) -> None:
        """It groups a single field into one row."""
        field = self._make_field(name="a", field_id="f-a", page=1, x=10, y=100)
        result = _build_rows([field])
        assert len(result) == 1
        assert result[0].page_index == 1
        assert result[0].fields == [field]

    def test_build_rows_skips_none_layout(self) -> None:
        """It skips fields that have no layout."""
        field_with = self._make_field(name="a", field_id="f-a", page=1, x=10, y=100)
        field_without = self._make_field(name="b", field_id="f-b", page=None)
        result = _build_rows([field_with, field_without])
        assert len(result) == 1
        assert result[0].fields == [field_with]

    def test_build_rows_same_y_same_row(self) -> None:
        """It groups fields with similar y coordinates into the same row."""
        f1 = self._make_field(name="a", field_id="f-a", page=1, x=50, y=100)
        f2 = self._make_field(name="b", field_id="f-b", page=1, x=10, y=105)
        result = _build_rows([f1, f2])
        assert len(result) == 1
        # Sorted by x ascending
        assert result[0].fields == [f2, f1]

    def test_build_rows_different_y_different_rows(self) -> None:
        """It splits fields with different y coordinates into separate rows."""
        f1 = self._make_field(name="a", field_id="f-a", page=1, x=10, y=200)
        f2 = self._make_field(name="b", field_id="f-b", page=1, x=10, y=50)
        result = _build_rows([f1, f2])
        assert len(result) == 2
        # Top row (higher y) comes first because we sort by y descending
        assert result[0].fields == [f1]
        assert result[1].fields == [f2]

    def test_build_rows_multiple_pages(self) -> None:
        """It groups fields by page index."""
        f1 = self._make_field(name="a", field_id="f-a", page=2, x=10, y=100)
        f2 = self._make_field(name="b", field_id="f-b", page=1, x=10, y=100)
        result = _build_rows([f1, f2])
        assert len(result) == 2
        # Pages sorted ascending
        assert result[0].page_index == 1
        assert result[1].page_index == 2

    def test_build_rows_y_tolerance(self) -> None:
        """It respects the y_tolerance parameter."""
        f1 = self._make_field(name="a", field_id="f-a", page=1, x=10, y=100)
        f2 = self._make_field(name="b", field_id="f-b", page=1, x=10, y=130)
        # Default tolerance is 15, so 30 diff should split
        result = _build_rows([f1, f2], y_tolerance=15)
        assert len(result) == 2
        # With tolerance 50, they should be in the same row
        result = _build_rows([f1, f2], y_tolerance=50)
        assert len(result) == 1

    def test_build_rows_multiple_in_row_sorted_by_x(self) -> None:
        """It sorts fields within a row by x coordinate."""
        f1 = self._make_field(name="a", field_id="f-a", page=1, x=100, y=50)
        f2 = self._make_field(name="b", field_id="f-b", page=1, x=10, y=50)
        f3 = self._make_field(name="c", field_id="f-c", page=1, x=50, y=50)
        result = _build_rows([f1, f2, f3])
        assert len(result) == 1
        assert result[0].fields == [f2, f3, f1]
