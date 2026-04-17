"""Tests for the FormReader class."""

from __future__ import annotations

from unittest.mock import MagicMock

from privacyforms_pdf.reader import FormReader


class TestFormReaderExtractWidgetsInfo:
    """Tests for FormReader.extract_widgets_info."""

    def test_extract_widgets_info_skips_duplicate_page_and_preserves_geometry(self) -> None:
        """Test repeated widgets on the same page do not duplicate pages or replace geometry."""
        reader = FormReader()

        first = {
            "/Subtype": "/Widget",
            "/T": "Field1",
            "/Rect": [10, 20, 30, 40],
        }
        second = {
            "/Subtype": "/Widget",
            "/T": "Field1",
            "/Rect": [50, 60, 70, 80],
        }

        first_ref = MagicMock()
        first_ref.get_object.return_value = first
        second_ref = MagicMock()
        second_ref.get_object.return_value = second

        pdf_reader = MagicMock()
        pdf_reader.pages = [{"/Annots": [first_ref, second_ref]}]

        info = reader.extract_widgets_info(pdf_reader)

        pages, geometry = info["Field1"]
        assert pages == [1]
        assert geometry is not None
        assert geometry.rect == (10.0, 20.0, 30.0, 40.0)
