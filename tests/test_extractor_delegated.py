"""Tests for delegated PDFFormExtractor methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from privacyforms_pdf.extractor import PDFFormExtractor


class TestDelegatedMethods:
    """Tests for thin wrapper methods delegating to FormFiller."""

    def test_fill_form_fields_without_appearance(self) -> None:
        extractor = PDFFormExtractor()
        writer = MagicMock()
        field_values = {"field": "value"}
        with patch.object(
            extractor._filler, "_fill_form_fields_without_appearance"
        ) as mock:
            extractor._fill_form_fields_without_appearance(writer, field_values)
            mock.assert_called_once_with(writer, field_values)

    def test_get_field_by_name_from_writer(self) -> None:
        extractor = PDFFormExtractor()
        writer = MagicMock()
        with patch.object(
            extractor._filler,
            "get_field_by_name_from_writer",
            return_value={"name": "field"},
        ) as mock:
            result = extractor.get_field_by_name_from_writer(writer, "field_name")
            mock.assert_called_once_with(writer, "field_name")
            assert result == {"name": "field"}

    def test_get_widget_annotation(self) -> None:
        annotation_ref = MagicMock()
        with patch(
            "privacyforms_pdf.extractor.FormFiller._get_widget_annotation",
            return_value=("a", "b"),
        ) as mock:
            result = PDFFormExtractor._get_widget_annotation(annotation_ref)
            mock.assert_called_once_with(annotation_ref)
            assert result == ("a", "b")

    def test_get_widget_on_state(self) -> None:
        annotation = MagicMock()
        with patch(
            "privacyforms_pdf.extractor.FormFiller._get_widget_on_state",
            return_value="/On",
        ) as mock:
            result = PDFFormExtractor._get_widget_on_state(annotation)
            mock.assert_called_once_with(annotation)
            assert result == "/On"

    def test_resolve_radio_field_state(self) -> None:
        parent_annotation = MagicMock()
        with patch(
            "privacyforms_pdf.extractor.FormFiller._resolve_radio_field_state",
            return_value="/Yes",
        ) as mock:
            result = PDFFormExtractor._resolve_radio_field_state(
                parent_annotation, "Yes"
            )
            mock.assert_called_once_with(parent_annotation, "Yes")
            assert result == "/Yes"

    def test_sync_radio_button_states(self) -> None:
        extractor = PDFFormExtractor()
        writer = MagicMock()
        field_values = {"field": "value"}
        with patch.object(
            extractor._filler, "_sync_radio_button_states"
        ) as mock:
            extractor._sync_radio_button_states(writer, field_values)
            mock.assert_called_once_with(writer, field_values)

    def test_resolve_listbox_index(self) -> None:
        parent_annotation = MagicMock()
        with patch(
            "privacyforms_pdf.extractor.FormFiller._resolve_listbox_index",
            return_value=1,
        ) as mock:
            result = PDFFormExtractor._resolve_listbox_index(
                parent_annotation, "option"
            )
            mock.assert_called_once_with(parent_annotation, "option")
            assert result == 1

    def test_sync_listbox_selection_indexes(self) -> None:
        extractor = PDFFormExtractor()
        writer = MagicMock()
        field_values = {"field": "value"}
        with patch.object(
            extractor._filler, "_sync_listbox_selection_indexes"
        ) as mock:
            extractor._sync_listbox_selection_indexes(writer, field_values)
            mock.assert_called_once_with(writer, field_values)

    def test_escape_pdf_text(self) -> None:
        with patch(
            "privacyforms_pdf.extractor.FormFiller._escape_pdf_text",
            return_value="escaped",
        ) as mock:
            result = PDFFormExtractor._escape_pdf_text("text")
            mock.assert_called_once_with("text")
            assert result == "escaped"

    def test_build_listbox_appearance_stream(self) -> None:
        extractor = PDFFormExtractor()
        writer = MagicMock()
        annotation = MagicMock()
        parent_annotation = MagicMock()
        expected = MagicMock()
        with patch.object(
            extractor._filler,
            "_build_listbox_appearance_stream",
            return_value=expected,
        ) as mock:
            result = extractor._build_listbox_appearance_stream(
                writer, annotation, parent_annotation, 1
            )
            mock.assert_called_once_with(
                writer, annotation, parent_annotation, 1
            )
            assert result is expected
